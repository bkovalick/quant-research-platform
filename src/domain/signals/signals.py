import numpy as np
from models.signals_config import SignalsConfig
from simulation.market_state import MarketState

class Signals:
    def __init__(self, market_state: MarketState, signals_cfg: SignalsConfig):
        self.market_state = market_state
        self.ann_factor = market_state.lookback_window
        self.signals_cfg = signals_cfg
        self.apply_winsorizing = signals_cfg.apply_winsorizing
        self.windsor_percentiles = signals_cfg.windsor_percentiles

    @property
    def lookback_prices(self):
        if not self.apply_winsorizing:
            return self.market_state.lookback_prices
        
        lower_bound = self.market_state.lookback_prices.quantile(self.windsor_percentiles["lower"])
        upper_bound = self.market_state.lookback_prices.quantile(self.windsor_percentiles["upper"])
        return self.market_state.lookback_prices.clip(lower=lower_bound, upper=upper_bound, axis = 1)        

    @property
    def lookback_returns(self):
        return self.lookback_prices.pct_change().dropna()

    def mean_returns(self) -> np.ndarray:
        return self.lookback_returns.mean().values * self.ann_factor

    def covariance_matrix(self) -> np.ndarray:
        r = self.lookback_returns.values
        cov = np.cov(r, rowvar=False) * self.ann_factor
        cov = 0.5 * (cov + cov.T)
        return cov

    def rolling_realized_vol(self, window: int = 20) -> float:
        vol = self.lookback_returns.rolling(window).std().iloc[-1]
        return vol.values * np.sqrt(self.ann_factor)

    def portfolio_vol(self, curr_weights: np.ndarray) -> float:
        cov = self.covariance_matrix
        return np.sqrt(curr_weights.T @ cov @ curr_weights)

    def momentum_signal(self) -> np.ndarray:
        p = self.lookback_prices
        return (p.iloc[-1] / p.iloc[0] - 1).values
