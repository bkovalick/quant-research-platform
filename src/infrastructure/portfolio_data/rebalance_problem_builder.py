import pandas as pd
import numpy as np

from infrastructure.market_data.marketdatagateway import MarketDataGateway
from infrastructure.portfolio_data.data_processor import DataProcessor
from infrastructure.portfolio_data.rebalance_problem import RebalanceProblem


class RebalanceProblemBuilder:
    """Orchestrates the pipeline to build a RebalanceProblem from input configuration."""
    
    def __init__(self, config: dict):
        """
        Initialize the builder with configuration.
        
        Args:
            config: Dictionary containing rebalance configuration with keys:
                - rebalance_sub_parameters: List of portfolio constituent configs
                - risk_free_rate: Risk-free rate for optimization
                - cash_allocation: (optional) Additional cash allocation
        """
        self.config = config
        self.market_data_gateway = MarketDataGateway()
        self.data_processor = DataProcessor()
    
    def build(self) -> RebalanceProblem:
        """
        Build and return a RebalanceProblem by executing the full pipeline.
        
        Returns:
            RebalanceProblem instance with all data prepared and calculations done
        """
        # Extract tickers from configuration
        tickers = self.data_processor.extract_tickers(
            self.config["rebalance_sub_parameters"]
        )
        
        # Fetch market data
        price_data = self.market_data_gateway.get_price_data(tickers)
        price_df = pd.DataFrame(price_data)
        
        # Transform data
        returns_data = self.data_processor.calculate_returns(price_df)
        mean_returns = self.data_processor.calculate_mean_returns(returns_data)
        covariance_matrix = self.data_processor.calculate_covariance_matrix(returns_data)
        
        # Extract other parameters
        target_weights = self.data_processor.extract_target_weights(
            self.config["rebalance_sub_parameters"]
        )
        initial_holdings = self.data_processor.extract_initial_holdings(
            self.config["rebalance_sub_parameters"]
        )
        
        # Calculate total portfolio value
        total_portfolio_value = sum(initial_holdings) + self.config.get("cash_allocation", 0.0)
        
        # Create prepared data dict
        prepared_data = {
            "tickers": tickers,
            "price_data": price_df,
            "returns_data": returns_data,
            "mean_vector": mean_returns,
            "covariance_matrix": covariance_matrix,
            "risk_free_rate": self.config["risk_free_rate"],
            "target_weights": target_weights,
            "initial_holdings": initial_holdings,
            "total_portfolio_value": total_portfolio_value,
            "cash_allocation": self.config.get("cash_allocation", 0.0),
        }
        
        return RebalanceProblem(prepared_data)
