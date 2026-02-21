from models.experiment import Experiment
from domain.portfolio.portfolio import Portfolio
from reporting.reporting_module import MetricsCompute
from reporting.reporting_module import ExcelGenerator
from simulation.backtesting_engine import BacktestingEngine
from simulation.market_state import MarketState
from services.strategy_factory import StrategyFactory
from services.optimizer_factory import OptimizerFactory
from services.rebalance_problem_builder import RebalanceProblemBuilder
from models.strategy_run import StrategyRun
from models.backtest_result import BacktestResult
from models.market_config import MarketStoreConfig, MarketStateConfig
from models.signals_config import SignalsConfig
from models.rebalance_problem import RebalanceProblem
from config.lookback_windows import LOOKBACK_WINDOWS
from data.market_data_gateway import MarketDataStore

import uuid
from datetime import datetime

class ExperimentRunner:
    def __init__(self, config):
        self.config = config

    def run(self) -> Experiment:
        market_store_cfg = self.config["market_store_config"]
        market_store = self._build_market_store(market_store_cfg)
        experiment = self._create_experiment()

        for strategy_cfg in self.config["strategies"]:
            run = self._run_strategy(strategy_cfg, market_store)
            experiment.add_run(run)

        return experiment

    def _run_strategy(self, strategy_cfg: dict, market_store: MarketDataStore) -> StrategyRun:
        run_id = str(uuid.uuid4())
        signal_config = self._build_signal_config(strategy_cfg)
        state = self._build_market_state(strategy_cfg, market_store)
        rebalance_problem = self._build_rebalance_problem(strategy_cfg)
        strategy = StrategyFactory.create(rebalance_problem)

        portfolio = Portfolio()
        engine = BacktestingEngine(
            portfolio,
            strategy,
            state,
            signal_config
        )

        portfolio = engine.run_backtest(rebalance_problem)

        result = MetricsCompute.compute(...)

        return StrategyRun(run_id, rebalance_problem, result, self._build_metadata())
    
    def _create_experiment(self, market_store_cfg: dict) -> Experiment:
        return Experiment(
            experiment_id = str(uuid.uuid4()), 
            created_at = datetime.now(),
            market_config = market_store_cfg 
        )

    def _build_market_store(self, market_store_cfg: dict) -> MarketDataStore:
        return MarketDataStore(market_store_cfg)

    def _build_market_state(self, strategy_cfg: dict, market_store: MarketDataStore):
        market_state_config = strategy_cfg["market_state_config"]
        market_state_config.annual_trading_days = LOOKBACK_WINDOWS[market_state_config.market_frequency]["1y"]
        market_state_config.universe_tickers = market_state_config.universe_tickers + + ["CASH"]
        return MarketState(market_store, market_state_config)

    def _build_signal_config(self, strategy_cfg: dict) -> SignalsConfig:
        return SignalsConfig(strategy_cfg["signals_config"]) 

    def _build_rebalance_problem(self, strategy_cfg: dict) -> RebalanceProblem:
        builder = RebalanceProblemBuilder(strategy_cfg)
        try:
            rebalance_problem = builder.build()
            return rebalance_problem
        except ValueError as e:
            print(f"Error building rebalance problem for {strategy_cfg['strategy_type']}: {e}")

    def _build_metadata(self) -> dict:
        return {
            "timestamp": datetime.now(), 
            "username": "bkovalick", 
            "engine_version": "1.0.0"
        }