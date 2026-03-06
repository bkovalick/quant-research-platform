from domain.strategies.istrategy import StrategyInterface
from models.rebalance_problem import RebalanceProblem
import numpy as np

class FixedWeightStrategy(StrategyInterface):
    def __init__(self, rebalance_problem: RebalanceProblem, optimizer=None):
        self.rebalance_problem = rebalance_problem

    def rebalance(self, signals: dict, current_weights: np.ndarray) -> np.ndarray:
        """Calculate rebalance weights"""
        return self.rebalance_problem.initial_weights