import pandas as pd
import numpy as np

class PortfolioCalculations:
    @staticmethod
    def calculate_returns(price_data: pd.DataFrame) -> pd.DataFrame:
        return price_data.pct_change().iloc[1:]

    @staticmethod
    def calculate_mean_returns(returns_data: pd.DataFrame) -> np.ndarray:
        return np.array(returns_data.mean())

    @staticmethod
    def calculate_covariance_matrix(returns_data: pd.DataFrame) -> np.ndarray:
        return np.cov(returns_data, rowvar=False)

    @staticmethod
    def extract_tickers(rebalance_params: list) -> list:
        return [item["ticker"] for item in rebalance_params]

    @staticmethod
    def extract_target_weights(rebalance_params: list) -> list:
        return [item["target_weight"] for item in rebalance_params]

    @staticmethod
    def extract_initial_holdings(rebalance_params: list) -> list:
        return [item["initial_holdings"] for item in rebalance_params]
