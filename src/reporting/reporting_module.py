from openpyxl import Workbook
from openpyxl.utils.dataframe import dataframe_to_rows
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import yfinance as yf

from domain.portfolio.portfolio import Portfolio
from config.lookback_windows import LOOKBACK_WINDOWS
from models.backtest_result import BacktestResult
from models.experiment import Experiment
from models.rebalance_problem import RebalanceProblem

# split out excel report generation.
# create a MetricsComputer class that returns a BacktestResult

class ExcelGenerator:
    def __init__(self, filename: str, experiment: Experiment):
        pass

class JsonGenerator():
    pass

class MetricsCompute:
    def __init__(self):
        pass
        # self.rebalance_problem = rebalance_problem
        # self.trading_frequency = self.rebalance_problem.get("trading_frequency", "y")
        # self.annual_trading_days = LOOKBACK_WINDOWS[self.trading_frequency]
        # self.weeks_per_year = self.annual_trading_days["1y"]

    def generate_report(self, filename: str, results: dict):
        pass
        # wb = Workbook()
        # default_sheet = wb.active
        # wb.remove(default_sheet)
        # if "summary" in results:
        #     summary_ws = wb.create_sheet(title="Summary")
        #     summary_rows = dataframe_to_rows(results["summary"], header=True, index=False)   
        #     for r_idx, row in enumerate(summary_rows, 1):
        #         for c_idx, value in enumerate(row, 1):
        #             summary_ws.cell(row=r_idx, column=c_idx, value=value)

        # if "time_series" in results:
        #     ts_ws = wb.create_sheet(title="Time Series")
        #     ts_rows = dataframe_to_rows(results["time_series"], header=True, index=False)
        #     for r_idx, row in enumerate(ts_rows, 1):
        #         for c_idx, value in enumerate(row, 1):
        #             ts_ws.cell(row=r_idx, column=c_idx, value=value)

        # if "rolling_time_series" in results:
        #     ts_ws = wb.create_sheet(title="Rolling Time Series")
        #     ts_rows = dataframe_to_rows(results["rolling_time_series"], header=True, index=False)
        #     for r_idx, row in enumerate(ts_rows, 1):
        #         for c_idx, value in enumerate(row, 1):
        #             ts_ws.cell(row=r_idx, column=c_idx, value=value)              

        # wb.save(filename)
        # wb.close()

    def compute(self, rebalance_problem: RebalanceProblem, portfolio: Portfolio) -> BacktestResult:
        # build each piece of the backtest result
        self.rebalance_problem = rebalance_problem
        self.trading_frequency = self.rebalance_problem.trading_frequency
        self.lookback_window = self.rebalance_problem.lookback_window
        self.annual_trading_days = LOOKBACK_WINDOWS[self.trading_frequency]
        self.weeks_per_year = self.annual_trading_days[self.lookback_window]
        return BacktestResult({}, {}, [], {})
    
    def aggregate_performance_metrics(self, all_metrics):
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
                weights_df.insert(0, "Date", pd.to_datetime(metrics["portfolio_wealth_factors"].index))
                weights_df.insert(1, "Strategy", label)
                weights_df.insert(2, "WealthFactor", metrics["portfolio_wealth_factors"].values)
                weights_df.insert(3, "PortfolioReturns", metrics["portfolio_returns"].values)
                weights_df.insert(4, "PortfolioTurnover", metrics["portfolio_turnover"].values)
                portfolio_dfs.append(weights_df)

            if "rolling_returns" in metrics:
                rolling_df = pd.DataFrame({
                    "Date": pd.to_datetime(metrics["rolling_returns"].index),
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

    def calculate_performance_metrics(self, rebalance_problem: RebalanceProblem, portfolio: Portfolio):
        """Calculate performance metrics for the portfolio."""
        portfolio_weights = portfolio.weights
        portfolio_returns = portfolio.returns
        portfolio_turnover = portfolio.turnover
        wealth_factors = (1 + portfolio_returns).cumprod()
        cumulative_returns = wealth_factors - 1
        num_periods = cumulative_returns.shape[0]
        years = num_periods / self.weeks_per_year
        annualized_return = wealth_factors.iloc[-1] ** (1 / years) - 1
        annualized_volatility = portfolio_returns.std() * np.sqrt(self.annual_trading_days[self.trading_frequency])

        sharpe_ratio = (
            annualized_return / annualized_volatility 
            if annualized_volatility != 0 else 0.0
        )

        lookback_window = getattr(rebalance_problem, 'lookback_window', 0)
        if lookback_window > 0:
            drawdown_returns = cumulative_returns.iloc[lookback_window:]
            rolling_dd = self._calculate_rolling_drawdown(drawdown_returns, lookback_window)
            rolling_dd = align_series_to_dataframe(cumulative_returns.copy(), rolling_dd)
        else:
            drawdown_returns = cumulative_returns
            rolling_dd = self._calculate_rolling_drawdown(drawdown_returns, lookback_window)
            rolling_dd = align_series_to_dataframe(cumulative_returns.copy(), rolling_dd)

        performance_metrics = {
            "portfolio_wealth_factors": wealth_factors,
            "portfolio_weights": portfolio_weights,
            "portfolio_returns": portfolio_returns,
            "portfolio_turnover": portfolio_turnover,
            "cumulative_returns": cumulative_returns,            
            "rolling_returns": self._calculate_rolling_returns(portfolio_returns, lookback_window, 
                                                             self.trading_frequency),
            "rolling_volatility": self._calculate_rolling_volatility(portfolio_returns, lookback_window, 
                                                                   self.trading_frequency),
            "rolling_sharpe_ratio": self._calculate_rolling_sharpe_ratio(portfolio_returns, lookback_window, 
                                                                       self.trading_frequency),
            "rolling_drawdown": rolling_dd,
            "rolling_turnover": self._calculate_rolling_turnover(portfolio_turnover, lookback_window, 
                                                                self.trading_frequency),
            "return": annualized_return,
            "volatility": annualized_volatility,
            "sharpe_ratio": sharpe_ratio,
            "max_drawdown": abs(self._calculate_max_drawdown(drawdown_returns)),
            "turnover": portfolio_turnover.mean() * self.weeks_per_year,
            "alpha": self.get_alpha(portfolio_returns, rebalance_problem)
        }
        return performance_metrics

    def _calculate_max_drawdown(self, cumulative_returns: pd.Series):
        """Calculate maximum drawdown from cumulative returns."""
        running_max = cumulative_returns.cummax()
        drawdown = (cumulative_returns - running_max) / running_max
        return drawdown.min()

    def _calculate_rolling_drawdown(self, cumulative: pd.Series, window: int):
        """Calculate rolling drawdown series over a specified window."""
        return cumulative.rolling(window, min_periods=1).apply(self._calculate_max_drawdown, raw=False)

    def _calculate_rolling_returns(self, returns: pd.Series, window: int, trading_frequency: str):
        """Calculate rolling return over a specified window."""
        annualization_factor = self.annual_trading_days.get(trading_frequency, 252)
        rolling_return = (1 + returns).rolling(window=window).apply(np.prod, raw=True) - 1
        rolling_return = (1 + rolling_return) ** (annualization_factor / window) - 1
        return rolling_return

    def _calculate_rolling_volatility(self, returns: pd.Series, window: int, trading_frequency: str):
        """Calculate rolling volatility over a specified window."""
        annualization_factor = self.annual_trading_days.get(trading_frequency, 252)
        rolling_std = returns.rolling(window=window).std()
        rolling_volatility = rolling_std * np.sqrt(annualization_factor)
        return rolling_volatility

    def _calculate_rolling_sharpe_ratio(self, returns: pd.Series, window: int, trading_frequency: str):
        """Calculate rolling Sharpe ratio over a specified window."""
        annualization_factor = self.annual_trading_days.get(trading_frequency, 252)
        rolling_mean = returns.rolling(window=window).mean()
        rolling_std = returns.rolling(window=window).std()
        rolling_sharpe = (rolling_mean / rolling_std) * np.sqrt(annualization_factor)
        return rolling_sharpe

    def _calculate_rolling_turnover(self, turnover: pd.Series, window: int, trading_frequency: str):
        """Calculate rolling turnover over a specified window."""
        annualization_factor = self.annual_trading_days.get(trading_frequency, 252)
        return turnover.rolling(window=window).mean() * np.sqrt(annualization_factor)

    def get_alpha(self, portfolio_returns, rebalance_problem):
        """Calculate alpha of the portfolio against a benchmark (S&P 500)."""
        annualization_factor = self.annual_trading_days.get(rebalance_problem.trading_frequency, 252)
        benchmark = yf.download("^GSPC", \
                        start=rebalance_problem.start_date, end=rebalance_problem.end_date)
        freq = 'W' if self.trading_frequency == 'w' else self.trading_frequency
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

    def get_benchmark(self, rebalance_problem: RebalanceProblem):
        benchmark_data = {}
        freq = 'W' if self.trading_frequency == 'w' else self.trading_frequency
        benchmark_universe = rebalance_problem.get("benchmark_universe", "SPY")
        benchmark = yf.download(benchmark_universe, start=rebalance_problem.start_date, end=rebalance_problem.end_date)
        benchmark = benchmark.asfreq(freq, method='ffill')
        benchmark_data.update({"benchmark_returns": benchmark["Close"].pct_change().fillna(0)})
        benchmark_data.update({"benchmark_wfs": benchmark / benchmark.iloc[0] })
        return benchmark_data
    
def align_series_to_dataframe(df, series):
    n = len(df) - len(series)
    nan_part = pd.Series([np.nan]*n, index=df.index[:n])
    aligned = pd.concat([nan_part, series])
    aligned = aligned.reindex(df.index)
    return aligned