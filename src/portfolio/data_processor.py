import pandas as pd
import numpy as np


class DataProcessor:
    """Handles data transformation and calculations for portfolio data."""
    
    @staticmethod
    def calculate_returns(price_data: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate percentage returns from price data.
        
        Args:
            price_data: DataFrame with price data
            
        Returns:
            DataFrame with percentage returns
        """
        return price_data.pct_change().iloc[1:] * 100
    
    @staticmethod
    def calculate_mean_returns(returns_data: pd.DataFrame) -> np.ndarray:
        """
        Calculate mean returns from returns data.
        
        Args:
            returns_data: DataFrame with returns data
            
        Returns:
            Array of mean returns
        """
        return np.array(returns_data.mean())
    
    @staticmethod
    def calculate_covariance_matrix(returns_data: pd.DataFrame) -> np.ndarray:
        """
        Calculate covariance matrix from returns data.
        
        Args:
            returns_data: DataFrame with returns data
            
        Returns:
            Covariance matrix as numpy array
        """
        return np.cov(returns_data, rowvar=False)
    
    @staticmethod
    def extract_tickers(rebalance_params: list) -> list:
        """
        Extract tickers from rebalance sub-parameters.
        
        Args:
            rebalance_params: List of rebalance sub-parameter dicts
            
        Returns:
            List of ticker symbols
        """
        return [item["ticker"] for item in rebalance_params]
    
    @staticmethod
    def extract_target_weights(rebalance_params: list) -> list:
        """
        Extract target weights from rebalance sub-parameters.
        
        Args:
            rebalance_params: List of rebalance sub-parameter dicts
            
        Returns:
            List of target weights
        """
        return [item["target_weight"] for item in rebalance_params]
    
    @staticmethod
    def extract_initial_holdings(rebalance_params: list) -> list:
        """
        Extract initial holdings from rebalance sub-parameters.
        
        Args:
            rebalance_params: List of rebalance sub-parameter dicts
            
        Returns:
            List of initial holdings
        """
        return [item["initial_holdings"] for item in rebalance_params]
