from domain.optimizers.portfolio_optimizer import PortfolioOptimizer
from domain.strategies.istrategy import StrategyInterface
from domain.signals.signals import Signals
from models.rebalance_problem import RebalanceProblem
import numpy as np

class MeanVarianceStrategy(StrategyInterface):
    def __init__(self, 
                 rebalance_problem: RebalanceProblem, 
                 optimizer=None):
        self.rebalance_problem = rebalance_problem
        self.optimizer = optimizer or PortfolioOptimizer()

    # TODO Signals will evolve and my hope is for this to be a dictionary of signals
    # signals = { "Base_Signals": signals, "MovingAvgSignals": ma_signals, etc. }
    def rebalance(self, signals: Signals, current_weights: np.ndarray):
        """Calculate rebalance weights"""
        rebalance_problem = self.rebalance_problem
        # target_vol = 0.10
        # raw_weights = self.optimizer.optimize(self.rebalance_problem, signals, current_weights)
        # realized_vol = signals.portfolio_vol(raw_weights)
        # scale = target_vol / realized_vol
        # final_weights = raw_weights * scale
        # return final_weights
        return self.optimizer.optimize(rebalance_problem, signals, current_weights)