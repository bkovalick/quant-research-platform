import pandas as pd
import numpy as np
from scipy.stats import rankdata

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
        self.scaler = StandardScaler() if self.model_type == "ridge" else None
        self.model = None

    def fit(self, X: pd.DataFrame | np.ndarray, y: pd.Series | np.ndarray) -> None:
        """Fit on row-aligned arrays, or on a DataFrame/Series pair (aligned here on their index).
        Rows with a missing or infinite label or feature are dropped."""
        if isinstance(X, pd.DataFrame):
            common = X.index.intersection(y.index)
            X, y = X.loc[common], y.loc[common]
        X_arr, y_arr = np.asarray(X), np.asarray(y)

        valid = np.isfinite(y_arr) & np.isfinite(X_arr).all(axis=1)
        if not valid.any():
            raise ValueError("No training rows with complete features and labels")
        X_arr, y_arr = X_arr[valid], y_arr[valid]
        if self.scaler is not None:
            X_arr = self.scaler.fit_transform(X_arr)

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

        X_arr = X.to_numpy(dtype=float)
        X_scaled = self.scaler.transform(X_arr) if self.scaler is not None else X_arr
        raw_scores = self.model.predict(X_scaled)
        ranked = rankdata(raw_scores, method='average', nan_policy='omit') / np.isfinite(raw_scores).sum()
        return ranked