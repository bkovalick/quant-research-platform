from core.strategies.strategy_factory import StrategyFactory
from core.optimizers.optimizer_factory import OptimizerFactory
from portfolio.portfolio import Portfolio
from portfolio.rebalance_problem_builder import RebalanceProblemBuilder
from backtesting.backtesting_engine import BacktestingEngine
from reporting.reporting_module import ReportingSystem

from multiprocessing import Pool
from zipfile import Path
from datetime import date
from pathlib import Path
import json
from itertools import product

"""Main entry point for running the backtesting engine with a rebalance problem."""
if __name__ == '__main__':
    def run_strategy(config):
        strat_config = config.copy()
        builder = RebalanceProblemBuilder(strat_config)
        try:
            rebalance_problem = builder.build()
        except ValueError as e:
            print(f"Error building rebalance problem for {strat_config['strategy_type']}: {e}")
            return None, None
        optimizer = OptimizerFactory.create_optimizer(rebalance_problem.optimizer_type)
        strategy = StrategyFactory.create_strategy(rebalance_problem, optimizer)
        portfolio = Portfolio()
        backtestingEngine = BacktestingEngine(portfolio, strategy)
        backtestingEngine.run_backtest(rebalance_problem)
        return backtestingEngine.portfolio, rebalance_problem

    combined_metrics = []
    
    # strategies = ["mv_strategy"]
    strategies = ["fwp_strategy", "mv_strategy"]
    # turnover_limits = [None, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
    turnover_limits = [None]
    for strategy_type, turnover_limit in product(strategies, turnover_limits):
        with open(f"src/config/{strategy_type}.json", 'r') as f:
            config = json.load(f)
        # config['constraints']['turnover_limit'] = turnover_limit

        portfolio, rebalance_problem = run_strategy(config)
        if portfolio is None:
            continue

        metric = ReportingSystem.calculate_performance_metrics(rebalance_problem, portfolio)
        if turnover_limit is not None:
            strategy_type += f"_turnover_{turnover_limit}"
        combined_metrics.append((metric, strategy_type))

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