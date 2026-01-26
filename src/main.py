from zipfile import Path
from core.strategies.strategy_factory import StrategyFactory
from core.optimizers.optimizer_factory import OptimizerFactory
from portfolio.portfolio import Portfolio
from portfolio.rebalance_problem_builder import RebalanceProblemBuilder
from backtesting.backtesting_engine import BacktestingEngine
from reporting.reporting_module import ReportingSystem
from multiprocessing import Pool
from datetime import date
from pathlib import Path

"""Main entry point for running the backtesting engine with a rebalance problem."""
if __name__ == '__main__':
    config = {
        "rebalance_sub_parameters": [
            {"ticker": "AAPL", "target_weights": 0.222, "initial_weights": 0.222},
            {"ticker": "GOOGL", "target_weights": 0.444, "initial_weights": 0.444},
            {"ticker": "MSFT", "target_weights": 0.333, "initial_weights": 0.333}
        ],
        "risk_free_rate": 0.03,
        "cash_allocation": 0.0,
        "risk_tolerance": 0.10,
        "start_date": "2005-01-01",
        "end_date": "2026-01-15",
        "program_type": "mv_optimizer",
        "trading_frequency": "w",
        "lookback_window": 52 * 5, 
        "first_rebal": 0,
        "apply_windsoring": True,
        "windsor_percentiles": {"lower": 0.05, "upper": 0.95},
        "turnover_limit": 0.075,
        "apply_max_return_objective": True,
        "apply_sharpe_objective": False
    }

    
    constraints = {
        "apply_windsoring": True,
        "windsor_percentiles": {"lower": 0.05, "upper": 0.95},
        "turnover_limit": 0.2,
        "max_position_size": 0.5,
        "max_positions": 10,
        # bounds around how big/small a position can get
    }
    config.update({"model_constraints": constraints})

    strategies = [
        ("Fixed Weights", "fixed_weights"),
        ("MVOptimization", "mv_optimizer")
    ]

    lookback_years = [ 3, 5, 7, 10, 15, 20, 25, 30 ]
    lookback_windows = [52 * years for years in lookback_years]
    trading_frequencies = [ "d", "w", "m", "q", "y" ]

    def run_strategy(label, strategy_type, config):
        strat_config = config.copy()
        strat_config["program_type"] = strategy_type
        builder = RebalanceProblemBuilder(strat_config)
        try:
            rebalance_problem = builder.build()
        except ValueError as e:
            print(f"Error building rebalance problem for {label}: {e}")
            return None, None, None
        optimizer = OptimizerFactory.create_optimizer(rebalance_problem.program_type)
        strategy = StrategyFactory.create_strategy(rebalance_problem, optimizer)
        portfolio = Portfolio()
        backtestingEngine = BacktestingEngine(portfolio, strategy)
        backtestingEngine.run_backtest(rebalance_problem)
        return backtestingEngine.portfolio, rebalance_problem, label

    combined_metrics = []
    for label, strategy_type in strategies:
        portfolio, rebalance_problem, label = run_strategy(label, strategy_type, config)
        if portfolio is None:
            continue

        metric = ReportingSystem.calculate_performance_metrics(rebalance_problem, portfolio)
        combined_metrics.append((metric, label))

    summary_df, portfolio_metrics_df, rolling_metrics_df = \
        ReportingSystem.aggregate_performance_metrics(combined_metrics)
    
    folder_name = "backtest_results/" + date.today().isoformat()
    path = Path(folder_name)
    path.mkdir(parents=True, exist_ok=True)
    ReportingSystem.generate_report(f"{folder_name}/backtest_report_{config['start_date']}_{config['end_date']}.xlsx", {
        "summary": summary_df,
        "time_series": portfolio_metrics_df if len(portfolio_metrics_df) > 0 else None,
        "rolling_time_series": rolling_metrics_df if len(rolling_metrics_df) > 0 else None
    })

    print("Backtesting complete.")


    # with Pool(processes=len(strategies)) as pool:
    #     results = [
    #         pool.apply_async(run_strategy, args=(label, strategy_type, config))
    #         for label, strategy_type in strategies
    #     ]
    #     for res in results:
    #         portfolio, rebalance_problem, label = res.get()
    #         if portfolio is None:
    #             continue

    #         metric = ReportingSystem.calculate_performance_metrics(rebalance_problem, portfolio)
    #         combined_metrics.append((metric, label))

    # summary_df, all_metrics_df = ReportingSystem.aggregate_performance_metrics(combined_metrics)
    # ReportingSystem.generate_report(f"backtest_results/backtest_report_{config['start_date']}_{config['end_date']}.xlsx", {
    #     "summary": summary_df,
    #     "time_series": all_metrics_df if len(all_metrics_df) > 0 else None
    # })

    # print("Backtesting complete.")