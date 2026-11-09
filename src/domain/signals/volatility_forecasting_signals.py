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
        self.inverse_vol_cfg = self.signals_cfg.inverse_vol
        if self.inverse_vol_cfg is None:
            self.refit_every = "12M"

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
        variation in the window (CASH), fewer than 30 observations (just listed) or a
        failed fit get NaN.
        """
        r = self.market_state.lookback_returns()
        cursor = self.market_state.cursor
        vols, params, last_fit = {}, {}, {}
        for asset in r.columns:
            series = r[asset].dropna() * 100.0
            if len(series) < 30 or series.std() == 0:
                vols[asset] = np.nan
                continue

            if asset not in last_fit or (cursor - last_fit.get(asset, pd.Timestamp.min)) >= self.refit_every:
                try:
                    res = arch_model(series, vol="Garch", p=1, q=1, rescale=False).fit(disp="off")
                    vols[asset] = res.conditional_volatility.iloc[-1] / 100.0 * np.sqrt(self.ann_factor)
                    params[asset] = (res.params["mu"], res.params["omega"], res.params["alpha[1]"], res.params["beta[1]"])
                    last_fit[asset] = cursor
                except Exception:
                    vols[asset] = np.nan

            mu, omega, alpha, beta = params[asset]
            eps = r * 100.0 - mu
            for e in eps:
                var = omega + alpha * e**2 + beta * (var if 'var' in locals() else series.var())
            vols[asset] = np.sqrt(var) / 100.0 * np.sqrt(self.ann_factor)
        
        return pd.Series(vols)
