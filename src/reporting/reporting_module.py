from openpyxl import Workbook
from openpyxl.utils.dataframe import dataframe_to_rows
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import yfinance as yf

from portfolio.portfolio import Portfolio

def align_series_to_dataframe(df, series, col_name):
    """
        Add a (possibly shorter) series to a DataFrame, aligning valid values at the end.
        NaNs will be at the top if the series is shorter than the DataFrame.
    """
    n = len(df) - len(series)
    nan_part = pd.Series([np.nan]*n, index=df.index[:n])
    aligned = pd.concat([nan_part, series])
    aligned = aligned.reindex(df.index)
    return aligned

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

        if "rolling_time_series" in results:
            ts_ws = wb.create_sheet(title="Rolling Time Series")
            ts_rows = dataframe_to_rows(results["rolling_time_series"], header=True, index=False)
            for r_idx, row in enumerate(ts_rows, 1):
                for c_idx, value in enumerate(row, 1):
                    ts_ws.cell(row=r_idx, column=c_idx, value=value)              

        wb.save(filename)
        wb.close()

    @classmethod
    def aggregate_performance_metrics(cls, all_metrics: list):
        """Aggregate performance metrics from multiple strategies into summary and time series DataFrames."""
        summary_rows = []
        portfolio_dfs = []
        rolling_dfs = []
        for metrics, label in all_metrics:
            row = {"strategy": label}
            for k, v in metrics.items():
                if isinstance(v, (pd.Series, pd.DataFrame)):
                    continue 
                row[k] = v
            summary_rows.append(row)

            if "portfolio_weights" in metrics:
                weights_df = pd.DataFrame(metrics["portfolio_weights"].values, columns=metrics["portfolio_weights"].columns)
                weights_df.insert(0, "Date", metrics["portfolio_wealth_factors"].index)
                weights_df.insert(1, "Strategy", label)
                weights_df["WealthFactor"] = metrics["portfolio_wealth_factors"].values
                weights_df["PortfolioReturns"] = metrics["portfolio_returns"].values
                weights_df["PortfolioTurnover"] = metrics["portfolio_turnover"].values
                portfolio_dfs.append(weights_df)

            if "rolling_returns" in metrics:
                rolling_df = pd.DataFrame({
                    "Date": metrics["rolling_returns"].index,
                    "Strategy": label,
                    "RollingReturns": metrics["rolling_returns"].values,
                    "RollingVolatility": metrics["rolling_volatility"].values,
                    "RollingSharpe": metrics["rolling_sharpe_ratio"].values,
                    "RollingDrawdown": metrics["rolling_drawdown"].values,
                    "RollingTurnover": metrics["rolling_turnover"].values                    
                })
                rolling_dfs.append(rolling_df)

        summary_df = pd.DataFrame(summary_rows)
        if portfolio_dfs:
            portfolio_metrics_df = pd.concat(portfolio_dfs, axis=0, ignore_index=True)
        else:
            portfolio_metrics_df = None

        if rolling_dfs:
            rolling_metrics_df = pd.concat(rolling_dfs, axis=0, ignore_index=True)
        else:
            rolling_metrics_df = None

        return summary_df, portfolio_metrics_df, rolling_metrics_df
    
    @classmethod
    def calculate_performance_metrics(cls, rebalance_problem, portfolio: Portfolio):
        """Calculate performance metrics for the portfolio."""
        portfolio_weights = portfolio.weights
        portfolio_returns = portfolio.returns
        portfolio_turnover = portfolio.turnover
        wealth_factors = (1 + portfolio_returns).cumprod()
        cumulative_returns = wealth_factors - 1
        num_periods = cumulative_returns.shape[0]
        years = num_periods / cls.WEEKS_PER_YEAR
        annualized_return = wealth_factors.iloc[-1] ** (1 / years) - 1
        annualized_volatility = portfolio_returns.std() * np.sqrt(cls.ANNUAL_TRADING_DAYS[rebalance_problem.trading_frequency])

        sharpe_ratio = (
            annualized_return / annualized_volatility 
            if annualized_volatility != 0 else 0.0
        )

        lookback_window = getattr(rebalance_problem, 'lookback_window', 0)
        if lookback_window > 0:
            drawdown_returns = cumulative_returns.iloc[lookback_window:]
            rolling_dd = cls._calculate_rolling_drawdown(drawdown_returns, lookback_window)
            rolling_dd = align_series_to_dataframe(cumulative_returns.copy(), rolling_dd, "RollingDrawdown")
        else:
            drawdown_returns = cumulative_returns
            rolling_dd = cls._calculate_rolling_drawdown(drawdown_returns, lookback_window)
            rolling_dd = align_series_to_dataframe(cumulative_returns.copy(), rolling_dd, "RollingDrawdown")

        performance_metrics = {
            "portfolio_wealth_factors": wealth_factors,
            "portfolio_weights": portfolio_weights,
            "portfolio_returns": portfolio_returns,
            "portfolio_turnover": portfolio_turnover,
            "cumulative_returns": cumulative_returns,            
            "rolling_returns": cls._calculate_rolling_returns(portfolio_returns, lookback_window, 
                                                             rebalance_problem.trading_frequency),
            "rolling_volatility": cls._calculate_rolling_volatility(portfolio_returns, lookback_window, 
                                                                   rebalance_problem.trading_frequency),
            "rolling_sharpe_ratio": cls._calculate_rolling_sharpe_ratio(portfolio_returns, lookback_window, 
                                                                       rebalance_problem.trading_frequency),
            "rolling_drawdown": rolling_dd,
            "rolling_turnover": cls._calculate_rolling_turnover(portfolio_turnover, lookback_window, 
                                                                rebalance_problem.trading_frequency),
            "return": annualized_return,
            "volatility": annualized_volatility,
            "sharpe_ratio": sharpe_ratio,
            "max_drawdown": abs(cls._calculate_max_drawdown(drawdown_returns)),
            "turnover": portfolio_turnover.mean() * cls.WEEKS_PER_YEAR,
            "alpha": cls.get_alpha(portfolio_returns, rebalance_problem)
        }
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
        return cumulative.rolling(window, min_periods=1).apply(cls._calculate_max_drawdown, raw=False)

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
    def _calculate_rolling_turnover(cls, turnover: pd.Series, window: int, trading_frequency: str):
        """Calculate rolling turnover over a specified window."""
        annualization_factor = cls.ANNUAL_TRADING_DAYS.get(trading_frequency, 252)
        return turnover.rolling(window=window).mean() * np.sqrt(annualization_factor)
    
    @classmethod
    def get_alpha(cls, portfolio_returns, rebalance_problem):
        """Calculate alpha of the portfolio against a benchmark (S&P 500)."""
        annual_trading_days = { "d": 252, "w": 52, "m": 12, "q": 4, "y": 1}
        annualization_factor = annual_trading_days.get(rebalance_problem.trading_frequency, 252)
        """Benchmark function to fetch data for given rebalance problem."""
        benchmark = yf.download("^GSPC", \
                        start=rebalance_problem.start_date, end=rebalance_problem.end_date)
        freq = rebalance_problem.trading_frequency

        if freq == 'w':
            freq = 'W'
        benchmark = benchmark.asfreq(freq, method='ffill')
        benchmark_returns = benchmark["Close"].pct_change().fillna(0)

        if(len(benchmark_returns) != len(portfolio_returns)):
            return

        aligned = pd.concat([portfolio_returns, benchmark_returns], axis=1, join='inner')
        aligned.columns = ['portfolio', 'benchmark']

        portfolio_annualized = (1 + aligned['portfolio']).prod() ** (annualization_factor/len(aligned)) - 1
        benchmark_annualized = (1 + aligned['benchmark']).prod() ** (annualization_factor/len(aligned)) - 1
        alpha = portfolio_annualized - benchmark_annualized
        return alpha