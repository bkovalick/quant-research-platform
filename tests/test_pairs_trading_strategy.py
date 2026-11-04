import numpy as np
import pandas as pd

from domain.signals.pairs_trading_signal import PairsTradingSignal
from domain.strategies.pairs_trading_strategy import PairsTradingStrategy
from models.pairs_trading_config import PairsTradingConfig


class FakeMarketState:
    def __init__(self, prices: pd.DataFrame):
        self.prices = prices
        self.end = len(prices)
        self.sectors_to_tickers = {"S": list(prices.columns)}

    def lookback_prices(self):
        return self.prices.iloc[: self.end]

    def current_date(self):
        return self.prices.index[self.end - 1]


def _prices(n=80, seed=0):
    rng = np.random.default_rng(seed)
    base = np.cumsum(rng.normal(0, 0.01, n))
    noise = rng.normal(0, 0.004, n)
    idx = pd.date_range("2024-01-01", periods=n)
    return pd.DataFrame({"A": 100 * np.exp(base + noise), "B": 100 * np.exp(base)}, index=idx)


def _config(**kw):
    d = dict(pairs_lookback_horizon=20, cointegration_threshold=1.0, correlation_filter=0.0,
             pairs_entry=1.25, pairs_exit=0.5, pairs_stop_loss=3.5, per_pair_gross=0.1,
             pairs_reselect_every=20, pairs_max_gross=1.0)
    d.update(kw)
    return PairsTradingConfig(**d)


def _signal(prices, **kw):
    state = FakeMarketState(prices)
    return state, PairsTradingSignal(state, _config(**kw))


def test_state_uses_position_book_not_weights():
    _, sig = _signal(_prices())
    pair = ("A", "B")
    assert sig._determine_state(pair, 2.0, {}) == "EnterShort"
    assert sig._determine_state(pair, -2.0, {}) == "EnterLong"
    assert sig._determine_state(pair, 1.0, {}) == "Flat"
    assert sig._determine_state(pair, 1.0, {pair: 1.0}) == "HoldLong"
    assert sig._determine_state(pair, 1.0, {pair: -1.0}) == "HoldShort"
    assert sig._determine_state(pair, 0.1, {pair: 1.0}) == "Exit"
    assert sig._determine_state(pair, 4.0, {pair: 1.0}) == "Exit"


def test_no_reentry_beyond_stop_loss():
    _, sig = _signal(_prices())
    assert sig._determine_state(("A", "B"), 5.0, {}) == "Flat"


def test_hedge_ratio_is_log_slope():
    prices = _prices()
    _, sig = _signal(prices)
    h = sig._hedge_ratio(np.log(prices["A"]), np.log(prices["B"]))
    assert 0.8 < h < 1.2


def test_pairs_reselected_only_on_schedule():
    prices = _prices()
    state, sig = _signal(prices, pairs_reselect_every=5)
    calls = []
    original = sig._reselect_pairs
    sig._reselect_pairs = lambda *a, **k: (calls.append(1), original(*a, **k))
    for end in range(60, 70):
        state.end = end
        sig.compute_trading_pairs({})
    assert len(calls) == 2


def test_strategy_goes_flat_after_exit_and_is_dollar_neutral():
    prices = _prices()
    state, sig = _signal(prices)
    strat = PairsTradingStrategy.__new__(PairsTradingStrategy)
    strat.pairs_cache, strat.position_book = [], {}
    tickers = ["A", "B"]

    strat.position_book[("A", "B")] = 1.0
    state.end = 60
    sig.compute_trading_pairs({})
    sig._hedge_ratios = {("A", "B"): 1.0}

    pairs = pd.DataFrame([{"AssetA": "A", "AssetB": "B", "HedgeRatio": 1.0, "FinalWeight": 0.1, "State": "HoldLong"}])
    sig.compute_trading_pairs = lambda book: pairs
    w = strat._run_pairs_strategy(tickers, sig)
    assert np.isclose(w["A"], 0.05) and np.isclose(w["B"], -0.05)

    pairs = pd.DataFrame([{"AssetA": "A", "AssetB": "B", "HedgeRatio": 1.0, "FinalWeight": 0.1, "State": "Exit"}])
    w = strat._run_pairs_strategy(tickers, sig)
    assert (w == 0).all()
    assert strat.position_book == {}


def test_gross_is_capped():
    prices = _prices()
    _, sig = _signal(prices, pairs_max_gross=0.05)
    strat = PairsTradingStrategy.__new__(PairsTradingStrategy)
    strat.pairs_cache, strat.position_book = [], {}
    pairs = pd.DataFrame([{"AssetA": "A", "AssetB": "B", "HedgeRatio": 1.0, "FinalWeight": 0.1, "State": "EnterLong"}])
    sig.compute_trading_pairs = lambda book: pairs
    w = strat._run_pairs_strategy(["A", "B"], sig)
    assert np.isclose(w.abs().sum(), 0.05)
