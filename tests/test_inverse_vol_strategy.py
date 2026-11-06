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

from domain.signals.volatility_forecasting_signals import VolatilityForecastingSignals
from domain.strategies.inverse_vol_strategy import InverseVolStrategy
from models.rebalance_problem import RebalanceProblem
from models.signals_config import SignalsConfig


def _returns(n=120, seed=0):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2024-01-01", periods=n, freq="B")
    return pd.DataFrame({
        "LOW": rng.normal(0, 0.005, n),    # 0.5% daily vol
        "HIGH": rng.normal(0, 0.020, n),   # 2.0% daily vol
        "FLAT": 0.0,                       # backfilled before listing: no variation
        "CASH": 0.0001,                    # constant accrual: zero vol
    }, index=idx)


def _signal(returns, forecast_type="rolling"):
    state = SimpleNamespace(
        annual_trading_days=252,
        lookback_returns=lambda: returns,
        lookback_prices=lambda: (1 + returns).cumprod(),
    )
    cfg = SignalsConfig.from_dict({"inverse_vol": {"forecast_type": forecast_type, "window": 60}})
    return VolatilityForecastingSignals(state, cfg)


def _rebalance(signal, cash_allocation=0.0, universe=("LOW", "HIGH", "FLAT", "CASH")):
    strategy = InverseVolStrategy(RebalanceProblem({"signal_source": "volatility_forecast",
                                                    "cash_allocation": cash_allocation}))
    context = SimpleNamespace(signals={"volatility_forecast": signal}, investment_universe=list(universe),
                              current_weights=pd.Series(0.0, index=list(universe)))
    return strategy.rebalance(context).target_weights


@pytest.mark.parametrize("forecast_type", ["rolling", "ewma"])
def test_weights_are_inverse_to_vol_and_skip_zero_vol_assets(forecast_type):
    w = _rebalance(_signal(_returns(), forecast_type))
    assert w.sum() == pytest.approx(1.0)
    assert w["FLAT"] == 0.0 and w["CASH"] == 0.0
    assert w["LOW"] / w["HIGH"] == pytest.approx(4.0, rel=0.35)   # vol ratio is 4:1


def test_cash_allocation_is_held_in_cash():
    w = _rebalance(_signal(_returns()), cash_allocation=0.1)
    assert w["CASH"] == pytest.approx(0.1)
    assert w.drop("CASH").sum() == pytest.approx(0.9)


def test_missing_inverse_vol_block_is_a_clear_error():
    state = SimpleNamespace(annual_trading_days=252, lookback_returns=lambda: _returns())
    signal = VolatilityForecastingSignals(state, SignalsConfig.from_dict({}))
    with pytest.raises(ValueError, match="signals_config.inverse_vol"):
        _rebalance(signal)
