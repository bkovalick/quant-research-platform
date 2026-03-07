import numpy as np
import pandas as pd
from arch import arch_model
from models.signals_config import SignalsConfig
from simulation.market_state import MarketState

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