import numpy as np
import pandas as pd

from domain.machine_learning.cross_sectional_model import CrossSectionalModel
from models.machine_learning_config import MachineLearningConfig


def test_fit_ignores_nan_in_y_and_x():
    config = MachineLearningConfig(
        enabled=True,
        features_model="cross_sectional_model",
        features=["f1", "f2"],
        signals_model="ridge",
        training_window=10,
        horizon=5,
        alpha=1.0,
        rebal_cadence=5,
        sample_stride=1,
        n_estimators=10,
        max_depth=3,
        learning_rate=0.05,
    )

    X = pd.DataFrame(
        {
            "f1": [1.0, 2.0, 3.0, 4.0],
            "f2": [0.0, 1.0, 2.0, 3.0],
        },
        index=["A", "B", "C", "D"],
    )
    y = pd.Series([0.10, np.nan, 0.20, 0.30], index=["A", "B", "C", "D"])

    model = CrossSectionalModel(config)
    model.fit(X, y)

    pred = model.predict(X)
    assert pred.shape == (4,)
    assert np.isfinite(pred).all()
