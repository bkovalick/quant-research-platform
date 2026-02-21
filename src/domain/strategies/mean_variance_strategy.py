from domain.optimizers.portfolio_optimizer import PortfolioOptimizer
from domain.strategies.istrategy import StrategyInterface
from models.rebalance_problem import RebalanceProblem

class MeanVarianceStrategy(StrategyInterface):
    def __init__(self, 
                 rebalance_problem: RebalanceProblem, 
                 optimizer=None):
        self.rebalance_problem = rebalance_problem
        self.optimizer = optimizer or PortfolioOptimizer()

    def rebalance(self, signals, current_weights):
        """Calculate rebalance weights"""
        # target_vol = 0.10
        # raw_weights = self.optimizer.optimize(self.rebalance_problem, signals, current_weights)
        # realized_vol = signals.portfolio_vol(raw_weights)
        # scale = target_vol / realized_vol
        # final_weights = raw_weights * scale
        # return final_weights
        return self.optimizer.optimize(self.rebalance_problem, signals, current_weights)