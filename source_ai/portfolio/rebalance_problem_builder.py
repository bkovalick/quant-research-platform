import pandas as pd
import numpy as np
from infrastructure.market_data.marketdatagateway import MarketDataGateway
from portfolio.portfolio_calculations import PortfolioCalculations
from portfolio.rebalance_problem import RebalanceProblem

class RebalanceProblemBuilder:
    def __init__(self, config: dict):
        self.config = config
        self.market_data_gateway = MarketDataGateway()
        self.portfolio_calculations = PortfolioCalculations()

    def build(self) -> RebalanceProblem:
        tickers = self.portfolio_calculations.extract_tickers(
            self.config["rebalance_sub_parameters"]
        )
        start_date = self.config["start_date"]
        end_date = self.config["end_date"]
        price_df = self.market_data_gateway.get_price_data(tickers, start_date, end_date)
        returns_data = self.portfolio_calculations.calculate_returns(price_df)
        cumulative_returns = (1 + returns_data).cumprod() - 1
        mean_returns = self.portfolio_calculations.calculate_mean_returns(returns_data)
        covariance_matrix = self.portfolio_calculations.calculate_covariance_matrix(returns_data)
        target_weights = self.portfolio_calculations.extract_target_weights(
            self.config["rebalance_sub_parameters"]
        )
        initial_holdings = self.portfolio_calculations.extract_initial_holdings(
            self.config["rebalance_sub_parameters"]
        )
        initial_weights = [holding / sum(initial_holdings) for holding in initial_holdings]
        total_portfolio_value = sum(initial_holdings) + self.config.get("cash_allocation", 0.0)
        prepared_data = {
            "tickers": tickers,
            "price_data": price_df,
            "returns_data": returns_data,
            "cumulative_returns": cumulative_returns,
            "mean_vector": mean_returns,
            "covariance_matrix": covariance_matrix,
            "risk_free_rate": self.config["risk_free_rate"],
            "target_weights": target_weights,
            "initial_holdings": initial_holdings,
            "initial_weights": initial_weights,
            "total_portfolio_value": total_portfolio_value,
            "cash_allocation": self.config.get("cash_allocation", 0.0),
            "risk_tolerance": self.config.get("risk_tolerance", 0.0),
            "trading_frequency": self.config.get("trading_frequency", "d"),
            "lookback_window": self.config.get("lookback_window", 252),
            "first_rebal": self.config.get("first_rebal", 0)
        }
        return RebalanceProblem(prepared_data)
