import logging
import time
from dataclasses import replace
from typing import Callable, Optional
import numpy as np
import pandas as pd

from domain.portfolio.portfolio import Portfolio
from domain.strategies.base_strategy import BaseStrategy
from domain.portfolio.tax_lot_ledger import TaxLotLedger
from models.rebalance_problem import RebalanceProblem
from models.backtest_run import BacktestRun
from models.rebalance_context import RebalanceContext
from models.rebalance_solution import RebalanceSolution
from simulation.market_state import MarketState
from services.signals_factory import SignalFactory
from utils.rebalance_steps import FREQ_TO_STEPS

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[float, pd.Timestamp], None]

def _announce(message: str, *args) -> None:
    """Log at INFO and echo to the console (local runs watch stdout)."""
    logger.info(message, *args)
    print(message % args)

class _ProgressTracker:
    """Reports whole-percent progress to an optional callback and logs each new year."""

    def __init__(self, total_steps: int, callback: Optional[ProgressCallback]):
        self._total_steps = max(1, total_steps)
        self._callback = callback
        self._last_pct = -1
        self._last_year = None

    def update(self, cursor: int, date: pd.Timestamp) -> None:
        if self._callback is not None:
            pct = int(100 * cursor / self._total_steps)
            if pct != self._last_pct:
                self._last_pct = pct
                self._callback(float(pct), date)

        if date.year != self._last_year:
            self._last_year = date.year
            _announce("Processing backtest year %s", date.year)

