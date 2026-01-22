import pandas as pd
import numpy as np
from models.rebalance_solution import RebalanceSolution
from core.optimizers.optimizer_factory import FixedWeightOptimizer
from core.portfolio.iportfolio import PortfolioInterface

class Portfolio(PortfolioInterface):
    """Portfolio class that houses weights, returns, and turnover calculations."""

    def __init__(self):
        self.weights = None
        self.returns = None
        self.holdings = None
        self.turnover = None

    def initialize(self, rebalance_problem):
        self.weights = pd.DataFrame(0, dtype=float, index=rebalance_problem.price_data.index, columns=rebalance_problem.tickers)
        self.weights.iloc[0] = rebalance_problem.initial_weights
        self.returns = pd.Series(0, dtype=float, index=rebalance_problem.price_data.index)
        self.turnover = pd.Series(0, dtype=float, index=rebalance_problem.price_data.index)
    
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
    
    