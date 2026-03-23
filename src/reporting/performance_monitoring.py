import abc
import pandas as pd
import numpy as np
from scipy.stats import spearmanr

from models.backtest_result import BacktestResult

class PerformanceMonitor(abc.ABC):
    def __init__(self, backtest_results: BacktestResult):
        self.backtest_results = backtest_results

    def check(self):
        self._compute_ic_statistics()
        self._compute_half_life()

    @abc.abstractmethod
    def _compute_ic_statistics(self):
        pass

    @abc.abstractmethod
    def _compute_half_life(self):
        pass            

class SignalDecay(PerformanceMonitor):
    def __init__(self, backtest_results: BacktestResult):
        super().__init__(backtest_results)

    def check(self): pass

    def _compute_ic_statistics(self):
        pass

    def _compute_half_life(self):
        pass
