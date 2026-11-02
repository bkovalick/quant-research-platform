import sys
import warnings
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from domain.signals.mean_reversion_signals import MeanReversionSignals


def _signals(prices: pd.DataFrame) -> MeanReversionSignals:
    signals = object.__new__(MeanReversionSignals)
    signals.market_state = SimpleNamespace(lookback_prices=lambda: prices)
    signals.signals_config = SimpleNamespace(mean_reversion_window=2)
    signals.apply_winsorizing = False
    signals.windsor_percentiles = {"lower": 0.05, "upper": 0.95}
    return signals


def test_mean_returns_ranks_losers_highest_without_warnings():
    prices = pd.DataFrame({
        "A": [100.0, 100.0, 90.0],
        "B": [100.0, 100.0, 100.0],
        "C": [100.0, 100.0, 110.0],
    })
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        ranked = _signals(prices).mean_returns()

    assert ranked[0] > ranked[1] > ranked[2]


def test_mean_returns_gives_missing_history_a_neutral_rank():
    prices = pd.DataFrame({
        "A": [100.0, 100.0, 90.0],
        "B": [np.nan, np.nan, np.nan],
        "C": [100.0, 100.0, 110.0],
    })

    ranked = _signals(prices).mean_returns()

    assert np.isfinite(ranked).all()
    assert ranked[1] == 0.0
    assert ranked[0] > ranked[2]
