from typing import Optional
import numpy as np
import pandas as pd

from models.vix_basis_config import VixBasisConfig
from simulation.market_state import MarketState

class VixBasisSignal:
    """
    Stateless point-in-time VIX term-structure ratio (front_index / back_index).
    Position state (hysteresis) is owned by VixBasisStrategy.
    """
    def __init__(self,
                 market_state: MarketState,
                 vix_basis_config: VixBasisConfig):
        self.config = vix_basis_config
        exogenous = market_state.exogenous_universe
        missing = [t for t in (self.config.front_index, self.config.back_index)
                   if t not in exogenous.columns]
        if missing:
            raise ValueError(
                f"VixBasisSignal needs {missing} in market_state_config.exogenous_tickers "
                f"and market_store_config.tickers"
            )
        front = exogenous[self.config.front_index]
        back = exogenous[self.config.back_index]
        self._ratio = (front / back).replace([np.inf, -np.inf], np.nan).dropna()
        self._as_of: Optional[pd.Timestamp] = None

    def update(self, cursor: int, as_of_date: pd.Timestamp) -> None:
        self._as_of = as_of_date

    def generate_signal(self) -> Optional[float]:
        """Latest ratio known as of the current date, or None if none is available."""
        if self._as_of is None:
            return None

        if self.config.use_prior_close:
            history = self._ratio[self._ratio.index < self._as_of]
        else:
            history = self._ratio[self._ratio.index <= self._as_of]
        return float(history.iloc[-1]) if not history.empty else None
