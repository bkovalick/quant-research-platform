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
        self.refit_every = self.inverse_vol_cfg.refit_every if self.inverse_vol_cfg is not None else 12
        self._params = {}
        self._last_fit = {}

    def rolling_realized_vol(self, window = 20) -> pd.Series:
        p = self.market_state.lookback_returns()
        return p.rolling(window).std().iloc[-1] * np.sqrt(self.ann_factor)

    def ewma_volatility(self, span: int = 20) -> pd.Series:
        """Annualized exponentially weighted std of returns (not prices)."""
        r = self.market_state.lookback_returns()
        return r.ewm(span=span, adjust=False).std().iloc[-1] * np.sqrt(self.ann_factor)

    def garch_volatility(self) -> pd.Series:
        """Annualized one-step GARCH(1,1) conditional vol per asset."""
        r = self.market_state.lookback_returns()
        today = self.market_state.current_date()
        vols = {}
        for asset in r.columns:
            series = r[asset].dropna() * 100.0
            if len(series) < 30 or series.std() == 0:
                vols[asset] = np.nan
                continue
            if self._needs_refit(asset, today):
                self._fit(asset, series, today)
            if asset not in self._params:
                vols[asset] = np.nan
                continue
            vols[asset] = self._filter(series.to_numpy(), *self._params[asset])
        
        return pd.Series(vols)

    def _needs_refit(self, asset: str, today: pd.Timestamp) -> bool:
        """Determine if the GARCH model for the asset needs refitting based on the refit frequency."""
        if asset not in self._params:
            return True
        last_fit = self._last_fit.get(asset, None)
        return last_fit is None or today >= last_fit + pd.Timedelta(days=self.refit_every)

    def _fit(self, asset: str, series: pd.Series, today: pd.Timestamp) -> None:
        "Fit the GARCH(1,1) model for the given asset and series, and store the parameters."
        try:
            res = arch_model(series, vol="Garch", p=1, q=1, rescale=False).fit(disp="off")
            p = res.params
            self._params[asset] = (p["mu"], p["omega"], p["alpha[1]"], p["beta[1]"])
        except Exception:
            pass

        self._last_fit[asset] = today

    @staticmethod
    def _filter(returns: np.ndarray, mu: float, omega: float, alpha: float, beta: float, ann_factor: float) -> float:
        "Filter the series using the GARCH(1,1) parameters and return the annualized one-step-ahead volatility."
        if len(returns) == 0:
            return np.nan

        eps = returns - mu
        persistence = alpha + beta
        var = omega / (1 - persistence) if persistence < 1 else eps.var()
        for e in eps:
            var = omega + alpha * e * e + beta * var
        return var
