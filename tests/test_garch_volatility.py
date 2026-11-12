"""GARCH vol signal: recursion matches arch's forecast, parameters refit on the configured cadence."""
import sys
import types
from pathlib import Path
from unittest import mock

import numpy as np
import pandas as pd

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import domain.signals.volatility_forecasting_signals as vfs
from arch import arch_model

ANN = 252


def _simulate_garch(n, omega=0.05, alpha=0.08, beta=0.90, seed=0):
    """Daily returns (decimal) from a GARCH(1,1) with parameters in pct^2 units."""
    rng = np.random.default_rng(seed)
    var = omega / (1 - alpha - beta)
    out = np.empty(n)
    for t in range(n):
        out[t] = np.sqrt(var) * rng.standard_normal()
        var = omega + alpha * out[t] ** 2 + beta * var
    return out / 100.0


def _signal(returns: pd.DataFrame, dates, refit_every):
    state = {"i": 0}
    market_state = types.SimpleNamespace(
        annual_trading_days=ANN,
        lookback_returns=lambda: returns,
        current_date=lambda: dates[state["i"]],
    )
    cfg = types.SimpleNamespace(apply_winsorizing=False, windsor_percentiles=None,
                                inverse_vol=types.SimpleNamespace(refit_every=refit_every))
    return vfs.VolatilityForecastingSignals(market_state, cfg), state


def test_filter_matches_arch_one_step_forecast():
    r = pd.Series(_simulate_garch(2000)) * 100.0
    res = arch_model(r, vol="Garch", p=1, q=1, rescale=False).fit(disp="off")
    p = res.params
    ours = vfs.VolatilityForecastingSignals._filter(r.to_numpy(), p["mu"], p["omega"], p["alpha[1]"], p["beta[1]"])
    theirs = res.forecast(horizon=1, reindex=False).variance.iloc[-1, 0]
    np.testing.assert_allclose(ours, theirs, rtol=1e-6)


def test_annualized_vol_is_sensible_and_refits_on_cadence():
    returns = pd.DataFrame({"A": _simulate_garch(252, seed=1), "B": _simulate_garch(252, seed=2) * 2})
    dates = pd.date_range("2020-01-31", periods=12, freq="ME")      # 12 monthly rebalances
    signal, state = _signal(returns, dates, refit_every=3)

    calls = {"n": 0}
    real = vfs.arch_model

    def counting(*a, **k):
        calls["n"] += 1
        return real(*a, **k)

    with mock.patch.object(vfs, "arch_model", counting):
        for i in range(len(dates)):
            state["i"] = i
            vols = signal.garch_volatility()

    assert calls["n"] == 2 * 4                                      # 2 assets x refit every 3 of 12 months
    true_vol = np.sqrt(0.05 / (1 - 0.08 - 0.90)) / 100 * np.sqrt(ANN)   # ~0.25 annualized
    assert 0.5 * true_vol < vols["A"] < 2 * true_vol
    assert 1.0 * true_vol < vols["B"] < 4 * true_vol                # B is scaled 2x


def test_short_flat_and_integrated_cases():
    returns = pd.DataFrame({"NEW": [np.nan] * 240 + list(np.full(12, 0.01)), "CASH": np.zeros(252)})
    signal, _ = _signal(returns, [pd.Timestamp("2020-01-31")], refit_every=1)
    vols = signal.garch_volatility()
    assert np.isnan(vols["NEW"]) and np.isnan(vols["CASH"])

    var = vfs.VolatilityForecastingSignals._filter(np.full(10, 1.0), 0.0, 0.1, 0.1, 0.9)   # alpha + beta = 1
    assert np.isfinite(var) and var > 0


def test_boundary_fits_fall_back_to_sample_variance():
    """Fits seen on real 252-day windows: GLD 2013 (omega=0) collapsed vol to ~0, TIP 2011
    (alpha + beta = 1) exploded it. Both must fall back to the window's sample vol."""
    usable = vfs.VolatilityForecastingSignals._usable
    assert usable(0.02, 0.05, 0.08, 0.90)
    assert not usable(0.016, 0.0, 0.0, 0.9963)          # no baseline variance
    assert not usable(0.025, 5e-4, 0.0, 1.0)            # integrated
    assert not usable(0.0, np.nan, 0.1, 0.8)

    returns = pd.DataFrame({"GLD": _simulate_garch(252, seed=3)})
    signal, _ = _signal(returns, [pd.Timestamp("2020-01-31")], refit_every=12)
    signal._params["GLD"] = (0.016, 0.0, 0.0, 0.9963)
    signal._last_fit["GLD"] = pd.Timestamp("2020-01-31")
    sample_vol = (returns["GLD"] * 100).to_numpy().var() ** 0.5 / 100 * np.sqrt(ANN)
    np.testing.assert_allclose(signal.garch_volatility()["GLD"], sample_vol)
