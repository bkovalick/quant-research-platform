import abc
import numpy as np
import pandas as pd
import time
import matplotlib.pyplot as plt

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
        """Determine if the current date is a rebalance date based on frequency."""
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
        """Run backtest on the given rebalance problem."""
        self._setup_rebalancing_data(rebalance_problem)
        self.portfolio.initialize(rebalance_problem)
        self.asset_prices = rebalance_problem.price_data
        self.asset_returns = rebalance_problem.returns_data

        print("Running backtest...")
        start_time = time.time()

        self._run_backtest_loop(rebalance_problem)

        performance_metrics = self._calculate_performance_metrics(
            rebalance_problem, self.portfolio.returns, self.portfolio.weights, self.portfolio.turnover
        )
        print(f"Backtest duration: {time.time() - start_time} seconds")
        return performance_metrics

    def _run_backtest_loop(self, rebalance_problem):
        """Main backtesting loop over all dates."""
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
        
        # Only compute max drawdown after lookback period
        lookback_window = getattr(rebalance_problem, 'lookback_window', 0)
        if lookback_window > 0:
            drawdown_returns = cumulative_returns.iloc[lookback_window:]
        else:
            drawdown_returns = cumulative_returns
        performance_metrics = {
            "portfolio_wealth_factors": wealth_factors,
            "portfolio_weights": portfolio_weights,
            "portfolio_returns": portfolio_returns,
            "portfolio_turnover": portfolio_turnover,
            "cumulative_returns": cumulative_returns,
            "return": annualized_return,
            "volatility": annualized_volatility,
            "sharpe_ratio": sharpe_ratio,
            "max_drawdown": abs(self._calculate_max_drawdown(drawdown_returns)),
            "turnover": portfolio_turnover.mean() * self.WEEKS_PER_YEAR
        }
        self._save_performance_plot(portfolio_returns, wealth_factors, sharpe_ratio, rebalance_problem)
        return performance_metrics
    
    def _calculate_max_drawdown(self, cumulative_returns):
        """Calculate maximum drawdown from cumulative returns."""
        running_max = cumulative_returns.cummax()
        drawdown = (cumulative_returns - running_max) / running_max
        return drawdown.min()  # negative value; abs() taken in reporting    
    
    def _save_performance_plot(self, portfolio_returns, wealth_factors, sharpe_ratio, rebalance_problem):
        """Generate and save performance plot with descriptive filename."""
        # Plot cumulative returns and save with descriptive filename
        returns = portfolio_returns.dropna(axis = 0)
        if isinstance(returns, pd.Series):
            if returns.name is None:
                returns.name = 'portfolio'      
            returns = returns.to_frame()        
        ax = wealth_factors.plot(figsize = (10,4))
        ax.set_title('Cumulative Return',  fontsize = 16)
        ax.tick_params(axis='x', labelsize = 12)
        ax.tick_params(axis='y', labelsize = 12)
        # Fix legend: build labels as list of strings, using scalar sharpe_ratio for all columns
        if np.isscalar(sharpe_ratio):
            labels = [f"{col} - Sharpe: {sharpe_ratio:.2f}" for col in returns.columns]
        else:
            labels = [f"{col} - Sharpe: {sharpe_ratio.get(col, 0):.2f}" for col in returns.columns]
        plt.legend(labels, fontsize=12.5)

        # Build descriptive filename
        program_type = getattr(rebalance_problem, 'program_type', 'unknown')
        # Try to get start/end dates from wealth_factors index
        try:
            start_date = str(wealth_factors.index[0])[:10]
            end_date = str(wealth_factors.index[-1])[:10]
        except Exception:
            start_date = 'unknown_start'
            end_date = 'unknown_end'
        filename = f"backtest_results/cumulative_return_{program_type}_{start_date}_to_{end_date}.png"
        plt.savefig(filename, bbox_inches='tight')
        plt.close()