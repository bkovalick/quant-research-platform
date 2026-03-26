import abc
import pandas as pd
import numpy as np
from scipy.stats import spearmanr

class BaseSignalMonitor(abc.ABC):
    def __init__(self):
        pass

    def analyze(self) -> dict:
        return {
            "ic_statistics": self._compute_ic_statistics(),
            "half_life": self._compute_half_life()
        }

    @abc.abstractmethod
    def _compute_ic_statistics(self): ...

    @abc.abstractmethod
    def _compute_half_life(self): ...

class SignalDecayMonitor(BaseSignalMonitor):
    def __init__(self, 
                 forward_returns: pd.DataFrame,
                 signal: pd.DataFrame,
                 window: int = 20):
        """Monitors signal decay by computing rolling Information Coefficient and half-life of those signals."""
        super().__init__()

        self.forward_returns = forward_returns
        self.signal = signal
        self.window = window

    def _compute_ic_statistics(self) -> pd.Series:
        """
        Calculates the Information Coefficient (Spearman Rank Correlation) 
        over a rolling window to detect decay.
        """
        ic_values = []
        for date in self.signal.index:
            scores = self.signal.loc[date].dropna()
            fwd_returns = self.forward_returns.loc[date].dropna()
            common = scores.index.intersection(fwd_returns.index)
            if len(common) < 5:
                continue

            ic, _ = spearmanr(scores.loc[common], fwd_returns.loc[common])
            ic_values.append((date, ic))
    
        dates, ics = zip(*ic_values)
        return pd.Series(ics, index=dates)      

    def _compute_half_life(self) -> float:
        """
        Estimate the signal decay half-life from signals using AR(1) autocorrelation.

        Fits a first-order autoregressive model and solves for the number of periods
        it takes for the autocorrelation to decay to half its initial value.
        Returns np.nan when phi is outside (0, 1), i.e. the series is non-stationary,
        mean-reverting with no persistence, or negatively autocorrelated.
        """
        ic_series = self._compute_ic_statistics()
        phi = ic_series.autocorr(lag=1)

        if phi <= 0 or phi >= 1:
            return np.nan

        half_life = np.log(0.5) / np.log(phi)
        return half_life
