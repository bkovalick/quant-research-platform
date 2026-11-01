import numpy as np
import pandas as pd
import pytest
from types import SimpleNamespace

from src.domain.strategies.systematic_strategy import SystematicStrategy
from src.models.market_config import MarketStateConfig
from src.models.rebalance_context import RebalanceContext
from src.models.rebalance_problem import RebalanceProblem
from src.services.optimizer_factory import OptimizerFactory
from src.simulation.market_state import MarketState

TICKERS = ["AAPL", "MSFT", "NVDA", "AMZN"]


class DummySignal:
    def __init__(self):
        self._signal = pd.Series([0.03, 0.015, -0.01, 0.02], index=TICKERS)

    def mean_returns(self):
        return self._signal.to_numpy(dtype=float)

    def covariance_matrix(self):
        cov = np.eye(len(TICKERS), dtype=float) * 0.0008
        for i in range(len(TICKERS)):
            for j in range(len(TICKERS)):
                if i != j:
                    cov[i, j] = 0.0002
        return cov

    def portfolio_vol(self, weights):
        weights = np.asarray(weights, dtype=float)
        cov = self.covariance_matrix()
        return float(np.sqrt(weights @ cov @ weights))


def _build_market_state() -> MarketState:
    rng = np.random.default_rng(42)
    dates = pd.date_range("2020-01-02", periods=700, freq="B")
    drift = np.linspace(0.0003, 0.0012, len(dates))
    shocks = rng.normal(loc=0.0005, scale=0.012, size=(len(dates), len(TICKERS)))
    prices = 100 * np.cumprod(1 + shocks + drift[:, None], axis=0)
    price_df = pd.DataFrame(prices, index=dates, columns=TICKERS)

    store = SimpleNamespace(
        prices=price_df,
        apply_market_caps=False,
        transaction_cost=0.003,
        sectors=pd.Series({ticker: "Information Technology" for ticker in TICKERS}),
        market_caps=pd.Series({ticker: 1.0e9 for ticker in TICKERS}),
        etf_market_caps=pd.Series({ticker: 1.0e9 for ticker in TICKERS}),
    )

    config = MarketStateConfig.from_dict(
        {
            "lookback_window_key": "1y",
            "market_frequency": "d",
            "cash_allocation": 0.0,
            "investment_universe": TICKERS,
            "signal_universe": TICKERS,
            "exogenous_tickers": [],
        }
    )

    return MarketState(store, config)


def test_ls_market_neutral_ml_one_off_date_is_feasible_after_warmup():
    market_state = _build_market_state()
    market_state.cursor = market_state.lookback_window + 5

    rebalance_problem = RebalanceProblem(
        {
            "n_assets": len(TICKERS),
            "optimizer_type": "portfolio_optimizer",
            "strategy_type": "systematic_strategy",
            "apply_max_return_objective": True,
            "initial_weights": {ticker: 0.25 for ticker in TICKERS},
            "cash_allocation": 0.0,
            "rebalance_frequency": "weekly",
            "risk_aversion": 2.5,
            "turnover_limit": 0.5,
            "min_position_size": -0.06,
            "max_position_size": 0.06,
            "max_number_of_positions": len(TICKERS),
            "concentration_strength": 1,
            "optimizer_vol_constraint": 0.2,
            "signal_source": "ml_cross_sectional",
            "investment_universe": TICKERS,
            "max_long": 0.8,
            "max_short": 0.8,
            "sector_constraints": {"Information Technology": [-0.1, 0.1]},
        }
    )

    optimizer = OptimizerFactory.create_optimizer(rebalance_problem.optimizer_type)
    strategy = SystematicStrategy(rebalance_problem, optimizer=optimizer)

    rebalance_context = RebalanceContext(
        cursor=market_state.cursor,
        signals={"ml_cross_sectional": DummySignal()},
        initial_weights={ticker: 0.25 for ticker in TICKERS},
        current_weights=pd.Series({ticker: 0.25 for ticker in TICKERS}),
        investment_universe=TICKERS,
        rebalance_problem=rebalance_problem,
        portfolio=None,
        tax_lot_ledger=None,
    )

    solution = strategy.rebalance(rebalance_context)
    weights = np.asarray(solution.target_weights, dtype=float)

    assert market_state.cursor >= market_state.lookback_window
    assert np.isfinite(weights).all()
    assert np.all(weights >= rebalance_problem.min_position_size - 1e-9)
    assert np.all(weights <= rebalance_problem.max_position_size + 1e-9)
    assert weights.abs().sum() <= (rebalance_problem.max_long + rebalance_problem.max_short) + 1e-9


STRATEGY_SCAFFOLD = [
    pytest.param("pairs_trading_strategy", marks=pytest.mark.skip(reason="scaffold only; not implemented yet")),
    pytest.param("equal_weight_strategy", marks=pytest.mark.skip(reason="scaffold only; not implemented yet")),
    pytest.param("fwp_strategy", marks=pytest.mark.skip(reason="scaffold only; not implemented yet")),
]


@pytest.mark.parametrize("strategy_name", STRATEGY_SCAFFOLD)
def test_strategy_feasibility_scaffold(strategy_name):
    assert strategy_name
