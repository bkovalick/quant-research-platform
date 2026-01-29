import pandas as pd
import numpy as np
from portfolio.rebalance_problem import RebalanceProblem

class RebalanceProblemBuilder:
    """Orchestrates the pipeline to build a RebalanceProblem from input configuration."""
    @staticmethod
    def get_lookback_window_mapping():
        """Return mapping of lookback windows for different frequencies and periods."""
        return {
            "d": {"1m": 21, "3m": 63, "6m": 126, "9m": 189, "1y": 252, "5y": 252*5, "10y": 252*10, "20y": 252*20, "30y": 252*30},
            "w": {"1m": 4, "3m": 12, "6m": 26, "9m": 39, "1y": 52, "5y": 52*5, "10y": 52*10, "20y": 52*20, "30y": 52*30},
            "m": {"1m": 1, "3m": 3, "6m": 6, "9m": 9, "1y": 12, "5y": 12*5, "10y": 12*10, "20y": 12*20, "30y": 12*30},
            "q": {"3m": 1, "6m": 2, "9m": 3, "1y": 4, "5y": 4*5, "10y": 4*10, "20y": 4*20, "30y": 4*30},
            "y": {"1y": 1, "5y": 5, "10y": 10, "20y": 20, "30y": 30},
        }

    def __init__(self, config: dict):
        """Initialize with configuration dictionary."""
        self.config = config

    def build(self) -> RebalanceProblem:
        """Build and return a RebalanceProblem instance."""
        tickers = [item["ticker"] for item in self.config["rebalance_sub_parameters"]]
        cash_allocation = self.config.get("cash_allocation", 0.0)
        tickers_with_cash = tickers + ["CASH"]
        initial_weights = [ item["initial_weights"] 
                           for item in self.config["rebalance_sub_parameters"] ] + [cash_allocation]
        lookback_window = self.config.get("lookback_window", "1y")
        trading_frequency = self.config.get("trading_frequency", "d")
        
        prepared_data = {
            "tickers": tickers_with_cash,
            "risk_free_rate": self.config["risk_free_rate"],
            "optimizer_type": self.config.get("optimizer_type"),
            "strategy_type": self.config.get("strategy_type"),
            "apply_max_return_objective": self.config.get("apply_max_return_objective", False),
            "apply_sharpe_objective": self.config.get("apply_sharpe_objective", False),
            "start_date": self.config["start_date"],
            "end_date": self.config["end_date"],
            "initial_weights": initial_weights,
            "cash_allocation": cash_allocation,
            "risk_tolerance": self.config.get("risk_tolerance", 0.0),
            "trading_frequency": trading_frequency,
            "lookback_window": self.get_lookback_window_mapping()[trading_frequency][lookback_window],
            "first_rebal": self.config.get("first_rebal", 0),
            "apply_windsoring": self.config["constraints"].get("apply_windsoring", True),
            "windsor_percentiles": self.config["constraints"].get("windsor_percentiles", \
                                                                  {"lower": 0.05, "upper": 0.95}),
            "turnover_limit": self.config["constraints"].get("turnover_limit", None),
            "max_position_size": self.config["constraints"].get("max_position_size", None),
            "max_number_of_positions": self.config["constraints"].get("max_number_of_positions", None),
            "asset_class_constraints": self.config["constraints"].get("asset_class_constraints", None),
            "sector_constraints": self.config["constraints"].get("sector_constraints", None)
        }

        return RebalanceProblem(prepared_data)
