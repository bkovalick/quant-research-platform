from domain.strategies.istrategy import StrategyInterface

class FixedWeightStrategy(StrategyInterface):
    def __init__(self, rebalance_problem, optimizer=None):
        self.rebalance_problem = rebalance_problem

    def rebalance(self, signals, current_weights):
        """Calculate rebalance weights"""
        return current_weights