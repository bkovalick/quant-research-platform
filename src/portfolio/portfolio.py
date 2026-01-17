import abc
import pandas as pd
import numpy as np
from models.rebalance_solution import RebalanceSolution, RebalanceSubSolution
from core.optimizers.optimizer_factory import FixedWeightOptimizer

class PortfolioInterface(abc.ABC):
    """Interface for portfolio classes."""
    @abc.abstractmethod
    def get_rebalance_solution(self, rebalance_problem):
        pass

class Portfolio(PortfolioInterface):
    """Portfolio class that can use an optimizer to rebalance or return fixed weights."""

    def __init__(self, optimizer=None):
        self.optimizer = optimizer
        self.weights = None
        self.returns = None
        self.holdings = None
        self.turnover = None

    def initialize(self, rebalance_problem):
        self.weights = pd.DataFrame(0, dtype=float, index=rebalance_problem.price_data.index, columns=rebalance_problem.tickers)
        self.weights.iloc[0] = rebalance_problem.initial_weights
        self.returns = pd.Series(0, dtype=float, index=rebalance_problem.price_data.index)
        self.turnover = pd.Series(0, dtype=float, index=rebalance_problem.price_data.index)

    def get_rebalance_solution(self, rebalance_problem):
        if isinstance(self.optimizer, FixedWeightOptimizer):
            # Always return the initial_weights for a fixed-weight portfolio
            decision_variables = {
                'total_trades': np.array([0.0] * len(rebalance_problem.tickers)),
                'portfolio_weights': rebalance_problem.initial_weights  }
            return RebalanceSolution(model=None, decision_variables=decision_variables, rebalance_problem=rebalance_problem)

        return self.optimizer.optimize(rebalance_problem)
    