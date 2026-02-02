import numpy as np
import pandas as pd

class Signals:
    def __init__(self, market_env, ann_factor: int = 252):
        self.market_env = market_env
        self.ann_factor = ann_factor

    @property
    def returns(self) -> pd.DataFrame:
        return self.market_env.normalized_prices.pct_change().iloc[1:]
    
    @property
    def mean_returns(self) -> np.ndarray:
        return np.array(self.returns.mean()) * self.ann_factor

    @property
    def covariance_matrix(self) -> np.ndarray:
        cov = np.cov(self.returns, rowvar=False) * self.ann_factor
        return cov
    
    def momentum_signal(self, lookback: int = 20) -> np.ndarray:
        return (self.normalized_prices.iloc[-1] / self.normalized_prices.iloc[-lookback] - 1).values
