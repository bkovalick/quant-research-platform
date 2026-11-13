from abc import ABC, abstractmethod
import pandas as pd
import numpy as np

class ReturnPredictor(ABC):
    """Interface for cross-sectional return prediction models."""

    @abstractmethod
    def fit(self, X: pd.DataFrame | np.ndarray, y: pd.Series | np.ndarray) -> None:
        """
        Train on historical cross-sectional data.
        X: (n_samples, n_features) — one row per asset per date
        y: (n_samples,)            — forward return for each asset
        Arrays must be row-aligned; a DataFrame/Series pair is aligned on index.
        """
        ...

    @abstractmethod
    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """
        Predict return scores for current cross-section.
        X: (n_assets, n_features)
        Returns: (n_assets,) array of predicted scores
        """
        ...