import pandas as pd
import numpy as np
from core.optimizers.maximize_sharp_optimizer.maximize_sharpe import MaximizeSharpeOptimizer
from portfolio.rebalance_problem_builder import RebalanceProblemBuilder


if __name__ == '__main__':
    config = {
        "rebalance_sub_parameters": [
            {"ticker": "AAPL", "target_weight": 0.3, "initial_holdings": 1000},
            {"ticker": "GOOGL", "target_weight": 0.5, "initial_holdings": 2000},
            {"ticker": "MSFT", "target_weight": 0.2, "initial_holdings": 1500}
        ],
        "risk_free_rate": 0.03,
        "cash_allocation": 0.0
    }
    
    # Build the rebalance problem using the builder
    builder = RebalanceProblemBuilder(config)
    rebalance_problem = builder.build()
    
    print(f"Portfolio constituents: {rebalance_problem.n_constituents}")
    print(f"Tickers: {rebalance_problem.tickers}")
    print(f"Risk-free rate: {rebalance_problem.risk_free_rate}")
