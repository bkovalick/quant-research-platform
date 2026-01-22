import pandas as pd
import numpy as np
from portfolio.rebalance_problem import RebalanceProblem

class RebalanceProblemBuilder:
    """Orchestrates the pipeline to build a RebalanceProblem from input configuration."""
    
    def __init__(self, config: dict):
        """Initialize with configuration dictionary."""
        self.config = config

    def build(self) -> RebalanceProblem:
        """Build and return a RebalanceProblem instance."""
        tickers = [item["ticker"] for item in self.config["rebalance_sub_parameters"]]
        cash_allocation = self.config.get("cash_allocation", 0.0)
        tickers_with_cash = tickers + ["CASH"]
        target_weights = [ item["target_weights"] 
                           for item in self.config["rebalance_sub_parameters"] ] + [cash_allocation]

        initial_weights = [ item["initial_weights"] 
                           for item in self.config["rebalance_sub_parameters"] ] + [cash_allocation]
        
        prepared_data = {
            "tickers": tickers_with_cash,
            "risk_free_rate": self.config["risk_free_rate"],
            "program_type": self.config["program_type"],
            "start_date": self.config["start_date"],
            "end_date": self.config["end_date"],
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
            "trading_buffer": self.config.get("trading_buffer", 0.0),
            "apply_max_return_objective": self.config.get("apply_max_return_objective", False),
            "apply_sharpe_objective": self.config.get("apply_sharpe_objective", False)
        }

        return RebalanceProblem(prepared_data)
