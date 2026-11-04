import sys
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from domain.signals.vix_basis_signal import VixBasisSignal
from domain.strategies.vix_basis_strategy import VixBasisStrategy, FLAT, SHORT, LONG
from models.rebalance_problem import RebalanceProblem
from models.signals_config import SignalsConfig
from models.vix_basis_config import VixBasisConfig

IDX = pd.date_range("2024-01-01", periods=5, freq="B")
UNIVERSE = ["SVXY", "VIXM", "CASH"]
CFG = VixBasisConfig()


def _signal(ratios, **cfg):
    exo = pd.DataFrame({"^VIX": [r * 20.0 for r in ratios], "^VIX3M": [20.0] * len(ratios)},
                       index=IDX[: len(ratios)])
    return VixBasisSignal(SimpleNamespace(exogenous_universe=exo), VixBasisConfig(**cfg))


def _context(signal):
    return SimpleNamespace(
        signals={"vix_basis": signal},
        investment_universe=UNIVERSE,
        current_weights=pd.Series([0.0, 0.0, 1.0], index=UNIVERSE),
    )


def _strategy():
    return VixBasisStrategy(RebalanceProblem({"signal_source": "vix_basis"}))


@pytest.mark.parametrize("side, ratio, expected", [
    (FLAT, 0.85, SHORT),
    (FLAT, 0.92, FLAT),    # between short entry and exit: no new trade
    (SHORT, 0.92, SHORT),  # ...but an open short is held
    (SHORT, 0.96, FLAT),
    (FLAT, 1.10, LONG),
    (LONG, 1.02, LONG),
    (LONG, 0.98, FLAT),
    (SHORT, 1.10, LONG),   # regime jump flips sides in one step
    (LONG, 0.85, SHORT),
    (SHORT, None, SHORT),  # missing data holds the current side
])
def test_hysteresis(side, ratio, expected):
    assert VixBasisStrategy.next_side(side, ratio, CFG) == expected


def test_long_disabled_stays_flat_in_backwardation():
    assert VixBasisStrategy.next_side(FLAT, 1.20, VixBasisConfig(enable_long=False)) == FLAT


def test_signal_is_point_in_time_and_lagged():
    sig = _signal([0.80, 1.10, 0.95])
    assert sig.generate_signal() is None             # no update yet
    sig.update(1, IDX[1])
    assert sig.generate_signal() == pytest.approx(0.80)  # prior close, never today's or future rows
    sig = _signal([0.80, 1.10, 0.95], use_prior_close=False)
    sig.update(1, IDX[1])
    assert sig.generate_signal() == pytest.approx(1.10)


def test_signal_requires_exogenous_tickers():
    with pytest.raises(ValueError, match="VIX3M"):
        VixBasisSignal(SimpleNamespace(exogenous_universe=pd.DataFrame({"^VIX": [20.0]})), CFG)


def test_strategy_allocates_whole_book_to_one_leg():
    sig = _signal([0.85, 0.85, 1.10, 1.10, 0.97])
    strat = _strategy()
    held = []
    for i in range(1, 5):
        sig.update(i, IDX[i])
        w = strat.rebalance(_context(sig)).target_weights
        assert w.sum() == pytest.approx(1.0)
        held.append(w.idxmax())
    # lagged ratios seen: 0.85, 0.85, 1.10, 1.10
    assert held == ["SVXY", "SVXY", "VIXM", "VIXM"]


def test_strategy_errors_without_cash():
    sig = _signal([0.85, 0.85])
    sig.update(1, IDX[1])
    ctx = _context(sig)
    ctx.investment_universe = ["SVXY", "VIXM"]
    with pytest.raises(ValueError, match="CASH"):
        _strategy().rebalance(ctx)


def test_config_validation_and_parsing():
    with pytest.raises(ValueError):
        VixBasisConfig(short_entry=0.96, short_exit=0.95)
    sc = SignalsConfig.from_dict({"vix_basis": {"short_entry": 0.88}})
    assert sc.vix_basis.short_entry == 0.88 and sc.vix_basis.back_index == "^VIX3M"
    assert SignalsConfig.from_dict({}).vix_basis is None
