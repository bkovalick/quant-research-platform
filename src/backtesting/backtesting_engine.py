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
            portfolio_weights = [ holding / rebalance_problem.total_portfolio_value \
                                 for holding in rebalance_problem.initial_holdings])
    
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
    """Concrete implementation of a backtesting engine."""
    # Constants for annualization
    WEEKS_PER_YEAR = 52
    
    def __init__(self, portfolio: PortfolioInterface):
        self.portfolio = portfolio
        self.annual_trading_days = { "d": 252, "w": 52, "m": 12, "q": 4, "y": 1}
        
    def run_backtest(self, rebalance_problem):
        self._setup_rebalancing_data(rebalance_problem)
        self._setup_variables(rebalance_problem)

        print("Running backtest...")
        start_time = time.time()
        
        # Cache frequently accessed attributes to reduce lookups
        first_rebal = rebalance_problem.first_rebal
        lookback_window = rebalance_problem.lookback_window
        date_indices = list(self.asset_prices.index)
        prev_weights = self.portfolio_weights.iloc[0].values.copy()
        
        for i, date_idx in enumerate(date_indices):
            print(f"Backtesting date: {date_idx}")
            
            # Skip early rows before lookback window
            if i < first_rebal:
                continue

            # Compute drift returns/weights from previous period
            if i > first_rebal:            
                curr_weights, curr_return = self._calculate_drifted_weights(
                    prev_weights, self.asset_returns.loc[date_idx].values
                )
                self.portfolio_weights.loc[date_idx] = curr_weights
                self.portfolio_returns.loc[date_idx] = curr_return
                prev_weights = curr_weights
            
            # Rebalance: hold weights during lookback period, then optimize
            if i < lookback_window and i > 0:
                # During lookback window, use previous weights
                self.portfolio_weights.loc[date_idx] = prev_weights
            else:
                # After lookback window, run optimization
                rebalance_problem.initial_weights = prev_weights
                optimized_weights = self._calculate_rebalance_weights(
                    rebalance_problem, self.asset_prices.loc[:date_idx]
                )
                self.portfolio_weights.loc[date_idx] = optimized_weights
            
            # Calculate turnover: sum of absolute weight changes divided by 2
            self.portfolio_turnover.loc[date_idx] = (
                np.sum(np.abs(self.portfolio_weights.loc[date_idx].values - prev_weights)) / 2
            )

        performance_metrics_df = self._calculate_performance_metrics(
            rebalance_problem, self.portfolio_returns, self.portfolio_weights, self.portfolio_turnover
        )
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

    def _calculate_rebalance_weights(self, rebalance_problem, model_data):
        """Calculate rebalance weights"""
        rebalance_problem.price_data = model_data
        rebalanced_portfolio = self.portfolio.get_rebalance_solution(rebalance_problem)
        curr_weights = rebalanced_portfolio.portfolio_weights
        return curr_weights
    
    def _calculate_performance_metrics(self, rebalance_problem, portfolio_returns: pd.Series, \
                                       portfolio_weights, portfolio_turnover):
        """Calculate performance metrics for the portfolio."""
        wealth_factors = (1 + portfolio_returns).cumprod()
        cumulative_returns = wealth_factors - 1
        
        # Annualize return: compound final return over time horizon
        num_periods = cumulative_returns.shape[0]
        years = num_periods / self.WEEKS_PER_YEAR
        annualized_return = cumulative_returns.iloc[-1] ** (1 / years)
        
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
            "max_drawdown": self._calculate_max_drawdown(cumulative_returns),
            "turnover": portfolio_turnover
        }
        return performance_metrics
    
    def _calculate_max_drawdown(self, cumulative_returns):
        running_max = cumulative_returns.cummax()
        drawdown = (cumulative_returns - running_max) / running_max
        return drawdown.min()    