import numpy as np
from models.signals_config import SignalsConfig
from simulation.market_state import MarketState
from sklearn.covariance import LedoitWolf
from domain.signals.signals import Signals

class RiskReturnSignals(Signals):
    def __init__(self, market_state: MarketState, signals_cfg: SignalsConfig):
        super().__init__(market_state, signals_cfg)

    def mean_returns(self) -> np.ndarray:
        lookback_returns = self.lookback_returns()
        return lookback_returns.mean().values * self.ann_factor

    def covariance_matrix(self) -> np.ndarray:
        lookback_returns = self.lookback_returns()
        lw = LedoitWolf()
        lw.fit(lookback_returns.values)
        cov = lw.covariance_ * self.ann_factor
        return 0.5 * (cov + cov.T)
    
    def portfolio_vol(self, curr_weights: np.ndarray) -> float:
        cov = self.covariance_matrix()
        return np.sqrt(curr_weights.T @ cov @ curr_weights)