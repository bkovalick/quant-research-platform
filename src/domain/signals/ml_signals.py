from domain.signals.risk_return_signals import RiskReturnSignals
from domain.machine_learning.isignal_model import ISignalModel
from domain.machine_learning.feature_builder import FeatureBuilder
from models.signals_config import SignalsConfig
from models.machine_learning_config import MachineLearningConfig
from simulation.market_state import MarketState

import pandas as pd
import numpy as np

class MLSignalsSate:
    """Long-lived. Owns model training lifecycle."""
    def __init__(self, feature_builder, model, rebal_cadence):
        self._feature_builder = feature_builder
        self._model = model
        self._cadence = rebal_cadence
        self._cached_scores = None
        self._last_trained = None

    def update(self, as_of_date):
        if self._should_retrain(as_of_date):
            X, y = self._feature_builder.build_training_data(as_of_date)
            self._model.fit(X, y)
            X_now = self._feature_builder.build(as_of_date)
            self._cached_scores = self._model.predict(X_now)
            self._last_trained = as_of_date

    @property
    def scores(self):
        return self._cached_scores
        
class MLSignals(RiskReturnSignals):
    def __init__(self, 
                 market_state: MarketState, 
                 signals_cfg: SignalsConfig,
                 ml_config: MachineLearningConfig,
                 feature_builder: FeatureBuilder,
                 model: ISignalModel):
        super().__init__(market_state, signals_cfg)

        self.ml_config = ml_config
        self.feature_builder = feature_builder
        self.model = model
        self.training_window = ml_config.training_window
        self.horizon = ml_config.horizon

    def mean_returns(self) -> np.ndarray:
        enabled = getattr(self.ml_config, "enabled", False)
        if not enabled:
            return super().mean_returns()

        dates = self.market_state.prices.index
        train_dates = dates[-(self.training_window + self.horizon):-self.horizon]

        X_list, y_list = [], []
        for date in train_dates[::5]:   # sample every 5 days for efficiency
            X_t = self.feature_builder.build(date)
            y_t = self.feature_builder.build_forward_returns(
                      date, self.horizon)
            if X_t.empty or y_t.empty:
                continue
            X_list.append(X_t)
            y_list.append(y_t)

        if not X_list:
            raise ValueError("Could not build training data.")

        # The model learns the relationship betwen the features and future returns
        X_train = pd.concat(X_list) # cross-sectional features (mom, vol, reversal)
        y_train = pd.concat(y_list) # corresponding forward returns over horizon days

        self.model.fit(X_train, y_train)
        X_now = self.feature_builder.build()
        scores = self.model.predict(X_now) # applies the trained model to today's features to produce a predicted return score for each asset.

        # return pd.Series(scores, index=X_now.index, name="predicted_return")
        return np.array(scores)
