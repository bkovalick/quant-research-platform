import numpy as np
import pandas as pd
from models.signals_config import SignalsConfig
from simulation.market_state import MarketState

from arch import arch_model

class Signals:
    def __init__(self, market_state: MarketState, signals_cfg: SignalsConfig):
        self.market_state = market_state
        self.ann_factor = market_state.annual_trading_days
        self.signals_cfg = signals_cfg
        self.apply_winsorizing = signals_cfg.apply_winsorizing
        self.windsor_percentiles = signals_cfg.windsor_percentiles
           
    def lookback_returns(self) -> pd.DataFrame:
        r = self.market_state.lookback_returns()
        if not self.apply_winsorizing:
            return r

        lower_bound = r.quantile(self.windsor_percentiles["lower"])
        upper_bound = r.quantile(self.windsor_percentiles["upper"])
        return r.clip(lower=lower_bound, upper=upper_bound, axis = 1) 

    def mean_returns(self) -> np.ndarray:
        lookback_returns = self.lookback_returns()
        return lookback_returns.mean().values * self.ann_factor

    def covariance_matrix(self) -> np.ndarray:
        lookback_returns = self.lookback_returns()
        r = lookback_returns.values
        cov = np.cov(r, rowvar=False) * self.ann_factor
        cov = 0.5 * (cov + cov.T)
        return cov
    
    def portfolio_vol(self, curr_weights: np.ndarray) -> float:
        cov = self.covariance_matrix()
        return np.sqrt(curr_weights.T @ cov @ curr_weights)
    
    def rolling_realized_vol(self, window: int = 20) -> float:
        lookback_returns = self.lookback_returns()
        vol = lookback_returns.rolling(window).std().iloc[-1]
        return vol.values * np.sqrt(self.ann_factor)

    def momentum_signal(self) -> np.ndarray:
        p = self.market_state.lookback_prices()
        return (p.iloc[-1] / p.iloc[0] - 1).values

class MovingAverageSignals(Signals):
    def __init__(self, 
                 market_state: MarketState, 
                 signals_cfg: SignalsConfig):
        super().__init__(market_state, signals_cfg)

    def simple_moving_average(self, window: int) -> float:
        p = self.market_state.lookback_prices()
        return p.rolling(window).mean()

    def exponential_weighted_moving_average(self, span: int = 20) -> pd.DataFrame:
        p = self.market_state.lookback_prices()
        return p.ewm(span=span, adjust=False).mean()

    def bollinger_weighted_moving_average(self, window: int = 20, num_std: float = 2.0) -> dict:
        p = self.market_state.lookback_prices()
        sma = p.rolling(window).mean()
        rolling_std = p.rolling(window).std()
        upper_band = sma + num_std * rolling_std
        lower_band = sma - num_std * rolling_std
        return { 'middle': sma, 'upper': upper_band, 'lower': lower_band }

class VolatilityForecastingSignals(Signals):
    def __init__(self, 
                 market_state: MarketState, 
                 signals_cfg: SignalsConfig):
        super().__init__(market_state, signals_cfg)

    def rolling_realized_vol(self, window = 20):
        p = self.market_state.lookback_returns()
        return p.rolling(window).std().iloc[-1] * np.sqrt(self.ann_factor)

    def ewma_volatility(self, span: int = 20) -> pd.DataFrame:
        p = self.market_state.lookback_prices()
        return p.ewm(span=span, adjust=False).std().iloc[-1] * np.sqrt(self.ann_factor)

    def garch_volatility(self) -> pd.Series:
        p = self.market_state.lookback_returns()
        vols = []
        for col in p.columns:
            am = arch_model(p[col].dropna(), vol='Garch', p=1, q=1)
            res = am.fit(disp='off')
            vols.append(res.conditional_volatility[-1] * np.sqrt(self.ann_factor))
        return pd.Series(vols, index=p.columns)