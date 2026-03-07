import numpy as np
import pandas as pd
from models.signals_config import SignalsConfig
from simulation.market_state import MarketState

from arch import arch_model
from abc import ABC, abstractmethod
from scipy.stats import rankdata
from sklearn.covariance import LedoitWolf

class Signals(ABC):
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

    @abstractmethod
    def mean_returns(self) -> np.ndarray: ...

    @abstractmethod
    def covariance_matrix(self) -> np.ndarray: ...

    @abstractmethod
    def portfolio_vol(self, weights: np.ndarray) -> float: ...    

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

class MomentumSignals(RiskReturnSignals):
    def __init__(self, 
                market_state: MarketState, 
                signals_cfg: SignalsConfig):
        super().__init__(market_state, signals_cfg)

    def mean_returns(self) -> np.ndarray:
        p = self.market_state.lookback_prices()
        skip = getattr(self.signals_cfg, "momentum_skip_periods", 4)
        total_return = (p.iloc[-(skip + 1)] / p.iloc[0] - 1).values
        annualized = total_return * (self.ann_factor / (len(p) - skip))
        return annualized
        
class MeanReversionSignals(RiskReturnSignals):
    def __init__(self, 
                 market_state: MarketState, 
                 signals_cfg: SignalsConfig):
        super().__init__(market_state, signals_cfg)

    def mean_returns(self) -> np.ndarray:
        mean_reversion_window = getattr(self.signals_cfg, "mean_reversion_window", None)
        if mean_reversion_window is None:
            return super().mean_returns()        
        
        lookback_prices = self.market_state.lookback_prices()
        short_returns = lookback_prices.pct_change(mean_reversion_window).iloc[-1]
        if self.apply_winsorizing:
            lower_bound = short_returns.quantile(self.windsor_percentiles["lower"])
            upper_bound = short_returns.quantile(self.windsor_percentiles["upper"])
            short_returns = short_returns.clip(lower=lower_bound, upper=upper_bound)
            
        ranked = rankdata(-short_returns.values) / len(short_returns) - 0.5
        return ranked
        
class MovingAverageSignals:
    def __init__(self, 
                 market_state: MarketState, 
                 signals_cfg: SignalsConfig):
        self.market_state = market_state
        self.ann_factor = market_state.annual_trading_days
        self.signals_cfg = signals_cfg
        self.apply_winsorizing = signals_cfg.apply_winsorizing
        self.windsor_percentiles = signals_cfg.windsor_percentiles

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

class VolatilityForecastingSignals:
    def __init__(self, 
                 market_state: MarketState, 
                 signals_cfg: SignalsConfig):
        self.market_state = market_state
        self.ann_factor = market_state.annual_trading_days
        self.signals_cfg = signals_cfg
        self.apply_winsorizing = signals_cfg.apply_winsorizing
        self.windsor_percentiles = signals_cfg.windsor_percentiles

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