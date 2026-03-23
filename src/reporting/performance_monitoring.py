import abc
import pandas as pd
import numpy as np
from scipy.stats import spearmanr

from models.backtest_result import BacktestResult

class PerformanceMonitor(abc.ABC):
    def __init__(self, backtest_results: BacktestResult):
        self.backtest_results = backtest_results

    def analyze(self) -> dict:
        return {
            "ic_statistics": self._compute_ic_statistics(),
            "half_life": self._compute_half_life()
        }

    @abc.abstractmethod
    def _compute_ic_statistics(self):
        pass

    @abc.abstractmethod
    def _compute_half_life(self):
        pass            

class SignalDecayMonitor(PerformanceMonitor):
    def __init__(self, 
                 backtest_results: BacktestResult,
                 signal: pd.Series,
                 window = 20):
        super().__init__(backtest_results)

        self.portfolio_returns = self.backtest_results.series["portfolio_returns"]
        self.signal = signal
        self.window = window

    def _compute_ic_statistics(self) -> pd.Series:
        """
        Calculates the Information Coefficient (Spearman Rank Correlation) 
        over a rolling window to detect decay.
        """
        ic_values = []
        for i in range(self.window, len(self.signal)):
            # Calculate rank correlation between signal(t) and returns(t+1)
            # Use spearmanr to handle non-linear relationships
            ic, _ = spearmanr(self.signal.iloc[i-self.window:i], self.portfolio_returns.iloc[i-self.window:i])
            ic_values.append(ic)
        
        return pd.Series(ic_values, index=self.signal.index[self.window:])        

    def _compute_half_life(self) -> float:
        """
        Estimate the signal decay half-life from portfolio returns using AR(1) autocorrelation.

        Fits a first-order autoregressive model and solves for the number of periods
        it takes for the autocorrelation to decay to half its initial value.
        Returns np.nan when phi is outside (0, 1), i.e. the series is non-stationary,
        mean-reverting with no persistence, or negatively autocorrelated.
        """
        phi = self.portfolio_returns.autocorr(lag=1)

        if phi <= 0 or phi >= 1:
            return np.nan

        half_life = np.log(0.5) / np.log(phi)
        return half_life
