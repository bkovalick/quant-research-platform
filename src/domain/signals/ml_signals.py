from domain.signals.risk_return_signals import RiskReturnSignals
from domain.machine_learning.isignal_model import ISignalModel
from domain.machine_learning.feature_builder import FeatureBuilder
from models.signals_config import SignalsConfig
from models.machine_learning_config import MachineLearningConfig
from simulation.market_state import MarketState

import pandas as pd
import numpy as np
from datetime import datetime

class MLSignalsState:
    """Long-lived. Owns model training lifecycle."""
    def __init__(self, 
                 ml_config: MachineLearningConfig, 
                 feature_builder: FeatureBuilder, 
                 model: ISignalModel):
        self._ml_config = ml_config
        self._feature_builder = feature_builder
        self._model = model
        self._cadence = ml_config.rebal_cadence
        self._cached_scores = None
        self._last_trained = None
        self._training_window = ml_config.training_window
        self._horizon = ml_config.horizon        

    def update(self, as_of_date: datetime):
        if self._should_retrain(as_of_date):
            dates = self._feature_builder.prices.index
            train_dates = dates[-(self._training_window + self._horizon):-self._horizon]

            X_list, y_list = [], []
            for date in train_dates[::5]:
                X_t = self._feature_builder.build(date)
                y_t = self._feature_builder.build_forward_returns(
                        date, self._horizon)
                if X_t.empty or y_t.empty:
                    continue
                X_list.append(X_t)
                y_list.append(y_t)

            if not X_list:
                raise ValueError("Could not build training data.")

            X_train = pd.concat(X_list)
            y_train = pd.concat(y_list)

            self._model.fit(X_train, y_train)
            X_now = self._feature_builder.build(as_of_date)
            scores = self._model.predict(X_now)
            self._cached_scores = np.array(scores)
            self._last_trained = as_of_date

    def _should_retrain(self, as_of_date: datetime) -> bool:
        if self._last_trained is None:
            return True
        return (as_of_date - self._last_trained).days >= self._cadence
    
    @property
    def scores(self):
        return self._cached_scores

class MLSignals(RiskReturnSignals):
    def __init__(self, 
                 market_state: MarketState, 
                 signals_cfg: SignalsConfig,
                 ml_config: MachineLearningConfig,
                 state: MLSignalsState):
        super().__init__(market_state, signals_cfg)

        self.ml_config = ml_config
        self.state = state

    def mean_returns(self):
        if not self.ml_config.enabled:
            return super().mean_returns()
        
        return self.state.scores