import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from reporting.performance_analyzer import PerformanceAnalyzer


def test_rolling_alpha_recovers_annualized_regression_intercept():
    annual_trading_days = 4
    risk_free_rate = 0.04
    rf_per_period = risk_free_rate / annual_trading_days
    benchmark_returns = pd.Series([0.01, -0.02, 0.03, 0.00, 0.02, -0.01])
    expected_alpha = 0.08
    beta = 1.5
    portfolio_returns = (
        rf_per_period
        + expected_alpha / annual_trading_days
        + beta * (benchmark_returns - rf_per_period)
    )
    analyzer = PerformanceAnalyzer()
    analyzer._annual_trading_days = annual_trading_days

    rolling_alpha = analyzer._calculate_rolling_alpha(
        portfolio_returns,
        benchmark_returns,
        risk_free_rate,
        window=4,
    )

    assert rolling_alpha.iloc[:3].isna().all()
    np.testing.assert_allclose(rolling_alpha.iloc[3:], expected_alpha)


def test_rolling_alpha_is_undefined_when_benchmark_has_no_variation():
    returns = pd.Series([0.01, 0.02, 0.03, 0.04])
    analyzer = PerformanceAnalyzer()
    analyzer._annual_trading_days = 4

    rolling_alpha = analyzer._calculate_rolling_alpha(
        returns,
        pd.Series([0.01, 0.01, 0.01, 0.01]),
        risk_free_rate=0.0,
        window=4,
    )

    assert rolling_alpha.isna().all()
