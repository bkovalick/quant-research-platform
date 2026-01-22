import numpy as np
import pandas as pd

class Signals:
    def __init__(self, market_env):
        self.market_env = market_env

    @property
    def returns(self) -> pd.DataFrame:
        return self.market_env.normalized_prices.pct_change().iloc[1:]
    
    @property
    def mean_returns(self) -> np.ndarray:
        return np.array(self.returns.mean())

    @property
    def covariance_matrix(self) -> np.ndarray:
        return np.cov(self.returns, rowvar=False)

    def momentum_signal(self, lookback: int = 20) -> np.ndarray:
        return (self.normalized_prices.iloc[-1] / self.normalized_prices.iloc[-lookback] - 1).values
