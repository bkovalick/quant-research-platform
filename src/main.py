from domain.portfolio.portfolio import Portfolio
from reporting.reporting_module import MetricsCompute
from simulation.backtesting_engine import BacktestingEngine
from simulation.market_state import MarketState
from services.strategy_factory import StrategyFactory
from services.optimizer_factory import OptimizerFactory
from services.rebalance_problem_builder import RebalanceProblemBuilder
from models.strategy_run import StrategyRun
from models.backtest_result import BacktestResult
from models.experiment import Experiment
from models.market_config import MarketStateConfig, MarketStoreConfig
from data.market_data_gateway import MarketDataStore

from multiprocessing import Pool
import multiprocessing
from zipfile import Path
from datetime import date
from pathlib import Path
import json
from itertools import product
from datetime import datetime
import numpy as np
import uuid

def run_strategy_async(rebalance_problem):
    mkt_state = create_market_state(market_store)
    opt_type = rebalance_problem.optimizer_type
    optimizer = OptimizerFactory.create_optimizer(opt_type)
    strategy = StrategyFactory.create_strategy(rebalance_problem, optimizer)
    portfolio = Portfolio()
    backtestingEngine = BacktestingEngine(portfolio, strategy, mkt_state)
    backtestedPortfolio = backtestingEngine.run_backtest(rebalance_problem)
    return backtestedPortfolio

def create_fwp_rebalance_problem(config):
    rebalance_problem = None
    strat_config = config.copy()
    builder = RebalanceProblemBuilder(strat_config) 
    try:
        rebalance_problem = builder.build()
    except ValueError as e:
        print(f"Error building rebalance problem for {strat_config['strategy_type']}: {e}") 

    return rebalance_problem

market_store = MarketStoreConfig(
    tickers = [
        'AAPL', 'NVDA', 'MSFT', 'TSLA'
    ],        
    start_date = "2005-01-01",
    end_date = "2026-02-13",
    data_source="yfinance"
)

def create_market_state(market_store):
    market_state_config = MarketStateConfig(
        trading_frequency = "w",
        lookback_window = "1y",
        apply_winsorizing = True,
        windsor_percentiles = {"lower": 0.05, "upper": 0.95}
    )
    mkt_store = MarketDataStore(market_store)
    mkt_state = MarketState(mkt_store, market_state_config)
    return mkt_state

"""Main entry point for running the backtesting engine with a rebalance problem."""
if __name__ == '__main__':
    strategies = ["mv_strategy"]
    # risk_tolerances = [1.0, 2.0, 3.0]
    risk_tolerances = [1]
    # concentration_strengths = [0.1, 0.5, 1, 5, 10]
    concentration_strengths = [10]
    rebalance_problems = {}
    combined_metrics = []
    with open(f"src/config/fwp_strategy.json", 'r') as f:
        fwp_config = json.load(f)
    fwp_rebal_problem = create_fwp_rebalance_problem(fwp_config)
    rebalance_problems.update({'fwp_strategy': fwp_rebal_problem})

    # for strategy_type, risk_tol, con_strength in product(strategies, risk_tolerances, concentration_strengths):
    #     with open(f"src/config/{strategy_type}.json", 'r') as f:
    #         config = json.load(f)

    #     strat_config = config.copy()
    #     strat_config['constraints']['risk_tolerance'] =  risk_tol
    #     strat_config['constraints']['concentration_strength'] =  con_strength
    #     builder = RebalanceProblemBuilder(strat_config)
    #     try:
    #         rebalance_problem = builder.build()
    #         strategy_type += f"_risk_tolerance_{str(risk_tol)}_con_strength{str(con_strength)}"
    #         rebalance_problems.update({strategy_type: rebalance_problem})
    #     except ValueError as e:
    #         print(f"Error building rebalance problem for {strat_config['strategy_type']}: {e}")
    #         continue

    runs = []
    metrics_computer = MetricsCompute()
    max_workers = min(8, multiprocessing.cpu_count())
    with Pool(processes=max_workers) as pool:
        results = [
            (strategy_type, pool.apply_async(run_strategy_async, args=(rebalance_problem,)))
            for strategy_type, rebalance_problem in rebalance_problems.items()
        ]
        for strategy_type, res in results:
            portfolio = res.get()
            if portfolio is None:
                continue
        
        run_id = str(uuid.uuid4())
        backtest_result = metrics_computer.compute(rebalance_problems[strategy_type], portfolio, market_store)
        metadata = {
            "timestamp": datetime.now(), 
            "username": "bkovalick", 
            "engine_version": "1.0.0"
        }
        runs.append(StrategyRun(run_id, rebalance_problems[strategy_type], backtest_result, metadata))

    # experiment = Experiment()
    print("Backtesting complete.")
