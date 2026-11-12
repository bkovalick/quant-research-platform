import pandas as pd
import numpy as np

from domain.machine_learning.return_predictor import ReturnPredictor
from models.machine_learning_config import MachineLearningConfig
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler

class CrossSectionalModel(ReturnPredictor):
    def __init__(self, 
                 config: MachineLearningConfig):
        super().__init__()

        self.config = config
        self.model_type = config.signals_model
        self.alpha = config.alpha
        self.n_estimators = config.n_estimators
        self.max_depth = config.max_depth
        self.learning_rate = config.learning_rate
        self.scaler = StandardScaler()
        self.model = None

    def fit(self, X: pd.DataFrame, y: pd.Series) -> None:
        common = X.index.intersection(y.index)
        X, y = X.loc[common], y.loc[common].replace([np.inf, -np.inf], np.nan)
        # A missing label (no forward price) or feature is not information; drop the row.
        valid = y.notna() & X.replace([np.inf, -np.inf], np.nan).notna().all(axis=1)
        if not valid.any():
            raise ValueError("No training rows with complete features and labels")
        X_arr = self.scaler.fit_transform(X.loc[valid])
        y_arr = y.loc[valid].values

        if self.model_type == "ridge":
            self.model = Ridge(alpha=self.alpha)
        elif self.model_type == "gradientboostingregressor":
            self.model = HistGradientBoostingRegressor(
                max_iter=self.n_estimators, max_depth=self.max_depth, learning_rate=self.learning_rate
            )
        self.model.fit(X_arr, y_arr)

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        if self.model is None:
            raise RuntimeError("Model must be fit before predicting.")
        X_scaled = self.scaler.transform(X)
        raw_scores = self.model.predict(X_scaled)
        ranked = pd.Series(raw_scores, index=X.index).rank(pct=True)
        return ranked.values