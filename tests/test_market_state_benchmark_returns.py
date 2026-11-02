import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from domain.signals.signals import Signals
from models.market_config import MarketStateConfig
from simulation.market_state import MarketState


class _BetaSignals(Signals):
    def mean_returns(self):
        raise NotImplementedError

    def covariance_matrix(self):
        raise NotImplementedError

    def portfolio_vol(self, weights):
        raise NotImplementedError


def _build_market_state():
    dates = pd.date_range("2024-01-01", periods=5, freq="B")
    prices = pd.DataFrame(
        {
            "ASSET": [100.0, 120.0, 96.0, 115.2, 100.0],
            "SPY": [100.0, 110.0, 99.0, 108.9, 87.12],
        },
        index=dates,
    )
    store = SimpleNamespace(
        prices=prices,
        benchmark="SPY",
        apply_market_caps=False,
        transaction_cost=0.0,
    )
    config = MarketStateConfig.from_dict(
        {
            "market_frequency": "d",
            "investment_universe": ["ASSET"],
            "signal_universe": ["ASSET"],
        }
    )
    return MarketState(store, config)


def test_market_state_exposes_frequency_aligned_benchmark_returns():
    market_state = _build_market_state()

    expected = market_state.store.prices["SPY"].pct_change(fill_method=None).fillna(0)
    pd.testing.assert_series_equal(market_state.market_returns, expected)


def test_beta_vector_uses_market_state_returns_only_through_current_cursor():
    market_state = _build_market_state()
    market_state.cursor = 3
    signals = _BetaSignals(
        market_state,
        SimpleNamespace(
            apply_winsorizing=False,
            windsor_percentiles={"lower": 0.01, "upper": 0.99},
        ),
    )

    np.testing.assert_allclose(signals.beta_vector, [2.0])