class BacktestingEngine:
    """Concrete implementation of a backtesting engine."""
    def __init__(self,
                 portfolio: Portfolio,
                 strategy: BaseStrategy,
                 market_state: MarketState,
                 signal_factory: SignalFactory,
                 tax_lot_ledger: TaxLotLedger = None,
                 progress_callback: Optional[ProgressCallback] = None):
        self.portfolio = portfolio
        self.strategy = strategy
        self.market_state = market_state
        self.signals_factory = signal_factory
        self.tax_lot_ledger = tax_lot_ledger
        self.progress_callback = progress_callback

    def run_backtest(self, rebalance_problem: RebalanceProblem) -> BacktestRun:
        """Run backtest on the given rebalance problem."""
        start_time = time.time()
        _announce("Starting backtest for %s assets at rebalance frequency %s",
                  len(rebalance_problem.investment_universe), rebalance_problem.rebalance_frequency)

        rebalance_every = self._get_steps(rebalance_problem.rebalance_frequency)
        weights = self._initialize_portfolio(rebalance_problem)
        progress = _ProgressTracker(len(self.market_state.investment_prices) - 1, self.progress_callback)

        while self.market_state.has_next():
            self.market_state.advance()
            cursor = self.market_state.cursor
            date = self.market_state.current_date()
            progress.update(cursor, date)

            weights = self.portfolio.drift(weights, self.market_state.investment_returns.iloc[cursor], cursor)
            if cursor < self.market_state.lookback_window:
                continue

            self.signals_factory.update(cursor, date)
            if cursor % rebalance_every == 0:
                weights = self._rebalance(cursor, date, weights, rebalance_problem)

        _announce("Backtest completed in %.2f seconds", time.time() - start_time)
        return self._build_backtest_run()

    def _initialize_portfolio(self, rebalance_problem: RebalanceProblem) -> np.ndarray:
        """Seed the portfolio (and tax lots, if enabled) with the initial weights."""
        initial_weights = np.array([
            rebalance_problem.initial_weights.get(ticker, 0.0)
            for ticker in rebalance_problem.investment_universe
        ])
        prices = self.market_state.investment_prices
        priced = prices.iloc[0].reindex(rebalance_problem.investment_universe).notna().to_numpy()
        initial_weights = self._restrict_to_tradable(initial_weights, priced, rebalance_problem.cash_index)
        self.portfolio.initialize(prices.index, prices.columns, initial_weights)

        if self.tax_lot_ledger is not None:
            self.tax_lot_ledger.initialize(self.market_state, self.portfolio, cursor=0)
        return initial_weights

    def _rebalance(self,
                   cursor: int,
                   date: pd.Timestamp,
                   prev_weights: np.ndarray,
                   rebalance_problem: RebalanceProblem) -> np.ndarray:
        """Ask the strategy for target weights, apply them, and update the tax ledger."""
        logger.debug("Rebalance step reached at %s (cursor=%s)", date, cursor)
        signals = self.signals_factory.build_signals()

        if self.tax_lot_ledger is not None:
            self.tax_lot_ledger.mark_to_market(self.market_state, self.portfolio, cursor)

        tradable = self._tradable_mask(cursor, rebalance_problem)
        context = self._build_rebalance_context(cursor, signals, rebalance_problem, tradable)
        solution = self.strategy.rebalance(context)
        solution = self._apply_leverage(solution, rebalance_problem)
        target_weights = np.asarray(solution.target_weights, dtype=float)
        target_weights = self._restrict_to_tradable(
            target_weights, tradable.to_numpy(), rebalance_problem.cash_index)
        if not np.allclose(target_weights, np.asarray(solution.target_weights, dtype=float), atol=1e-10):
            solution = replace(solution, target_weights=pd.Series(
                target_weights, index=rebalance_problem.investment_universe))

        reason = "no_trade_change" if np.allclose(target_weights, prev_weights, atol=1e-10) else "trade_executed"
        logger.info("reason_code=%s cursor=%s date=%s", reason, cursor, date)

        self.portfolio.apply(target_weights, prev_weights, cursor)

        if self.tax_lot_ledger is not None:
            self.tax_lot_ledger.apply_rebalance(self.market_state, self.portfolio, solution, cursor)
        return target_weights

    def _tradable_mask(self, cursor: int, rebalance_problem: RebalanceProblem) -> pd.Series:
        universe = list(rebalance_problem.investment_universe)
        tradable = getattr(self.market_state, "tradable", None)
        if tradable is None:
            return pd.Series(True, index=universe)
        return tradable(cursor).reindex(universe).fillna(False).astype(bool)

    @staticmethod
    def _restrict_to_tradable(weights: np.ndarray, tradable: np.ndarray, cash_index: Optional[int]) -> np.ndarray:
        """Zero the weight of untradable assets. The freed weight goes to CASH when it is in the
        universe; otherwise the remaining weights are rescaled to keep the same net exposure
        (skipped for a ~zero-net book, e.g. market neutral, where it just stays unallocated)."""
        weights = np.nan_to_num(np.asarray(weights, dtype=float), nan=0.0)
        tradable = np.asarray(tradable, dtype=bool)
        if tradable.all():
            return weights
        restricted = np.where(tradable, weights, 0.0)
        freed = float(weights[~tradable].sum())
        if abs(freed) < 1e-12:
            return restricted
        if cash_index is not None and tradable[cash_index]:
            restricted[cash_index] += freed
            return restricted
        original_net, kept_net = float(weights.sum()), float(restricted.sum())
        if abs(original_net) > 1e-12 and abs(kept_net) > 1e-12 and np.sign(original_net) == np.sign(kept_net):
            restricted *= original_net / kept_net
        return restricted

    @staticmethod
    def _apply_leverage(solution: RebalanceSolution, rebalance_problem: RebalanceProblem) -> RebalanceSolution:
        leverage = getattr(rebalance_problem, "leverage", 1.0)
        if leverage == 1.0:
            return solution
        return replace(solution, target_weights=solution.target_weights * leverage)

    def _get_steps(self, freq_param: str) -> int:
        key = (self.market_state.market_frequency, freq_param)
        return FREQ_TO_STEPS.get(key, 1)

    def _build_backtest_run(self) -> BacktestRun:
        diagnostics = self.strategy.get_diagnostics() if hasattr(self.strategy, "get_diagnostics") else {}

        if hasattr(self.signals_factory, "get_diagnostics"):
            diagnostics.update(self.signals_factory.get_diagnostics())

        return BacktestRun(
            portfolio=self.portfolio,
            **diagnostics
        )

    def _build_rebalance_context(self,
                                 cursor: int,
                                 signals: dict,
                                 rebalance_problem: RebalanceProblem,
                                 tradable: Optional[pd.Series] = None) -> RebalanceContext:
        return RebalanceContext(
            tradable=tradable,
            cursor=cursor,
            current_weights=self.portfolio.weights.iloc[cursor],
            signals=signals,
            portfolio=self.portfolio,
            initial_weights=rebalance_problem.initial_weights,
            investment_universe=self.market_state.investment_universe,
            tax_lot_ledger=self.tax_lot_ledger,
            rebalance_problem=rebalance_problem,
        )
