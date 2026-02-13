import pandas as pd
import numpy as np
from domain.portfolio.iportfolio import PortfolioInterface

class Portfolio(PortfolioInterface):
    """Portfolio class that houses weights, returns, and turnover calculations."""

    def __init__(self):
        self.weights = None
        self.returns = None
        self.holdings = None
        self.turnover = None

    def initialize(self, dates, tickers, initial_weights):
        """Initialize portfolio with rebalance problem and price data."""
        if len(initial_weights) == 0:
            raise ValueError("price_data is empty—cannot initialize portfolio weights.")

        self.weights = pd.DataFrame(0, dtype=float, index=dates, columns=tickers)
        self.weights.iloc[0] = initial_weights
        self.returns = pd.Series(0, dtype=float, index=dates)
        self.turnover = pd.Series(0, dtype=float, index=dates)
    
    @property
    def rebalanced_weights(self):
        """Get the current portfolio weights."""
        return self.weights
    
    @property
    def current_returns(self):
        """Get the current portfolio returns."""
        return self.returns
    
    @property
    def current_turnover(self):
        """Get the current portfolio turnover."""
        return self.turnover
    
    