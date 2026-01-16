import pandas as pd
import numpy as np
from core.optimizers.optimizer_factory import OptimizerFactory
from portfolio.rebalance_problem_builder import RebalanceProblemBuilder


if __name__ == '__main__':
    config = {
        "rebalance_sub_parameters": [
            {"ticker": "AAPL", "target_weight": 0.3, "initial_holdings": 1000},
            {"ticker": "GOOGL", "target_weight": 0.5, "initial_holdings": 2000},
            {"ticker": "MSFT", "target_weight": 0.2, "initial_holdings": 1500}
        ],
        "risk_free_rate": 0.03,
        "cash_allocation": 0.0,
        "start_date": "2022-01-01",
        "end_date": "2026-01-13",
        "program_type": "maximize_sharpe",
        "trading_frequency": "monthly"
    }
    
    # Build the rebalance problem using the builder
    builder = RebalanceProblemBuilder(config)
    try:
        rebalance_problem = builder.build()
    except Exception as e:
        # Fallback to synthetic data if market fetch fails
        print("Market data fetch failed; using synthetic data:", e)
        dates = pd.date_range(start=config["start_date"], end=config["end_date"], freq='B')
        tickers = [p["ticker"] for p in config["rebalance_sub_parameters"]]
        price_df = pd.DataFrame({t: 100 + np.cumsum(np.random.randn(len(dates)) * 0.5) for t in tickers}, index=dates)
        prepared = {
            "tickers": tickers,
            "price_data": price_df,
            "returns_data": None,
            "mean_vector": None,
            "covariance_matrix": None,
            "risk_free_rate": config["risk_free_rate"],
            "target_weights": [p["target_weight"] for p in config["rebalance_sub_parameters"]],
            "initial_holdings": [p["initial_holdings"] for p in config["rebalance_sub_parameters"]],
            "total_portfolio_value": sum([p["initial_holdings"] for p in config["rebalance_sub_parameters"]]) + config.get("cash_allocation", 0.0),
            "cash_allocation": config.get("cash_allocation", 0.0),
        }
        from portfolio.rebalance_problem import RebalanceProblem
        rebalance_problem = RebalanceProblem(prepared)

    print(f"Portfolio constituents: {rebalance_problem.n_constituents}")
    print(f"Tickers: {rebalance_problem.tickers}")
    print(f"Risk-free rate: {rebalance_problem.risk_free_rate}")

    # Show initial derived statistics
    print("Initial mean vector:\n", rebalance_problem.mean_vector)
    cov = rebalance_problem.covariance_matrix
    print("Initial covariance shape:", None if cov is None else cov.shape)

    # Slice price_data (e.g., last 60 business days) and assign back
    price_df = rebalance_problem.price_data
    if price_df is not None and len(price_df) > 60:
        sliced = price_df.tail(60)
    else:
        sliced = price_df

    if sliced is not None:
        rebalance_problem.price_data = sliced
        print("After slicing price_data (rows):", None if rebalance_problem.price_data is None else len(rebalance_problem.price_data))
        print("Recomputed mean vector:\n", rebalance_problem.mean_vector)
        cov2 = rebalance_problem.covariance_matrix
        print("Recomputed covariance shape:", None if cov2 is None else cov2.shape)

    
    # Optionally run optimizer
    # optimizer = OptimizerFactory.create_optimizer(config["program_type"])
    # optimizer.optimize(rebalance_problem)