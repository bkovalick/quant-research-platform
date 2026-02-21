import numpy as np
import pandas as pd

class Signals:
    def __init__(self, market_state, ann_factor: int = 252):
        self.market_state = market_state
        self.ann_factor = market_state.annual_trading_days

    @property
    def mean_returns(self) -> np.ndarray:
        return self.market_state.lookback_returns().mean().values * self.ann_factor

    @property
    def covariance_matrix(self) -> np.ndarray:
        r = self.market_state.lookback_returns().iloc[1:].values
        cov = np.cov(r, rowvar=False) * self.ann_factor
        cov = 0.5 * (cov + cov.T)
        return cov
    
    @property
    def rolling_realized_vol(self, window: int = 20) -> float:
        vol = self.market_state.lookback_returns().rolling(window).std().iloc[-1]
        return vol.values * np.sqrt(self.ann_factor)

    @property
    def portfolio_vol(self, curr_weights: np.ndarray) -> float:
        cov = self.covariance_matrix
        return np.sqrt(curr_weights.T @ cov @ curr_weights)

    @property
    def momentum_signal(self) -> np.ndarray:
        p = self.market_state.lookback_prices()
        return (p.iloc[-1] / p.iloc[0] - 1).values
