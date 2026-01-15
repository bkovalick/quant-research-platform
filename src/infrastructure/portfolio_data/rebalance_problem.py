import pandas as pd
import numpy as np


class RebalanceProblem:
    """
    Pure data container for a prepared rebalance problem.
    
    Does NOT perform data fetching or transformations.
    Use RebalanceProblemBuilder to construct instances.
    """
    
    def __init__(self, prepared_data: dict):
        """
        Initialize with pre-processed data.
        
        Args:
            prepared_data: Dictionary with keys:
                - tickers: List of ticker symbols
                - price_data: DataFrame with price data
                - returns_data: DataFrame with calculated returns
                - mean_vector: Array of mean returns
                - covariance_matrix: Covariance matrix as numpy array
                - risk_free_rate: Risk-free rate
                - target_weights: List of target weights
                - initial_holdings: List of initial holdings
                - total_portfolio_value: Total portfolio value
                - cash_allocation: Cash allocation amount
        """
        self._data = prepared_data
    
    @property
    def n_constituents(self) -> int:
        """Number of portfolio constituents."""
        return len(self._data["tickers"])
    
    @property
    def tickers(self) -> list:
        """List of ticker symbols."""
        return self._data["tickers"]
    
    @property
    def price_data(self) -> pd.DataFrame:
        """Historical price data."""
        return self._data["price_data"]
    
    @property
    def returns_data(self) -> pd.DataFrame:
        """Calculated returns data."""
        return self._data["returns_data"]
    
    @property
    def mean_vector(self) -> np.ndarray:
        """Mean returns vector."""
        return self._data["mean_vector"]
    
    @property
    def covariance_matrix(self) -> np.ndarray:
        """Covariance matrix of returns."""
        return self._data["covariance_matrix"]
    
    @property
    def risk_free_rate(self) -> float:
        """Risk-free rate for optimization."""
        return self._data["risk_free_rate"]
    
    @property
    def target_weights(self) -> list:
        """Target portfolio weights."""
        return self._data["target_weights"]
    
    @property
    def initial_holdings(self) -> list:
        """Initial holdings for each constituent."""
        return self._data["initial_holdings"]
    
    @property
    def total_portfolio_value(self) -> float:
        """Total portfolio value including cash."""
        return self._data["total_portfolio_value"]
    
    @property
    def cash_allocation(self) -> float:
        """Available cash allocation."""
        return self._data["cash_allocation"]