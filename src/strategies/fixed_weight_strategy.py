from core.strategies.istrategy import StrategyInterface
import numpy as np

class FixedWeightStrategy(StrategyInterface):
    def __init__(self, rebalance_problem, optimizer=None):
        self.rebalance_problem = rebalance_problem
        self.optimizer = optimizer

    def calculate_drifted_weights(self, prev_weights, prev_asset_returns):
        """Calculate drifted weights based on previous weights and returns."""
        curr_returns = np.sum(prev_weights * prev_asset_returns)
        curr_weights = prev_weights * (1 + prev_asset_returns) / (1 + np.sum(prev_weights * prev_asset_returns))
        curr_weights = curr_weights / sum(curr_weights)
        return curr_weights, curr_returns
    
    def calculate_rebalanced_weights(self, rebalance_idx, lookback_prices):
        return self.rebalance_problem.initial_weights