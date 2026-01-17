import pandas as pd
import numpy as np

from portfolio.portfolio_calculations import PortfolioCalculations

class RebalanceProblem:
    """
    Pure data container for a prepared rebalance problem.

    This class will compute derived values (returns, mean vector, covariance)
    from the current `price_data` if precomputed values are absent or if
    `price_data` is replaced. Assigning to `price_data` invalidates cached
    derived values so subsequent property access recomputes from the current
    data.
    """

    def __init__(self, prepared_data: dict):
        self._data = dict(prepared_data)

    @property
    def n_constituents(self) -> int:
        return len(self.tickers)

    @property
    def tickers(self) -> list:
        return self._data.get("tickers", [])

    @property
    def price_data(self) -> pd.DataFrame:
        return self._data.get("price_data")

    @price_data.setter
    def price_data(self, df: pd.DataFrame):
        """Replace stored price data and invalidate derived cached values."""
        self._data["price_data"] = df
        # Remove cached derived results to force recomputation
        for key in ("returns_data", "mean_vector", "covariance_matrix"):
            if key in self._data:
                del self._data[key]

    @property
    def returns_data(self) -> pd.DataFrame:
        if "returns_data" in self._data:
            return self._data["returns_data"]
        price_df = self.price_data
        if price_df is None:
            return None
        returns = PortfolioCalculations.calculate_returns(price_df)
        # cache for subsequent calls
        self._data["returns_data"] = returns
        return returns

    @property
    def mean_vector(self) -> np.ndarray:
        if "mean_vector" in self._data:
            return self._data["mean_vector"]
        returns = self.returns_data
        if returns is None:
            return None
        mean = PortfolioCalculations.calculate_mean_returns(returns)
        self._data["mean_vector"] = mean
        return mean

    @property
    def covariance_matrix(self) -> np.ndarray:
        if "covariance_matrix" in self._data:
            return self._data["covariance_matrix"]
        returns = self.returns_data
        if returns is None:
            return None
        cov = PortfolioCalculations.calculate_covariance_matrix(returns)
        self._data["covariance_matrix"] = cov
        return cov

    @property
    def risk_free_rate(self) -> float:
        return self._data.get("risk_free_rate")

    @property
    def target_weights(self) -> list:
        return self._data.get("target_weights")

    @property
    def initial_holdings(self) -> list:
        return self._data.get("initial_holdings")

    @property
    def initial_weights(self) -> list:
        return self._data.get("initial_weights")

    @initial_weights.setter
    def initial_weights(self, weights):
        """Set the initial portfolio weights."""
        self._data["initial_weights"] = weights

    @property
    def total_portfolio_value(self) -> float:
        return self._data.get("total_portfolio_value")

    @property
    def cash_allocation(self) -> float:
        return self._data.get("cash_allocation")
    
    @property
    def trading_frequency(self) -> str:
        return self._data.get("trading_frequency", "d")
    
    @property
    def lookback_window(self) -> int:
        return self._data.get("lookback_window", 252)
    
    @property
    def first_rebal(self) -> int:
        return self._data.get("first_rebal", 0)
    
    @property
    def risk_tolerance(self) -> int:
        return self._data.get("risk_tolerance", 0)