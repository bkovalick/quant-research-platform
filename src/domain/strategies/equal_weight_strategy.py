from domain.strategies.istrategy import StrategyInterface

class EqualWeightStrategy(StrategyInterface):
    def __init__(self, rebalance_problem, optimizer=None):
        self.rebalance_problem = rebalance_problem

    def rebalance(self, signals, current_weights):
        """Calculate rebalance weights"""
        return 1 / len(current_weights)