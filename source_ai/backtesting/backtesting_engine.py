import numpy as np
import pandas as pd
import time

from .portfolio import Portfolio

class BacktestingEngine:
    def __init__(self, portfolio: Portfolio):
        self.portfolio = portfolio
    def run_backtest(self, rebalance_problem):
        self._setup_variables(rebalance_problem)
        self._setup_rebalancing_data(rebalance_problem)
        print("Running backtest...")
        start_time = time.time()
        last_date_idx = None
        # Every row in price_data is a rebalance date, since price_data is already resampled
        for i, date_idx in enumerate(self.asset_prices.index):
            print(f"Backtesting date: {date_idx}")
            if i < rebalance_problem.first_rebal:
                last_date_idx = date_idx
                continue

            if i > rebalance_problem.first_rebal:
                self.portfolio_weights.loc[date_idx], self.portfolio_returns.loc[date_idx] = \
                    self._calculate_drifted_weights(self.portfolio_weights.loc[last_date_idx],
                                                    self.asset_returns.loc[date_idx])
            # Always rebalance on every row
            previous_weights = self.portfolio_weights.loc[date_idx].copy() if last_date_idx is None \
                else self.portfolio_weights.loc[last_date_idx].copy()
            if i < rebalance_problem.lookback_window and i > 0:
                self.portfolio_weights.loc[date_idx] = self.portfolio_weights.loc[last_date_idx]
            else:
                rebalance_problem.initial_weights = previous_weights
                self.portfolio_weights.loc[date_idx] = self._calculate_rebalance_weights(rebalance_problem, self.asset_prices.loc[:date_idx])
            self.portfolio_turnover.loc[date_idx] = np.sum(np.abs(self.portfolio_weights.loc[date_idx] - previous_weights)) / 2
            last_date_idx = date_idx
            
        performance_metrics_df = self._calculate_performance_metrics(self.portfolio_returns,
                                                                     self.portfolio_weights, self.portfolio_turnover)
        print(f"Backtest duration: {time.time() - start_time} seconds")
        return performance_metrics_df
    
    def _setup_variables(self, rebalance_problem):
        self.asset_prices = rebalance_problem.price_data
        self.asset_returns = rebalance_problem.returns_data
        self.portfolio_weights = pd.DataFrame(0, dtype=float,
                                        index=self.asset_prices.index, columns=rebalance_problem.tickers)
        self.portfolio_weights.iloc[0] = rebalance_problem.initial_weights
        self.portfolio_returns = pd.Series(0, dtype=float, index=self.asset_prices.index)
        self.portfolio_turnover = pd.Series(0, dtype=float, index=self.asset_prices.index)
    def _setup_rebalancing_data(self, rebalance_problem):
        rebalance_problem.price_data = rebalance_problem.price_data.asfreq(
            rebalance_problem.trading_frequency, method='ffill')
        rebalance_problem.price_data = rebalance_problem.price_data.dropna(axis=0)
    def _calculate_drifted_weights(self, prev_weights, prev_asset_returns):
        curr_returns = np.sum(prev_weights * prev_asset_returns)
        curr_weights = prev_weights * (1 + prev_asset_returns) / (1 + np.sum(prev_weights * prev_asset_returns))
        curr_weights = curr_weights / sum(curr_weights)
        return curr_weights, curr_returns
    def _calculate_rebalance_weights(self, rebalance_problem, model_data):
        rebalance_problem.price_data = model_data
        rebalanced_portfolio = self.portfolio.get_rebalance_solution(rebalance_problem)
        curr_weights = rebalanced_portfolio.portfolio_weights
        return curr_weights
    def _calculate_performance_metrics(self, portfolio_returns: pd.Series, portfolio_weights, portfolio_turnover):
        wealth_factors = (1 + portfolio_returns).cumprod()
        cumulative_returns = wealth_factors - 1
        num_periods = cumulative_returns.shape[0]
        years = num_periods / 52
        annualized_return = cumulative_returns.iloc[-1] ** (1 / years) - 1
        annualized_volatility = portfolio_returns.std() * np.sqrt(252)
        sharpe_ratio = (annualized_return / annualized_volatility if annualized_volatility != 0 else 0.0)
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
