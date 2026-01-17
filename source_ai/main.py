import pandas as pd
import numpy as np
from core.optimizers.optimizer_factory import OptimizerFactory
from portfolio.rebalance_problem_builder import RebalanceProblemBuilder
from backtesting.backtesting_engine import BacktestingEngine, FixedWeightPortfolio, MaxSharpePortfolio, MeanVariancePortfolio
from backtesting.portfolio import Portfolio

if __name__ == '__main__':
    config = {
        "rebalance_sub_parameters": [
            {"ticker": "AAPL", "target_weight": 0.3, "initial_holdings": 1000},
            {"ticker": "GOOGL", "target_weight": 0.5, "initial_holdings": 2000},
            {"ticker": "MSFT", "target_weight": 0.2, "initial_holdings": 1500}
        ],
        "risk_free_rate": 0.03,
        "cash_allocation": 0.0,
        "risk_tolerance": 0.07,
        "start_date": "2022-01-01",
        "end_date": "2026-01-13",
        "program_type": "maximize_sharpe",
        "trading_frequency": "w",
        "lookback_window": 52,
        "first_rebal": 0
    }

    fwp_config = config.copy()
    fwp_config["program_type"] = "fixed_weights"
    mvc_config = config.copy()
    mvc_config["program_type"] = "mean_variance"

    builder = RebalanceProblemBuilder(config)
    try:
        rebalance_problem = builder.build()
    except ValueError as e:
        print(f"Error building rebalance problem: {e}")
        exit(1)

    optimizer = OptimizerFactory.create_optimizer(config["program_type"])
    portfolio = Portfolio(optimizer=optimizer)
    backtestingEngine = BacktestingEngine(portfolio)
    rebal_port = backtestingEngine.run_backtest(rebalance_problem)
    print(rebal_port)
