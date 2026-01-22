import pandas as pd
import numpy as np

from infrastructure.market_data.marketdatagateway import MarketDataGateway
from portfolio.portfolio_calculations import PortfolioCalculations
from portfolio.rebalance_problem import RebalanceProblem

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
        self.portfolio_calculations = PortfolioCalculations()
    

    def build(self) -> RebalanceProblem:
        """
        Build and return a RebalanceProblem by executing the full pipeline.
        Adds a cash column to price_data (all 1s) and a cash component to portfolios.
        """
        # Extract tickers from configuration
        tickers = self.portfolio_calculations.extract_tickers(
            self.config["rebalance_sub_parameters"]
        )

        # Fetch market data
        start_date = self.config["start_date"]
        end_date = self.config["end_date"]
        price_df = self.market_data_gateway.get_price_data(tickers, start_date, end_date)

        # Add cash column (all 1s)
        cash_allocation = self.config.get("cash_allocation", 0.0)
        price_df["CASH"] = 1.0
        tickers_with_cash = tickers + ["CASH"]

        # Transform data
        returns_data = self.portfolio_calculations.calculate_returns(price_df)
        cumulative_returns = (1 + returns_data).cumprod() - 1
        mean_returns = self.portfolio_calculations.calculate_mean_returns(returns_data)
        covariance_matrix = self.portfolio_calculations.calculate_covariance_matrix(returns_data)

        # Extract other parameters and add cash component (weight 0)
        target_weights = self.portfolio_calculations.extract_target_weights(
            self.config["rebalance_sub_parameters"]
        ) + [cash_allocation]
        initial_weights = self.portfolio_calculations.extract_initial_weights(
            self.config["rebalance_sub_parameters"]
        ) + [cash_allocation]

        # Create prepared data dict
        prepared_data = {
            "tickers": tickers_with_cash,
            "price_data": price_df,
            "returns_data": returns_data,
            "cumulative_returns": cumulative_returns,
            "mean_vector": mean_returns,
            "covariance_matrix": covariance_matrix,
            "risk_free_rate": self.config["risk_free_rate"],
            "program_type": self.config["program_type"],
            "start_date": start_date,
            "end_date": end_date,
            "target_weights": target_weights,
            "initial_weights": initial_weights,
            "cash_allocation": cash_allocation,
            "risk_tolerance": self.config.get("risk_tolerance", 0.0),
            "trading_frequency": self.config.get("trading_frequency", "d"),
            "lookback_window": self.config.get("lookback_window", 252),
            "first_rebal": self.config.get("first_rebal", 0),
            "model_constraints": self.config.get("model_constraints", {}),
            "apply_windsoring": self.config.get("apply_windsoring", True),
            "windsor_percentiles": self.config.get("windsor_percentiles", {"lower": 0.05, "upper": 0.95}),
            "trading_buffer": self.config.get("trading_buffer", 0.0)
        }

        return RebalanceProblem(prepared_data)
