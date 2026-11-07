"""Assets with no price (before listing, after delisting) must stay NaN end to end:
never backfilled into a flat history, never given weight, never poisoning other assets."""
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
from sklearn.covariance import LedoitWolf

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from domain.portfolio.portfolio import Portfolio
from domain.signals.risk_return_signals import RiskReturnSignals
from domain.strategies.equal_weight_strategy import EqualWeightStrategy
from models.market_config import MarketStateConfig
from models.rebalance_problem import RebalanceProblem
from simulation.backtesting_engine import BacktestingEngine
from simulation.market_state import MarketState

N_DAYS, LISTS_AT, LOOKBACK = 120, 40, 21     # LOOKBACK = LOOKBACK_WINDOWS["d"]["1m"]


def _market_state() -> MarketState:
    rng = np.random.default_rng(0)
    dates = pd.date_range("2024-01-01", periods=N_DAYS, freq="B")
    prices = pd.DataFrame({
        "A": 100 * np.cumprod(1 + rng.normal(0, 0.01, N_DAYS)),
        "B": 50 * np.cumprod(1 + rng.normal(0, 0.02, N_DAYS)),
        "LATE": 20 * np.cumprod(1 + rng.normal(0, 0.03, N_DAYS)),
        "SPY": 400 * np.cumprod(1 + rng.normal(0, 0.01, N_DAYS)),
    }, index=dates)
    prices.iloc[:LISTS_AT, prices.columns.get_loc("LATE")] = np.nan       # lists on day LISTS_AT
    store = SimpleNamespace(prices=prices, benchmark="SPY", apply_market_caps=False, transaction_cost=0.0)
    config = MarketStateConfig.from_dict({
        "market_frequency": "d", "lookback_window_key": "1m",
        "investment_universe": ["A", "B", "LATE"],
    })
    return MarketState(store, config)


def test_tradable_requires_a_price_and_a_full_lookback_window():
    state = _market_state()
    assert not state.tradable(LISTS_AT - 1)["LATE"]                  # not listed yet
    assert not state.tradable(LISTS_AT + LOOKBACK // 2)["LATE"]      # listed, window still partial
    assert state.tradable(LISTS_AT + LOOKBACK + 1)["LATE"]           # full window of returns
    assert state.tradable(LISTS_AT - 1)[["A", "B"]].all()


def test_covariance_ignores_incomplete_columns_instead_of_dropping_rows():
    state = _market_state()
    state.cursor = LISTS_AT + 5            # LATE has only 5 days of returns in the window
    signals = RiskReturnSignals(state, SimpleNamespace(apply_winsorizing=False, windsor_percentiles=None))

    cov = signals.covariance_matrix()
    assert cov.shape == (3, 3) and np.isfinite(cov).all()
    assert np.linalg.eigvalsh(cov).min() > 0                        # PSD and invertible
    assert cov[2, 0] == 0 and cov[2, 1] == 0                        # no fake covariance for LATE
    # A and B keep their whole window (all 21 rows), not just the rows where LATE also has data
    full_window = state.lookback_returns()[["A", "B"]]
    assert len(full_window) == LOOKBACK
    expected = LedoitWolf().fit(full_window.to_numpy()).covariance_ * state.annual_trading_days
    np.testing.assert_allclose(cov[:2, :2], expected)
    assert np.isnan(signals.mean_returns()[2])


def test_backtest_gives_no_weight_until_tradable_and_returns_stay_finite():
    state = _market_state()
    problem = RebalanceProblem({
        "investment_universe": ["A", "B", "LATE"],
        "rebalance_frequency": "daily",
        "initial_weights": {"A": 0.4, "B": 0.3, "LATE": 0.3},
    })
    portfolio = Portfolio()
    signal_factory = SimpleNamespace(update=lambda cursor, date: None, build_signals=lambda: {})
    engine = BacktestingEngine(portfolio, EqualWeightStrategy(problem), state, signal_factory)
    engine.run_backtest(problem)

    weights, returns = portfolio.weights, portfolio.returns
    assert np.isfinite(returns).all()
    # Initial 30% in LATE can't be bought (no price); with no CASH it is spread pro rata.
    np.testing.assert_allclose(weights.iloc[0].to_numpy(), [0.4 / 0.7, 0.3 / 0.7, 0.0])
    first_tradable = LISTS_AT + LOOKBACK
    assert (weights["LATE"].iloc[:first_tradable] == 0).all()
    assert weights["LATE"].iloc[first_tradable + 1:].gt(0).all()
    assert np.allclose(weights.iloc[first_tradable + 1:].sum(axis=1), 1.0)


def test_held_asset_that_loses_its_price_is_carried_then_exited():
    weights = np.array([0.5, 0.5, 0.0])
    returns = np.array([0.01, np.nan, np.nan])          # B stops pricing while held
    portfolio = Portfolio()
    portfolio.initialize(pd.date_range("2024-01-01", periods=2), np.array(["A", "B", "C"]), weights)
    drifted = portfolio.drift(weights, returns, cursor=1)
    assert np.isfinite(drifted).all()
    assert np.isclose(portfolio.returns.iloc[1], 0.005)              # only A's return counts

    restricted = BacktestingEngine._restrict_to_tradable(
        np.array([0.3, 0.5, 0.2]), np.array([True, False, True]), cash_index=2)
    np.testing.assert_allclose(restricted, [0.3, 0.0, 0.7])          # freed weight goes to CASH
