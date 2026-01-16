import abc
import numpy as np
import pandas as pd
import time

from models.rebalance_solution import RebalanceSubSolution

class PortfolioInterface(abc.ABC):
    """Interface for portfolio classes."""
    @abc.abstractmethod
    def get_rebalance_solution(self, rebalance_problem):
        pass

class FixedWeightPortfolio:
    """A simple fixed-weight portfolio for benchmarking purposes."""
    def __init__(self, 
                 optimizer = None):
        self.optimizer = optimizer

    def get_rebalance_solution(self, rebalance_problem):
        """Return the fixed weights of the portfolio."""
        return RebalanceSubSolution(
            total_trades = np.array([0.0] * len(rebalance_problem.tickers)), 
            portfolio_weights = rebalance_problem.initial_weights)
    
class MaxSharpePortfolio:
    """A portfolio optimized to maximize the Sharpe ratio."""
    def __init__(self, 
                 optimizer = None):
        self.optimizer = optimizer

    def get_rebalance_solution(self, rebalance_problem):
        """Optimize the portfolio to maximize the Sharpe ratio."""
        return self.optimizer.optimize(rebalance_problem)
    
class BacktestingEngineInterface(abc.ABC):
    """Interface for backtesting engines."""
    @abc.abstractmethod
    def run_backtest(self, rebalance_problem, optimizer):
        pass

class BacktestingEngine(BacktestingEngineInterface):
    def __init__(self, portfolio: PortfolioInterface):
        self.portfolio = portfolio

    """Concrete implementation of a backtesting engine."""
    def run_backtest(self, rebalance_problem):
        # create a fixedweight portfolio as an optimizer -> good benchmark
        self._setup_variables(rebalance_problem)
        self._setup_rebalancing_data(rebalance_problem)

        print("Running backtest...")
        start_time = time.time()
        last_date_idx = None
        for i, date_idx in enumerate(self.asset_prices.index):
            print(f"Backtesting date: {date_idx}")
            
            # Skip first row and rows with insufficient lookback window
            if i < rebalance_problem.first_rebal: # starting_week, we can choose to not start on t = 0
                last_date_idx = date_idx
                continue

            # compute drift returns/weights
            if i > rebalance_problem.first_rebal:            
                self.portfolio_weights.loc[date_idx], self.portfolio_returns.loc[date_idx] = \
                    self._calculate_drifted_weights(self.portfolio_weights.loc[last_date_idx], \
                                                    self.asset_returns.loc[date_idx])

            # check if it's a rebalancing date
            rebalance_problem.initial_weights = np.array(self.portfolio_weights.loc[date_idx])
            prev_weights = rebalance_problem.initial_weights.copy()
            rebalanced_portfolio = self.portfolio.get_rebalance_solution(rebalance_problem)
            self.portfolio_weights.loc[date_idx] = rebalanced_portfolio.portfolio_weights
            self.portfolio_turnover.loc[date_idx] = np.sum(np.abs(self.portfolio_weights.loc[date_idx] - prev_weights)) / 2
            
            last_date_idx = date_idx

        performance_metrics_df = self._calculate_performance_metrics(self.portfolio_returns, \
                                                                     self.portfolio_weights, self.portfolio_turnover)
        print(f"Backtest duration: {time.time() - start_time} seconds")
        return performance_metrics_df

    def _setup_variables(self, rebalance_problem):
        """Setup necessary variables for backtesting."""
        self.asset_prices = rebalance_problem.price_data
        self.asset_returns = rebalance_problem.returns_data
        self.portfolio_weights = pd.DataFrame(0, dtype = float, \
                                        index = self.asset_prices.index, columns=rebalance_problem.tickers)
        self.portfolio_weights.iloc[0] = rebalance_problem.initial_weights
        self.portfolio_returns = pd.Series(0, dtype = float, index = self.asset_prices.index)
        self.portfolio_turnover = pd.Series(0, dtype = float, index = self.asset_prices.index)

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

    def _calculate_rebalance_weights(self):
        """Calculate rebalance weights considering cash allocation."""
        return []
    
    def _calculate_performance_metrics(self, portfolio_returns: pd.Series, portfolio_weights, portfolio_turnover):
        """Calculate performance metrics for the portfolio."""
        wealth_factors = (1 + portfolio_returns).cumprod()
        cumulative_returns = wealth_factors - 1
        asset_returns = cumulative_returns.iloc[-1]  ** (1/(cumulative_returns.shape[0]/52)) - 1
        asset_volatilities = portfolio_returns.std() * np.sqrt(252)
        performance_metrics = {
            "portfolio_weights": portfolio_weights,
            "portfolio_wealth_factors": wealth_factors,
            "cumulative_returns": cumulative_returns,
            "return": asset_returns,
            "volatility": asset_volatilities,
            "sharpe_ratio": asset_returns / asset_volatilities,
            "max_drawdown": self._calculate_max_drawdown(cumulative_returns),
            "turnover": portfolio_turnover
        }
        return performance_metrics
    
    def _calculate_max_drawdown(self, cumulative_returns):
        running_max = cumulative_returns.cummax()
        drawdown = (cumulative_returns - running_max) / running_max
        return drawdown.min()    