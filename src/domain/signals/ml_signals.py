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
        self.ml_config = ml_config
        self.feature_builder = feature_builder
        self.model = model
        self.cadence = ml_config.rebal_cadence
        self.cached_scores = None
        self.last_trained = None
        self.training_window = ml_config.training_window
        self.horizon = ml_config.horizon
        self.sample_stride = ml_config.sample_stride

    def update(self, cursor: int, as_of_date: datetime):
        """
        Retrains the model on a rolling window of historical features and forward returns,
        then generates and caches predicted scores for the current date. Retraining is
        skipped if the configured cadence has not elapsed since the last training run.
        """
        if not self._should_retrain(cursor):
            return 
        
        train_end = cursor - self.horizon
        train_start = train_end - self.training_window
        if train_start < 0 or train_end <= 0:
            # Not enough history yet, leave scores as None
            # Strategy will fall back to non-ML signals            
            return

        dates = self.feature_builder.prices.index
        train_dates = dates[train_start:train_end:self.sample_stride]

        X_list, y_list = [], []
        for date in train_dates:
            X_t = self.feature_builder.build(date)
            y_t = self.feature_builder.build_forward_returns(date, self.horizon)
            if X_t.empty or y_t.empty:
                continue
            X_list.append(X_t)
            y_list.append(y_t)

        if not X_list:
            return

        X_train = pd.concat(X_list)
        y_train = pd.concat(y_list)

        self.model.fit(X_train, y_train)
        X_now = self.feature_builder.build(as_of_date)
        if X_now.empty:
            return

        scores = self.model.predict(X_now)
        self.cached_scores = pd.Series(scores, index=X_now.index)
        self.last_trained = cursor

    def _should_retrain(self, cursor: int) -> bool:
        if self.last_trained is None:
            return True
        return (cursor - self.last_trained) >= self.cadence
    
    @property
    def scores(self):
        if self.cached_scores is None:
            return None
        # Reindex to full universe, NaN for any assets dropped by dropna()
        all_tickers = self.feature_builder.prices.columns
        return self.cached_scores.reindex(all_tickers)

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
        if self.state.scores is None:
            return super().mean_returns()
        return self.state.scores