from typing import Any, Dict

import numpy as np
import pandas as pd
import logging
from abc import ABC, abstractmethod

from models.signals_config import SignalsConfig
from simulation.market_state import MarketState

import numpy as np

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

    def lookback_returns(self) -> pd.DataFrame:
        r = self.market_state.lookback_returns()
        if not self.apply_winsorizing:
            return r

        lower_bound = r.quantile(self.windsor_percentiles["lower"])
        upper_bound = r.quantile(self.windsor_percentiles["upper"])
        return r.clip(lower=lower_bound, upper=upper_bound, axis = 1)
    
    def lookback_prices(self) -> pd.DataFrame:
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

        aligned_values = aligned_returns.to_numpy(dtype=float)
        covariance = np.cov(aligned_values, rowvar=False, ddof=1)
        market_variance = covariance[0, 0]
        if np.isclose(market_variance, 0):
            return np.zeros(asset_returns.shape[1], dtype=float)

        beta = covariance[1:, 0] / market_variance
        return beta

    @abstractmethod
    def mean_returns(self) -> np.ndarray: ...

    @abstractmethod
    def covariance_matrix(self) -> np.ndarray: ...

    @abstractmethod
    def portfolio_vol(self, weights: np.ndarray) -> float: ...