import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from domain.signals.mean_reversion_signals import MeanReversionSignals
from models.signals_config import SignalsConfig

PRICES = pd.DataFrame({
    "UP": [100.0, 100.0, 100.0, 100.0, 100.0, 110.0],
    "FLAT": [100.0, 101.0, 100.0, 101.0, 100.0, 100.5],
    "DOWN": [100.0, 100.0, 100.0, 100.0, 100.0, 90.0],
})


def _signals(prices: pd.DataFrame = PRICES, **config) -> MeanReversionSignals:
    signals = object.__new__(MeanReversionSignals)
    market_state = SimpleNamespace(lookback_prices=lambda: prices, annual_trading_days=52)
    signals.market_state = market_state
    signals.signals_config = SignalsConfig.from_dict({
        "mean_reversion_window": 2,
        "bollinger_window": 5,
        "bollinger_num_std": 2.0,
        "apply_winsorizing": False,
        **config,
    })
    signals.apply_winsorizing = False
    signals.windsor_percentiles = {"lower": 0.05, "upper": 0.95}
    return signals


def test_signals_config_defaults_to_rank_reversal():
    config = SignalsConfig.from_dict({})

    assert config.mean_reversion_method == "rank_reversal"
    assert config.bollinger_window == 20
    assert config.bollinger_num_std == 2.0
    assert config.bollinger_scale == 0.01


def test_signals_config_reads_method_and_bollinger_settings():
    config = SignalsConfig.from_dict({
        "mean_reversion_method": "bollinger",
        "bollinger_window": 10,
        "bollinger_num_std": 1.5,
        "bollinger_scale": 0.05,
    })

    assert config.mean_reversion_method == "bollinger"
    assert config.bollinger_window == 10
    assert config.bollinger_num_std == 1.5
    assert config.bollinger_scale == 0.05


def test_method_defaults_to_rank_reversal_when_unset():
    signals = _signals()

    np.testing.assert_array_equal(signals.mean_returns(), signals._rank_reversal_signal())


def test_rank_reversal_method_uses_rank_signal():
    signals = _signals(mean_reversion_method="rank_reversal")

    np.testing.assert_array_equal(signals.mean_returns(), signals._rank_reversal_signal())
    assert set(np.round(signals.mean_returns(), 6)) == {round(-1 / 6, 6), round(1 / 6, 6), 0.5}


def test_bollinger_method_uses_bollinger_signal():
    signals = _signals(mean_reversion_method="bollinger", bollinger_scale=1.0)

    np.testing.assert_array_equal(signals.mean_returns(), signals._bollinger_signal())
    assert not np.array_equal(signals.mean_returns(), signals._rank_reversal_signal())


def test_unknown_method_raises():
    # Rejected when the config is loaded, before any market data is fetched.
    with pytest.raises(ValueError, match="mean_reversion_method must be one of"):
        _signals(mean_reversion_method="momentum")


def test_bollinger_signal_is_negative_z_score_so_stretched_assets_revert():
    view = _signals(mean_reversion_method="bollinger", bollinger_scale=1.0).mean_returns()

    up, flat, down = view
    assert up < 0 < down
    assert abs(flat) < abs(up)


def test_bollinger_signal_matches_manual_z_score():
    window = 5
    rolling = PRICES.rolling(window)
    expected = -((PRICES - rolling.mean()) / rolling.std()).iloc[-1].values

    view = _signals(mean_reversion_method="bollinger", bollinger_scale=1.0).mean_returns()

    np.testing.assert_allclose(view, expected)


def test_bollinger_scale_multiplies_signal():
    unscaled = _signals(mean_reversion_method="bollinger", bollinger_scale=1.0).mean_returns()
    scaled = _signals(mean_reversion_method="bollinger", bollinger_scale=0.01).mean_returns()

    np.testing.assert_allclose(scaled, unscaled * 0.01)


def test_bollinger_signal_keeps_magnitude_unlike_rank_signal():
    baseline = [100.0, 101.0, 99.0, 100.0, 101.0, 99.0]

    def frame(up_last: float) -> pd.DataFrame:
        return pd.DataFrame({
            "UP": baseline[:-1] + [up_last],
            "FLAT": baseline,
            "DOWN": baseline[:-1] + [97.0],
        })

    mild, extreme = frame(101.0), frame(104.0)

    ranked_mild = _signals(mild, mean_reversion_method="rank_reversal").mean_returns()
    ranked_extreme = _signals(extreme, mean_reversion_method="rank_reversal").mean_returns()
    z_mild = _signals(mild, mean_reversion_method="bollinger", bollinger_scale=1.0).mean_returns()
    z_extreme = _signals(extreme, mean_reversion_method="bollinger", bollinger_scale=1.0).mean_returns()

    np.testing.assert_array_equal(ranked_mild, ranked_extreme)
    assert z_extreme[0] < z_mild[0] < 0


def test_bollinger_signal_is_zero_where_z_score_is_undefined():
    prices = PRICES.copy()
    prices["CONSTANT"] = 100.0
    prices["NO_HISTORY"] = np.nan

    view = _signals(prices, mean_reversion_method="bollinger", bollinger_scale=1.0).mean_returns()

    assert np.isfinite(view).all()
    assert view[3] == 0.0
    assert view[4] == 0.0
