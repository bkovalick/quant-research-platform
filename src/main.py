import pandas as pd
import numpy as np
from core.optimizers.optimizer_factory import OptimizerFactory
from portfolio.portfolio import Portfolio
from portfolio.rebalance_problem_builder import RebalanceProblemBuilder
from backtesting.backtesting_engine import BacktestingEngine

"""Main entry point for running the backtesting engine with a rebalance problem."""
if __name__ == '__main__':
    config = {
        "rebalance_sub_parameters": [
            {"ticker": "AAPL", "target_weight": 0.3, "initial_weights": 0.222},
            {"ticker": "GOOGL", "target_weight": 0.5, "initial_weights": 0.444},
            {"ticker": "MSFT", "target_weight": 0.2, "initial_weights": 0.333}
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

    strategies = [
        ("Fixed Weights", "fixed_weights"),
        ("Max Sharpe", "maximize_sharpe"),
        ("Mean Variance", "mean_variance")
    ]

    summary_rows = []
    all_metrics = []

    for label, program_type in strategies:
        strat_config = config.copy()
        strat_config["program_type"] = program_type
        builder = RebalanceProblemBuilder(strat_config)
        try:
            rebalance_problem = builder.build()
        except ValueError as e:
            print(f"Error building rebalance problem for {label}: {e}")
            continue
        optimizer = OptimizerFactory.create_optimizer(program_type)
        portfolio = Portfolio(optimizer=optimizer)
        backtestingEngine = BacktestingEngine(portfolio)
        metrics = backtestingEngine.run_backtest(rebalance_problem)
        # Flatten scalar metrics and add label
        row = {"strategy": label}
        for k, v in metrics.items():
            if isinstance(v, (pd.Series, pd.DataFrame)):
                continue  # skip for now, will handle below
            row[k] = v
        summary_rows.append(row)
        # Add DataFrame/Series metrics with strategy label as a column
        for k, v in metrics.items():
            if isinstance(v, pd.Series):
                df = v.to_frame(name=k)
                df["strategy"] = label
                all_metrics.append(df.reset_index())
            elif isinstance(v, pd.DataFrame):
                v = v.copy()
                v["strategy"] = label
                all_metrics.append(v.reset_index())

    # Summary table of scalar metrics
    summary_df = pd.DataFrame(summary_rows)
    print("\nSummary Table (Scalars):")
    print(summary_df)

    # # Condensed DataFrame of all time series metrics
    # if all_metrics:
    #     all_metrics_df = pd.concat(all_metrics, axis=0, ignore_index=True)
    #     print("\nAll Time Series Metrics (Condensed):")
    #     print(all_metrics_df.head())
    # else:
    #     print("No time series metrics to display.")

    print("Backtesting complete.")
