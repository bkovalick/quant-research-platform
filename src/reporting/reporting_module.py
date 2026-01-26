from openpyxl import Workbook
from openpyxl.utils.dataframe import dataframe_to_rows
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import yfinance as yf

from portfolio.portfolio import Portfolio

class ReportingSystem:
    WEEKS_PER_YEAR = 52
    ANNUAL_TRADING_DAYS = { "d": 252, "w": 52, "m": 12, "q": 4, "y": 1}

    @classmethod
    def generate_report(cls, filename: str, results: dict):
        wb = Workbook()
        default_sheet = wb.active
        wb.remove(default_sheet)
        if "summary" in results:
            summary_ws = wb.create_sheet(title="Summary")
            summary_rows = dataframe_to_rows(results["summary"], header=True, index=False)   
            for r_idx, row in enumerate(summary_rows, 1):
                for c_idx, value in enumerate(row, 1):
                    summary_ws.cell(row=r_idx, column=c_idx, value=value)

        if "time_series" in results:
            ts_ws = wb.create_sheet(title="Time Series")
            ts_rows = dataframe_to_rows(results["time_series"], header=True, index=False)
            for r_idx, row in enumerate(ts_rows, 1):
                for c_idx, value in enumerate(row, 1):
                    ts_ws.cell(row=r_idx, column=c_idx, value=value)

        wb.save(filename)
        wb.close()

    @classmethod
    def aggregate_performance_metrics(cls, all_metrics: list):
        """Aggregate performance metrics from multiple strategies into summary and time series DataFrames."""
        summary_rows = []
        combined_rows = []
        for metrics, label in all_metrics:
            # Flatten scalar metrics and add label
            row = {"strategy": label}
            for k, v in metrics.items():
                if isinstance(v, (pd.Series, pd.DataFrame)):
                    continue  # skip for now, will handle below
                row[k] = v
            summary_rows.append(row)

            # Expand weights into separate columns and reorder columns
            if "portfolio_weights" in metrics:
                weights_df = pd.DataFrame(metrics["portfolio_weights"].values, columns=metrics["portfolio_weights"].columns)
                weights_df.insert(0, "Date", metrics["portfolio_wealth_factors"].index)
                weights_df["WealthFactor"] = metrics["portfolio_wealth_factors"].values
                weights_df["PortfolioReturns"] = metrics["portfolio_returns"].values
                weights_df["PortfolioTurnover"] = metrics["portfolio_turnover"].values
                weights_df["Strategy"] = label
                df = weights_df
                combined_rows.append(df)

        # Summary table of scalar metrics
        summary_df = pd.DataFrame(summary_rows)

        # Condensed DataFrame of all time series metrics
        if combined_rows:
            all_metrics_df = pd.concat(combined_rows, axis=0, ignore_index=True)
        else:
            all_metrics_df = None

        return summary_df, all_metrics_df
    
    @classmethod
    def calculate_performance_metrics(cls, rebalance_problem, portfolio: Portfolio):
        """Calculate performance metrics for the portfolio."""
        portfolio_weights = portfolio.weights
        portfolio_returns = portfolio.returns
        portfolio_turnover = portfolio.turnover
        wealth_factors = (1 + portfolio_returns).cumprod()
        cumulative_returns = wealth_factors - 1

        # Annualize return: compound final return over time horizon (CAGR)
        num_periods = cumulative_returns.shape[0]
        years = num_periods / cls.WEEKS_PER_YEAR
        annualized_return = wealth_factors.iloc[-1] ** (1 / years) - 1
        
        # Annualize volatility
        annualized_volatility = portfolio_returns.std() * np.sqrt(cls.ANNUAL_TRADING_DAYS[rebalance_problem.trading_frequency])
        
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
            "rolling_returns": cls._calculate_rolling_returns(portfolio_returns, lookback_window, 
                                                             rebalance_problem.trading_frequency),
            "rolling_volatility": cls._calculate_rolling_volatility(portfolio_returns, lookback_window, 
                                                                   rebalance_problem.trading_frequency),
            "rolling_sharpe_ratio": cls._calculate_rolling_sharpe_ratio(portfolio_returns, lookback_window, 
                                                                       rebalance_problem.trading_frequency),
            "rolling_drawdown": cls._calculate_rolling_drawdown(drawdown_returns, lookback_window),
            "portfolio_turnover": portfolio_turnover,
            "cumulative_returns": cumulative_returns,
            "return": annualized_return,
            "volatility": annualized_volatility,
            "sharpe_ratio": sharpe_ratio,
            "max_drawdown": abs(cls._calculate_max_drawdown(drawdown_returns)),
            "turnover": portfolio_turnover.mean() * cls.WEEKS_PER_YEAR,
            "alpha": cls.get_alpha(portfolio_returns, rebalance_problem)
        }
        cls._save_performance_plot(portfolio_returns, wealth_factors, sharpe_ratio, rebalance_problem)
        return performance_metrics
    
    @classmethod
    def _calculate_max_drawdown(cls, cumulative_returns):
        """Calculate maximum drawdown from cumulative returns."""
        running_max = cumulative_returns.cummax()
        drawdown = (cumulative_returns - running_max) / running_max
        return drawdown.min()
    
    @classmethod
    def _calculate_rolling_drawdown(cls, cumulative: pd.Series, window: int):
        """Calculate rolling drawdown series over a specified window."""
        return cumulative.rolling(window).apply(cls._calculate_max_drawdown, raw=False)

    @classmethod 
    def _calculate_rolling_returns(cls, returns: pd.Series, window: int, trading_frequency: str):
        """Calculate rolling return over a specified window."""
        annualization_factor = cls.ANNUAL_TRADING_DAYS.get(trading_frequency, 252)
        rolling_return = (1 + returns).rolling(window=window).apply(np.prod, raw=True) - 1
        rolling_return = (1 + rolling_return) ** (annualization_factor / window) - 1
        return rolling_return

    @classmethod
    def _calculate_rolling_volatility(cls, returns: pd.Series, window: int, trading_frequency: str):
        """Calculate rolling volatility over a specified window."""
        annualization_factor = cls.ANNUAL_TRADING_DAYS.get(trading_frequency, 252)
        rolling_std = returns.rolling(window=window).std()
        rolling_volatility = rolling_std * np.sqrt(annualization_factor)
        return rolling_volatility

    @classmethod
    def _calculate_rolling_sharpe_ratio(cls, returns: pd.Series, window: int, trading_frequency: str):
        """Calculate rolling Sharpe ratio over a specified window."""
        annualization_factor = cls.ANNUAL_TRADING_DAYS.get(trading_frequency, 252)
        rolling_mean = returns.rolling(window=window).mean()
        rolling_std = returns.rolling(window=window).std()
        rolling_sharpe = (rolling_mean / rolling_std) * np.sqrt(annualization_factor)
        return rolling_sharpe
    
    @classmethod
    def _save_performance_plot(cls, portfolio_returns, wealth_factors, sharpe_ratio, rebalance_problem):
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

    @classmethod
    def get_alpha(cls, portfolio_returns, rebalance_problem):
        annual_trading_days = { "d": 252, "w": 52, "m": 12, "q": 4, "y": 1}
        annualization_factor = annual_trading_days.get(rebalance_problem.trading_frequency, 252)
        """Benchmark function to fetch data for given rebalance problem."""
        benchmark = yf.download("^GSPC", \
                        start=rebalance_problem.start_date, end=rebalance_problem.end_date)
        benchmark= benchmark.asfreq(
                rebalance_problem.trading_frequency, method='ffill'
        )
        benchmark_returns = benchmark["Close"].pct_change().fillna(0)

        if(len(benchmark_returns) != len(portfolio_returns)):
            return

        aligned = pd.concat([portfolio_returns, benchmark_returns], axis=1, join='inner')
        aligned.columns = ['portfolio', 'benchmark']

        portfolio_annualized = (1 + aligned['portfolio']).prod() ** (annualization_factor/len(aligned)) - 1
        benchmark_annualized = (1 + aligned['benchmark']).prod() ** (annualization_factor/len(aligned)) - 1
        alpha = portfolio_annualized - benchmark_annualized
        return alpha
