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
    signals.signals_config = SimpleNamespace(
        mean_reversion_window=2,
        bollinger_window=5,
        bollinger_num_std=2.0,
        apply_winsorizing=False,
        windsor_percentiles={"lower": 0.05, "upper": 0.95},
        **config,
    )
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
    assert set(np.round(signals.mean_returns(), 6)) == {-1 / 6, 0.0, 1 / 6}


def test_bollinger_method_uses_bollinger_signal():
    signals = _signals(mean_reversion_method="bollinger", bollinger_scale=1.0)

    np.testing.assert_array_equal(signals.mean_returns(), signals._bollinger_signal())
    assert not np.array_equal(signals.mean_returns(), signals._rank_reversal_signal())


def test_unknown_method_raises():
    with pytest.raises(ValueError, match="Unknown mean_reversion_method"):
        _signals(mean_reversion_method="momentum").mean_returns()


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
    prices = PRICES.copy()
    prices.loc[5, "UP"] = 200.0
    prices.loc[5, "DOWN"] = 99.0

    bollinger = _signals(prices, mean_reversion_method="bollinger", bollinger_scale=1.0).mean_returns()
    ranked = _signals(prices, mean_reversion_method="rank_reversal").mean_returns()

    np.testing.assert_array_equal(np.sign(bollinger[[0, 2]]), np.sign(ranked[[0, 2]]) * -1)
    assert not np.isclose(abs(bollinger[0]), abs(bollinger[2]))
    assert np.isclose(abs(ranked[0]), abs(ranked[2]))


def test_bollinger_signal_is_zero_where_z_score_is_undefined():
    prices = PRICES.copy()
    prices["CONSTANT"] = 100.0
    prices["NO_HISTORY"] = np.nan

    view = _signals(prices, mean_reversion_method="bollinger", bollinger_scale=1.0).mean_returns()

    assert np.isfinite(view).all()
    assert view[3] == 0.0
    assert view[4] == 0.0
