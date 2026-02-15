from domain.optimizers.portfolio_optimizer import PortfolioOptimizer
from domain.strategies.istrategy import StrategyInterface
from models.rebalance_problem import RebalanceProblem

class MVOptimizationStrategy(StrategyInterface):
    def __init__(self, 
                 rebalance_problem: RebalanceProblem, 
                 optimizer=None):
        self.rebalance_problem = rebalance_problem
        self.optimizer = optimizer or PortfolioOptimizer()

    def rebalance(self, signals, current_weights):
        """Calculate rebalance weights"""
        return self.optimizer.optimize(self.rebalance_problem, signals, current_weights)