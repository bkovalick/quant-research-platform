import pandas as pd

from domain.strategies.base_strategy import BaseStrategy
from domain.signals.pairs_trading_signal import PairsTradingSignal
from domain.optimizers.target_weight_optimizer import TargetWeightOptimizer
from models.rebalance_problem import RebalanceProblem
from models.rebalance_context import RebalanceContext
from models.rebalance_solution import RebalanceSolution

class PairsTradingStrategy(BaseStrategy):
    """
    Market-neutral pairs strategy. The strategy owns a position book
    ({(asset_a, asset_b): +1 long spread / -1 short spread}) so position state
    never depends on drifted portfolio weights. Pairs not in the book carry zero weight.
    """
    def __init__(self,
                 rebalance_problem: RebalanceProblem,
                 optimizer: TargetWeightOptimizer = None):
        super().__init__(rebalance_problem, optimizer)
        self.pairs_cache = []
        self.position_book = {}

    def get_diagnostics(self) -> dict:
        return {"pairs_cache": self.pairs_cache}

    def rebalance(self, rebalance_context: RebalanceContext) -> RebalanceSolution:
        signal_key = self.rebalance_problem.signal_source
        active_signal = rebalance_context.signals.get(signal_key)

        if active_signal is None:
            target_weights = pd.Series(
                rebalance_context.current_weights,
                index=rebalance_context.investment_universe,
            )
        else:
            target_weights = self._run_pairs_strategy(
                rebalance_context.investment_universe, active_signal
            )
        return RebalanceSolution(
            target_weights=target_weights,
            sell_allocations={},
            realized_tax_cost=0.0,
            tracking_error=0.0
        )

    def _run_pairs_strategy(self,
                            tickers: list,
                            active_signal: PairsTradingSignal) -> pd.Series:
        if not isinstance(active_signal, PairsTradingSignal):
            raise ValueError("Active signal must be of type PairsTradingSignal")

        pairs = active_signal.compute_trading_pairs(self.position_book)
        weights = pd.Series(0.0, index=tickers)
        if pairs.empty:
            self.position_book.clear()
            return weights

        self._update_position_book(pairs)
        self.pairs_cache.extend(pairs.to_dict("records"))
        keys = list(zip(pairs["AssetA"], pairs["AssetB"]))
        held = pairs[[k in self.position_book for k in keys]].copy()
        if held.empty:
            return weights

        sides = pd.Series([self.position_book[k] for k in zip(held["AssetA"], held["AssetB"])], index=held.index)
        denom = 1.0 + held["HedgeRatio"].abs()
        held["WeightA"] = sides * held["FinalWeight"] / denom
        held["WeightB"] = -sides * held["FinalWeight"] * held["HedgeRatio"] / denom

        combined = held.groupby("AssetA")["WeightA"].sum().add(
            held.groupby("AssetB")["WeightB"].sum(), fill_value=0
        )
        weights.update(combined.reindex(tickers).dropna())

        gross = weights.abs().sum()
        if active_signal.max_gross and gross > active_signal.max_gross:
            weights = weights * (active_signal.max_gross / gross)

        return weights

    def _update_position_book(self, pairs: pd.DataFrame) -> None:
        for row in pairs.itertuples():
            key = (row.AssetA, row.AssetB)
            if row.State == "EnterLong":
                self.position_book[key] = 1.0
            elif row.State == "EnterShort":
                self.position_book[key] = -1.0
            elif row.State == "Exit":
                self.position_book.pop(key, None)
