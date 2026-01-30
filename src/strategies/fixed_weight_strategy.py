import numpy as np

from core.strategies.istrategy import StrategyInterface
from infrastructure.market_data.marketdatagateway import MarketEnvironment

class FixedWeightStrategy(StrategyInterface):
    def __init__(self, rebalance_problem, optimizer=None):
        self.rebalance_problem = rebalance_problem
        self.market_params = {
            "tickers": rebalance_problem.tickers, 
            "start_date": rebalance_problem.start_date, 
            "end_date": rebalance_problem.end_date, 
            "trading_frequency": rebalance_problem.trading_frequency}
        self.market_env = MarketEnvironment(market_params=self.market_params)
        self.optimizer = optimizer

    def calculate_drifted_weights(self, prev_weights, prev_asset_returns):
        """Calculate drifted weights based on previous weights and returns."""
        curr_returns = np.sum(prev_weights * prev_asset_returns)
        curr_weights = prev_weights * (1 + prev_asset_returns)\
              / (1 + np.sum(prev_weights * prev_asset_returns))
        curr_weights = curr_weights / sum(curr_weights)
        return curr_weights, curr_returns
    
    def calculate_rebalanced_weights(self, rebalance_idx, lookback_prices, current_weights):
        """Calculate rebalance weights"""
        return self.rebalance_problem.initial_weights