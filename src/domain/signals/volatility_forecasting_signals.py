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

    def rolling_realized_vol(self, window = 20) -> pd.Series:
        p = self.market_state.lookback_returns()
        return p.rolling(window).std().iloc[-1] * np.sqrt(self.ann_factor)

    def ewma_volatility(self, span: int = 20) -> pd.Series:
        """Annualized exponentially weighted std of returns (not prices)."""
        r = self.market_state.lookback_returns()
        return r.ewm(span=span, adjust=False).std().iloc[-1] * np.sqrt(self.ann_factor)

    def garch_volatility(self) -> pd.Series:
        """
        Annualized one-step GARCH(1,1) conditional vol per asset. Returns are fitted
        in percent (arch converges poorly on decimal returns). Assets with no
        variation in the window (CASH, or prices backfilled before listing) or a
        failed fit get NaN.
        """
        r = self.market_state.lookback_returns()
        vols = {}
        for col in r.columns:
            series = r[col].dropna() * 100.0
            if len(series) < 30 or series.std() == 0:
                vols[col] = np.nan
                continue
            try:
                res = arch_model(series, vol="Garch", p=1, q=1, rescale=False).fit(disp="off")
                vols[col] = res.conditional_volatility.iloc[-1] / 100.0 * np.sqrt(self.ann_factor)
            except Exception:
                vols[col] = np.nan
        return pd.Series(vols)
