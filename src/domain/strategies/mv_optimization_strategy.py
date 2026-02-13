import numpy as np

from domain.signals.signals import Signals
from domain.optimizers.cvxpy_optimizer import CvxpyOptimizer
from domain.strategies.istrategy import StrategyInterface
from data.market_data_gateway import MarketEnvironment

class MVOptimizationStrategy(StrategyInterface):
    freq_map = {"d": 252, "w": 52, "m": 12, "q": 4, "y": 1}

    def __init__(self, rebalance_problem, optimizer=None):
        self.rebalance_problem = rebalance_problem
        self.market_params = {
            "tickers": rebalance_problem.tickers, 
            "start_date": rebalance_problem.start_date, 
            "end_date": rebalance_problem.end_date, 
            "trading_frequency": rebalance_problem.trading_frequency}
        self.market_env = MarketEnvironment(market_params=self.market_params)
        self.optimizer = optimizer or CvxpyOptimizer()
        self.signals = Signals(self.market_env, 
                               ann_factor=self.freq_map.get(rebalance_problem.trading_frequency, 252))
        self.rebalance_solution = None
        self.rebalance_solutions = []

    def calculate_drifted_weights(self, prev_weights, prev_asset_returns):
        """Calculate drifted weights based on previous weights and returns."""
        curr_returns = np.sum(prev_weights * prev_asset_returns)
        curr_weights = prev_weights * (1 + prev_asset_returns) / (1 + curr_returns)  
        curr_weights /= sum(curr_weights)
        return curr_weights, curr_returns
    
    def calculate_rebalanced_weights(self, rebalance_idx, lookback_prices, current_weights):
        """Calculate rebalance weights"""
        if rebalance_idx < self.rebalance_problem.lookback_window:       
            return self.rebalance_problem.initial_weights
        
        self.market_env.normalized_prices = self._apply_winsorizing(lookback_prices)
        self.rebalance_solution = self.optimizer.optimize(self.rebalance_problem, 
                                                          self.signals, current_weights)
        self.rebalance_solutions.append(self.rebalance_solution)
        portfolio_weights = self.rebalance_solution.decision_variables['portfolio_weights']
        return portfolio_weights
    
    def _apply_winsorizing(self, lookback_prices):
        """Apply windsoring to lookback prices."""
        if self.rebalance_problem.windsor_percentiles is None or \
                self.rebalance_problem.apply_windsoring is False:
            return lookback_prices
        
        windsor_percentiles = self.rebalance_problem.windsor_percentiles
        lower_bound = lookback_prices.quantile(windsor_percentiles["lower"])
        upper_bound = lookback_prices.quantile(windsor_percentiles["upper"])
        return lookback_prices.clip(lower=lower_bound, upper=upper_bound, axis = 1)