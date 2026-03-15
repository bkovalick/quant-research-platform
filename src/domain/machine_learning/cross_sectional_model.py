import pandas as pd
import numpy as np
from domain.machine_learning.isignal_model import ISignalModel
from models.machine_learning_config import MachineLearningConfig
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler

class CrossSectionalModel(ISignalModel):
    def __init__(self, 
                 config: MachineLearningConfig):
        super().__init__()

        self.config = config
        self.model_type = config.signals_model
        self.alpha = config.alpha
        self.scaler = StandardScaler()
        self._model = None

    def fit(self, X: pd.DataFrame, y: pd.Series) -> None:
        common = X.index.intersection(y.index)
        X_arr = self.scaler.fit_transform(X.loc[common])
        y_arr = y.loc[common].values

        if self.model_type == "ridge":
            self._model = Ridge(alpha=self.alpha)
        else:
            self._model = GradientBoostingRegressor(
                n_estimators=100, max_depth=3, learning_rate=0.05 # add as params
            )
        self._model.fit(X_arr, y_arr)

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        if self._model is None:
            raise RuntimeError("Model must be fit before predicting.")
        X_scaled = self.scaler.transform(X)
        raw_scores = self._model.predict(X_scaled)

        # Rank-normalize predictions → uniform [0,1] cross-sectionally
        # This converts raw predicted returns into relative scores,
        # which is what the optimizer actually needs.
        ranked = pd.Series(raw_scores, index=X.index).rank(pct=True)
        return ranked.values        