import numpy as np
import pandas as pd

from domain.signals.machine_learning_signals import MLPredictorSignal, MLPredictorSignalsState
from models.machine_learning_config import MachineLearningConfig
from models.signals_config import SignalsConfig


class DummyMarketState:
    annual_trading_days = 252
    investment_universe = ["A", "B", "C", "D"]

    def lookback_returns(self):
        return pd.DataFrame(
            {
                "A": [0.01, 0.02],
                "B": [0.02, -0.01],
                "C": [0.03, 0.04],
                "D": [-0.01, 0.01],
            },
            index=[pd.Timestamp("2024-01-01"), pd.Timestamp("2024-01-02")],
        )


def test_ml_signal_uses_fallback_for_missing_scores():
    feature_builder = type(
        "FeatureBuilderStub",
        (),
        {"prices": pd.DataFrame(columns=["A", "B", "C", "D"])},
    )()

    ml_config = MachineLearningConfig(
        enabled=True,
        features_model="cross_sectional_model",
        features=["feature_1"],
        signals_model="ridge",
        training_window=2,
        horizon=1,
        alpha=1.0,
        rebal_cadence=1,
        sample_stride=1,
        n_estimators=10,
        max_depth=3,
        learning_rate=0.05,
    )

    predictor_state = MLPredictorSignalsState(
        ml_config=ml_config,
        feature_builder=feature_builder,
        model=type("ModelStub", (), {"fit": lambda self, X, y: None, "predict": lambda self, X: np.array([0.1, 0.2, 0.3])})(),
    )
    predictor_state.cached_scores = pd.Series([0.10, np.nan, 0.30], index=["A", "B", "C"])

    signals_config = SignalsConfig(
        apply_winsorizing=False,
        windsor_percentiles={"lower": 0.05, "upper": 0.95},
        mean_reversion_window=2,
        momentum_skip_periods=2,
        black_litterman=None,
        ml_signals_config=None,
        pairs_trading=None,
    )

    signal = MLPredictorSignal(
        market_state=DummyMarketState(),
        signals_cfg=signals_config,
        ml_config=ml_config,
        predictor_state=predictor_state,
    )

    result = signal.mean_returns()

    assert result.shape == (4,)
    assert not np.isnan(result).any()
    np.testing.assert_allclose(result, np.array([0.10, 1.26, 0.30, 0.0]), atol=1e-9)
