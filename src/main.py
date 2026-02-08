from portfolio.portfolio import Portfolio
from reporting.reporting_module import ReportingSystem
from core.strategies.strategy_factory import StrategyFactory
from backtesting.backtesting_engine import BacktestingEngine
from core.optimizers.optimizer_factory import OptimizerFactory
from portfolio.rebalance_problem_builder import RebalanceProblemBuilder

from multiprocessing import Pool
import multiprocessing
from zipfile import Path
from datetime import date
from pathlib import Path
import json
from itertools import product
from datetime import datetime
import numpy as np

def run_strategy_async(rebalance_problem):
    optimizer = OptimizerFactory.create_optimizer(rebalance_problem.optimizer_type)
    strategy = StrategyFactory.create_strategy(rebalance_problem, optimizer)
    portfolio = Portfolio()
    backtestingEngine = BacktestingEngine(portfolio, strategy)
    backtestingEngine.run_backtest(rebalance_problem)
    return backtestingEngine.portfolio

def create_fwp_rebalance_problem(config):
    rebalance_problem = None
    strat_config = config.copy()
    builder = RebalanceProblemBuilder(strat_config)
    try:
        rebalance_problem = builder.build()
    except ValueError as e:
        print(f"Error building rebalance problem for {strat_config['strategy_type']}: {e}") 

    return rebalance_problem

"""Main entry point for running the backtesting engine with a rebalance problem."""
if __name__ == '__main__':
    strategies = ["mv_strategy"]
    turnover_limits = [0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
    returns = np.linspace(0.21, 0.50, 20)
    rebalance_problems = {}
    combined_metrics = []
    with open(f"src/config/fwp_strategy.json", 'r') as f:
        fwp_config = json.load(f)
    fwp_rebal_problem = create_fwp_rebalance_problem(fwp_config)
    rebalance_problems.update({'fwp_strategy': fwp_rebal_problem})

    for strategy_type, exp_return, turnover_limit in product(strategies, returns, turnover_limits):
        with open(f"src/config/{strategy_type}.json", 'r') as f:
            config = json.load(f)

        strat_config = config.copy()
        strat_config['constraints']['turnover_limit'] = turnover_limit
        strat_config['constraints']['max_return'] =  exp_return
        builder = RebalanceProblemBuilder(strat_config)
        try:
            rebalance_problem = builder.build()
            strategy_type += f"_exp_mu_{str(round(exp_return, 3))}_turn_limit_{str(turnover_limit)}"
            rebalance_problems.update({strategy_type: rebalance_problem})
        except ValueError as e:
            print(f"Error building rebalance problem for {strat_config['strategy_type']}: {e}")
            continue

    max_workers = min(16, multiprocessing.cpu_count())
    with Pool(processes=max_workers) as pool:
        results = [
            (strategy_type, pool.apply_async(run_strategy_async, args=(rebalance_problem,)))
            for strategy_type, rebalance_problem in rebalance_problems.items()
        ]
        for strategy_type, res in results:
            portfolio = res.get()
            if portfolio is None:
                continue

            metric = ReportingSystem.calculate_performance_metrics(rebalance_problems[strategy_type], portfolio)
            combined_metrics.append((metric, strategy_type))

    summary_df, portfolio_metrics_df, rolling_metrics_df = \
        ReportingSystem.aggregate_performance_metrics(combined_metrics)
    
    folder_name = "backtest_results/" + date.today().isoformat()
    path = Path(folder_name)
    path.mkdir(parents=True, exist_ok=True)
    ReportingSystem.generate_report(\
        f"{folder_name}/backtest_report_{config['start_date']}_{config['end_date']}_{datetime.now().strftime("%Y-%m-%d_%H-%M-%S")}.xlsx", 
    {
        "summary": summary_df,
        "time_series": portfolio_metrics_df if len(portfolio_metrics_df) > 0 else None,
        "rolling_time_series": rolling_metrics_df if len(rolling_metrics_df) > 0 else None
    })

    print("Backtesting complete.")