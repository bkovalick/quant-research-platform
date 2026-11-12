from typing import Any, Dict
import numpy as np
import pandas as pd
import logging
from abc import ABC, abstractmethod

from models.signals_config import SignalsConfig
from simulation.market_state import MarketState

class Signals(ABC):
    def __init__(self, 
                 market_state: MarketState, 
                 signals_config: SignalsConfig):
        self.logger = logging.getLogger(__name__)
        self.market_state = market_state
        self.ann_factor = market_state.annual_trading_days
        self.signals_config = signals_config
        self.apply_winsorizing = signals_config.apply_winsorizing
        self.windsor_percentiles = signals_config.windsor_percentiles
        self._returns_cursor = None
        self._returns = None

    def lookback_returns(self) -> pd.DataFrame:
        """ Returns the lookback returns for the investment universe, applying caching. """
        if self._returns_cursor != self.market_state.cursor:
            self._returns_cursor = self.market_state.cursor
            self._returns = self._compute_lookback_returns()
        return self._returns

    def _compute_lookback_returns(self) -> pd.DataFrame:
        """ Computes the lookback returns, applying winsorization if configured. """
        r = self.market_state.lookback_returns()
        if not self.apply_winsorizing:
            return r

        lower_bound = r.quantile(self.windsor_percentiles["lower"])
        upper_bound = r.quantile(self.windsor_percentiles["upper"])
        return r.clip(lower=lower_bound, upper=upper_bound, axis = 1)
    
    def lookback_prices(self) -> pd.DataFrame:
        """ Returns the lookback prices for the investment universe. """
        return self.market_state.lookback_prices()
    
    def update(self, cursor: int, as_of_date: pd.Timestamp) -> None:
        """Per-step heartbeat. Stateless signals inherit doing nothing."""
        pass

    def get_diagnostics(self) -> Dict[str, Any]:
        """Measurement artifacts accumulated during the run."""
        return {}

    @property
    def beta_vector(self):
        """Compute the beta vector of assets relative to the market."""
        asset_returns = getattr(self.market_state, "investment_returns", None)
        market_returns = getattr(self.market_state, "market_returns", None)
        if asset_returns is None or market_returns is None:
            return None

        aligned_returns = pd.concat(
            [market_returns.rename("market"), asset_returns],
            axis=1,
            join="inner",
        ).iloc[: self.market_state.cursor + 1]
        if len(aligned_returns) < 2:
            return None

        market = aligned_returns["market"].to_numpy(dtype=float)
        assets = aligned_returns.drop(columns="market").to_numpy(dtype=float)
        valid = np.isfinite(assets) & np.isfinite(market)[:, None]
        counts = valid.sum(axis=0)

        m = np.where(valid, market[:, None], 0.0)
        a = np.where(valid, assets, 0.0)
        with np.errstate(invalid="ignore", divide="ignore"):
            m_mean = m.sum(axis=0) / counts
            a_mean = a.sum(axis=0) / counts
            m_dev = np.where(valid, market[:, None] - m_mean, 0.0)
            a_dev = np.where(valid, assets - a_mean, 0.0)
            covariance = (m_dev * a_dev).sum(axis=0)
            market_variance = (m_dev ** 2).sum(axis=0)
            beta = covariance / market_variance

        enough = (counts >= 2) & (market_variance > 1e-18)
        return np.where(enough, beta, np.nan)

    @abstractmethod
    def mean_returns(self) -> np.ndarray: ...

    @abstractmethod
    def covariance_matrix(self) -> np.ndarray: ...

    @abstractmethod
    def portfolio_vol(self, weights: np.ndarray) -> float: ...