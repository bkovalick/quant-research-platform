import numpy as np
import pandas as pd

class Signals:
    def __init__(self, market_env, ann_factor: int = 252):
        self.market_env = market_env
        self.ann_factor = ann_factor

    @property
    def returns(self) -> pd.DataFrame:
        return self.market_env.normalized_prices.pct_change().iloc[1:]

    # @property
    # def cleaned_returns(self) -> pd.DataFrame:
    #     returns = self.returns.replace([np.inf, -np.inf], np.nan)
    #     return returns.fillna(0.0)
    
    @property
    def mean_returns(self) -> np.ndarray:
        return np.array(self.returns.mean()) * self.ann_factor

    @property
    def covariance_matrix(self) -> np.ndarray:
        cov = np.cov(self.returns, rowvar=False) * self.ann_factor
        # diag_mean = np.nanmean(np.diag(cov)) if cov.size else 0.0
        # scale = diag_mean if np.isfinite(diag_mean) and diag_mean > 0 else 1.0
        # eps = 1e-6 * scale
        # cov = cov + np.eye(cov.shape[0]) * eps
        return cov
    
    def momentum_signal(self, lookback: int = 20) -> np.ndarray:
        return (self.normalized_prices.iloc[-1] / self.normalized_prices.iloc[-lookback] - 1).values
