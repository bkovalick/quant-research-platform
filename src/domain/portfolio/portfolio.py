from duckdb import cursor
import pandas as pd
import numpy as np

class Portfolio:
    """Portfolio class that houses weights, returns, and turnover calculations."""
    def __init__(self, financing_rate: float = 0.0, periods_per_year: int = 252):
        self.weights = None
        self.returns = None
        self.turnover = None
        self.financing = None
        self.financing_rate = financing_rate
        self.periods_per_year = periods_per_year

    def initialize(self, dates, tickers: np.ndarray, initial_weights: np.ndarray):
        """Initialize portfolio with rebalance problem and price data."""
        if len(initial_weights) == 0:
            raise ValueError("price_data is empty—cannot initialize portfolio weights.")

        self.weights = pd.DataFrame(0, dtype=float, index=dates, columns=tickers)
        self.weights.iloc[0] = initial_weights
        self.returns = pd.Series(0, dtype=float, index=dates)
        self.turnover = pd.Series(0, dtype=float, index=dates)
        self.financing = pd.Series(0, dtype=float, index=dates)
    
    def apply(self, target_weights: np.ndarray, prev_weights: np.ndarray, cursor: int) -> None:
        """ Updates weights and turnover """
        turnover = np.sum(np.abs(target_weights - prev_weights)) / 2
        self.weights.iloc[cursor] = target_weights
        self.turnover.iloc[cursor] = turnover

    def drift(self, prev_weights: np.ndarray, asset_returns: np.ndarray, cursor: int) -> np.ndarray:
        """ Updates weights, returns, and financing """
        gross_return = np.sum(prev_weights * asset_returns)

        borrowed = max(np.sum(np.abs(prev_weights)) - 1.0, 0.0)
        financing_cost = borrowed * self.financing_rate / self.periods_per_year

        portfolio_return = gross_return - financing_cost
        if portfolio_return <= -1.0:
            raise ValueError(f"Equity wiped out at cursor {cursor}: return {portfolio_return:.4f}")
        
        new_weights = prev_weights * (1 + asset_returns) / (1 + portfolio_return)
        self.weights.iloc[cursor] = new_weights
        self.returns.iloc[cursor] = portfolio_return
        self.financing.iloc[cursor] = financing_cost
        return np.array(new_weights)