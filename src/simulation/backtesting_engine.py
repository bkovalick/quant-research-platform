import abc
import numpy as np
import pandas as pd
import time

from domain.portfolio.iportfolio import PortfolioInterface
from domain.strategies.istrategy import StrategyInterface
from config.lookback_windows import LOOKBACK_WINDOWS

class BacktestingEngineInterface(abc.ABC):
    """Interface for backtesting engines."""
    @abc.abstractmethod
    def run_backtest(self, rebalance_problem, optimizer):
        raise NotImplementedError("Must implement run_backtest in derived classes.")

class BacktestingEngine(BacktestingEngineInterface):
    """Concrete implementation of a backtesting engine."""
    def __init__(self, portfolio: PortfolioInterface, strategy: StrategyInterface):
        self.portfolio = portfolio
        self.strategy = strategy
        self.rebalance_problem = self.strategy.rebalance_problem

    def _is_rebalance_date(self, date_idx, rebalance_frequency):
        """Determine if the current date is a rebalance date based on frequency."""
        if rebalance_frequency == 'w':
            return True
        elif rebalance_frequency == 'm':
            return date_idx.is_month_start or date_idx.is_month_end
        elif rebalance_frequency == 'q':
            return date_idx.is_quarter_start or date_idx.is_quarter_end
        elif rebalance_frequency == 'y':
            return date_idx.is_year_start or date_idx.is_year_end
        else:
            raise ValueError(f"Unsupported rebalance frequency: {rebalance_frequency}")

    def run_backtest(self, rebalance_problem):
        """Run backtest on the given rebalance problem."""
        initial_weights = rebalance_problem.initial_weights
        self.asset_prices = self.strategy.market_env.normalized_prices.copy()
        self.asset_returns = self.asset_prices.pct_change().fillna(0)        
        self.portfolio.initialize(self.asset_prices.index, self.asset_prices.columns, initial_weights)
        print("Running backtest...")
        start_time = time.time()
        self._run_backtest_loop()
        print(f"Backtest duration: {time.time() - start_time} seconds")
    
    def _run_backtest_loop(self):
        """Main backtesting loop over all dates."""
        first_rebal = self.rebalance_problem.first_rebal
        date_indices = list(self.asset_prices.index)
        prev_weights = self.portfolio.weights.iloc[0].values.copy()
        rebalance_frequency = getattr(self.rebalance_problem, 'rebalance_frequency', 'w')

        for curr_step, curr_date in enumerate(date_indices):
            print(f"Backtesting date: {curr_date.date()}")
            if curr_step < first_rebal:
                continue

            if curr_step > first_rebal:
                curr_weights, curr_return = self.strategy.calculate_drifted_weights(
                    prev_weights, self.asset_returns.loc[curr_date].values
                )
                self.portfolio.weights.loc[curr_date] = curr_weights
                self.portfolio.returns.loc[curr_date] = curr_return
                prev_weights = curr_weights

            if not self._is_rebalance_date(curr_date, rebalance_frequency):
                continue

            self.rebalance_problem.rebalanced_weights = prev_weights
            optimized_weights = self.strategy.calculate_rebalanced_weights(
                curr_step, self.asset_prices.loc[:curr_date], prev_weights
            )
            self.portfolio.weights.loc[curr_date] = optimized_weights
            self.portfolio.turnover.loc[curr_date] = (
                np.sum(np.abs(self.portfolio.weights.loc[curr_date].values - prev_weights)) / 2
            )
            prev_weights = optimized_weights