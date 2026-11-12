import logging
from typing import Optional

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

class Portfolio:
    """Portfolio class that houses weights, returns, and turnover calculations."""
    def __init__(self, financing_rate: float = 0.0, periods_per_year: int = 252):
        self.dates = None
        self.tickers = None
        self.weights = None
        self.returns = None
        self.turnover = None
        self.financing = None
        self.financing_rate = financing_rate
        self.periods_per_year = periods_per_year

    def initialize(self, dates: pd.DatetimeIndex, tickers: np.ndarray, initial_weights: np.ndarray):
        """Initialize portfolio with rebalance problem and price data."""
        if len(initial_weights) == 0:
            raise ValueError("price_data is empty—cannot initialize portfolio weights.")
  
        self.dates = pd.DatetimeIndex(dates)
        self.tickers = pd.Index(tickers)
        self.weights = np.zeros((len(dates), len(tickers)), dtype=float)
        self.weights[0] = initial_weights
        self.returns = np.zeros(len(dates), dtype=float)
        self.turnover = np.zeros(len(dates), dtype=float)
        self.financing = np.zeros(len(dates), dtype=float)
    
    @property
    def returns_series(self) -> Optional[pd.Series]:
        """Portfolio returns indexed by date, or None if the portfolio is not initialized."""
        if self.returns is None:
            return None
        return pd.Series(self.returns, index=self.dates, dtype=float)

    @property
    def turnover_series(self) -> Optional[pd.Series]:
        """Portfolio turnover indexed by date, or None if the portfolio is not initialized."""
        if self.turnover is None:
            return None
        return pd.Series(self.turnover, index=self.dates, dtype=float)

    @property
    def weights_frame(self) -> Optional[pd.DataFrame]:
        """Portfolio weights as a (dates x tickers) frame, or None if the portfolio is not initialized."""
        if self.weights is None:
            return None
        return pd.DataFrame(self.weights, index=self.dates, columns=self.tickers)

    def weights_at(self, cursor: int) -> pd.Series:
        """Weights at `cursor`, labelled by ticker."""
        return pd.Series(self.weights[cursor], index=self.tickers, dtype=float)

    def apply(self, target_weights: np.ndarray, prev_weights: np.ndarray, cursor: int) -> None:
        """ Updates weights and turnover """
        turnover = np.sum(np.abs(target_weights - prev_weights)) / 2
        self.weights[cursor] = target_weights
        self.turnover[cursor] = turnover

    def drift(self, prev_weights: np.ndarray, asset_returns: np.ndarray, cursor: int) -> np.ndarray:
        """ Updates weights, returns, and financing."""
        asset_returns = np.asarray(asset_returns, dtype=float)
        missing = ~np.isfinite(asset_returns)
        if missing.any():
            held = missing & (np.abs(prev_weights) > 1e-12)
            if held.any():
                logger.warning("No price at cursor %s for held assets %s; carrying at last price",
                               cursor, list(self.tickers[held]))
            asset_returns = np.where(missing, 0.0, asset_returns)
        gross_return = np.sum(prev_weights * asset_returns)

        borrowed = max(np.sum(np.abs(prev_weights)) - 1.0, 0.0)
        financing_cost = borrowed * self.financing_rate / self.periods_per_year

        portfolio_return = gross_return - financing_cost
        if portfolio_return <= -1.0:
            raise ValueError(f"Equity wiped out at cursor {cursor}: return {portfolio_return:.4f}")
        
        new_weights = prev_weights * (1 + asset_returns) / (1 + portfolio_return)
        self.weights[cursor] = new_weights
        self.returns[cursor] = portfolio_return
        self.financing[cursor] = financing_cost
        return np.array(new_weights)