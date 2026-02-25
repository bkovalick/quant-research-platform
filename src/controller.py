from data.market_data_gateway import MarketDataStore
from models.experiment import Experiment
from models.strategy_run import StrategyRun
from domain.portfolio.portfolio import Portfolio
from reporting.reporting_module import MetricsCompute
from simulation.backtesting_engine import BacktestingEngine
from simulation.market_state import MarketState
from services.strategy_factory import StrategyFactory
from services.optimizer_factory import OptimizerFactory

from datetime import datetime
import uuid

def run_backtesting_suite(config):
    market_store_config = config["market_store_config"]
    market_store = MarketDataStore(market_store_config)
    experiment = Experiment(
        experiment_id = str(uuid.uuid4()), 
        created_at = datetime.now(),
        market_config = market_store 
    )
    metrics_computer = MetricsCompute()
    for strat_cfg in config["strategies"]:
        run_id = str(uuid.uuid4())
        market_state = MarketState(market_store, strat_cfg)
        rebalance_problem = strat_cfg["rebalance_problem"]
        opt_type = rebalance_problem.optimizer_type
        optimizer = OptimizerFactory.create_optimizer(opt_type)
        strategy = StrategyFactory.create_strategy(rebalance_problem, optimizer)
        portfolio = Portfolio()
        backtestingEngine = BacktestingEngine(portfolio, strategy, market_state)
        backtestedPortfolio = backtestingEngine.run_backtest(rebalance_problem)
        backtest_result = metrics_computer.compute(rebalance_problem, backtestedPortfolio)
        experiment.add_run(StrategyRun(run_id, rebalance_problem, backtest_result, build_metadata()))

    return experiment

def build_metadata():
    return {
        "timestamp": datetime.now(), 
        "username": "bkovalick", 
        "engine_version": "1.0.0"
    }