import abc
import numpy as np
import pandas as pd
import time

from portfolio.portfolio import PortfolioInterface

class BacktestingEngineInterface(abc.ABC):
    """Interface for backtesting engines."""
    @abc.abstractmethod
    def run_backtest(self, rebalance_problem, optimizer):
        pass

class BacktestingEngine(BacktestingEngineInterface):
    """Concrete implementation of a backtesting engine."""
    WEEKS_PER_YEAR = 52
    
    def __init__(self, portfolio: PortfolioInterface):
        self.portfolio = portfolio
        self.annual_trading_days = { "d": 252, "w": 52, "m": 12, "q": 4, "y": 1}
        
    def _is_rebalance_date(self, date_idx, rebalance_frequency):
        if rebalance_frequency == 'w':
            return True  # every week
        elif rebalance_frequency == 'm':
            return date_idx.is_month_start or date_idx.is_month_end
        elif rebalance_frequency == 'q':
            return date_idx.is_quarter_start or date_idx.is_quarter_end
        elif rebalance_frequency == 'y':
            return date_idx.is_year_start or date_idx.is_year_end
        else:
            raise ValueError(f"Unsupported rebalance frequency: {rebalance_frequency}")

    def run_backtest(self, rebalance_problem):
        self._setup_rebalancing_data(rebalance_problem)
        self.portfolio.initialize(rebalance_problem)
        self.asset_prices = rebalance_problem.price_data
        self.asset_returns = rebalance_problem.returns_data

        print("Running backtest...")
        start_time = time.time()

        first_rebal = rebalance_problem.first_rebal
        lookback_window = rebalance_problem.lookback_window
        date_indices = list(self.asset_prices.index)
        prev_weights = self.portfolio.weights.iloc[0].values.copy()
        rebalance_frequency = getattr(rebalance_problem, 'rebalance_frequency', 'w')

        for i, date_idx in enumerate(date_indices):
            print(f"Backtesting date: {date_idx}")
            if i < first_rebal:
                continue

            if i > first_rebal:
                curr_weights, curr_return = self._calculate_drifted_weights(
                    prev_weights, self.asset_returns.loc[date_idx].values
                )
                self.portfolio.weights.loc[date_idx] = curr_weights
                self.portfolio.returns.loc[date_idx] = curr_return
                prev_weights = curr_weights

            if not self._is_rebalance_date(date_idx, rebalance_frequency):
                continue

            rebalance_problem.rebalanced_weights = prev_weights
            optimized_weights = self._calculate_rebalance_weights(
                i, lookback_window, rebalance_problem, self.asset_prices.loc[:date_idx]
            )
            self.portfolio.weights.loc[date_idx] = optimized_weights
            self.portfolio.turnover.loc[date_idx] = (
                np.sum(np.abs(self.portfolio.weights.loc[date_idx].values - prev_weights)) / 2
            )
            prev_weights = optimized_weights

        performance_metrics = self._calculate_performance_metrics(
            rebalance_problem, self.portfolio.returns, self.portfolio.weights, self.portfolio.turnover
        )
        print(f"Backtest duration: {time.time() - start_time} seconds")
        return performance_metrics
    
    def _setup_rebalancing_data(self, rebalance_problem):
        """Setup market data frequency based on rebalance problem settings."""
        rebalance_problem.price_data = rebalance_problem.price_data.asfreq(
            rebalance_problem.trading_frequency, method='ffill'
        )

        rebalance_problem.price_data = rebalance_problem.price_data.dropna(axis = 0)

    def _calculate_drifted_weights(self, prev_weights, prev_asset_returns):
        """Calculate drifted weights based on previous weights and returns."""
        curr_returns = np.sum(prev_weights * prev_asset_returns)
        curr_weights = prev_weights * (1 + prev_asset_returns) / (1 + np.sum(prev_weights * prev_asset_returns))  
        curr_weights = curr_weights / sum(curr_weights)
        return curr_weights, curr_returns

    def _calculate_rebalance_weights(self, i, lookback_window, rebalance_problem, model_data):
        """Calculate rebalance weights"""
        if i < lookback_window:
            return rebalance_problem.initial_weights
        
        rebalance_problem.price_data = model_data
        rebalance_solution = self.portfolio.get_rebalance_solution(rebalance_problem)
        curr_weights = rebalance_solution.rebalance_sub_solution.portfolio_weights
        return curr_weights
    
    def _calculate_performance_metrics(self, rebalance_problem, portfolio_returns: pd.Series, \
                                       portfolio_weights, portfolio_turnover):
        """Calculate performance metrics for the portfolio."""
        wealth_factors = (1 + portfolio_returns).cumprod()
        cumulative_returns = wealth_factors - 1
        # Annualize return: compound final return over time horizon (CAGR)
        num_periods = cumulative_returns.shape[0]
        years = num_periods / self.WEEKS_PER_YEAR
        annualized_return = wealth_factors.iloc[-1] ** (1 / years) - 1
        
        # Annualize volatility
        annualized_volatility = portfolio_returns.std() * np.sqrt(self.annual_trading_days[rebalance_problem.trading_frequency])
        
        # Calculate Sharpe ratio safely (avoid division by zero)
        sharpe_ratio = (
            annualized_return / annualized_volatility 
            if annualized_volatility != 0 else 0.0
        )
        
        performance_metrics = {
            "portfolio_weights": portfolio_weights,
            "portfolio_wealth_factors": wealth_factors,
            "cumulative_returns": cumulative_returns,
            "return": annualized_return,
            "volatility": annualized_volatility,
            "sharpe_ratio": sharpe_ratio,
            "max_drawdown": abs(self._calculate_max_drawdown(cumulative_returns)),
            "turnover": portfolio_turnover.mean() * self.WEEKS_PER_YEAR
        }
        return performance_metrics
    
    def _calculate_max_drawdown(self, cumulative_returns):
        running_max = cumulative_returns.cummax()
        drawdown = (cumulative_returns - running_max) / running_max
        return drawdown.min()  # negative value; abs() taken in reporting