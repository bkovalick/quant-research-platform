from domain.portfolio.portfolio import Portfolio
from reporting.reporting_module import MetricsCompute
from simulation.backtesting_engine import BacktestingEngine
from simulation.market_state import MarketState
from services.strategy_factory import StrategyFactory
from services.optimizer_factory import OptimizerFactory
from services.rebalance_problem_builder import RebalanceProblemBuilder
from models.strategy_run import StrategyRun
from models.market_config import MarketStoreConfig, MarketStateConfig
from models.signals_config import SignalsConfig
from models.rebalance_problem import RebalanceProblem
from models.experiment import Experiment
from models.machine_learning_config import MachineLearningConfig
from infrastructure.market_data_gateway import MarketDataStore

import uuid
from datetime import datetime
import multiprocessing
from concurrent.futures import ProcessPoolExecutor, as_completed

def build_signal_config(strategy_cfg: dict) -> SignalsConfig:
    signals_config = strategy_cfg.get("signals_config", None)
    if signals_config is not None:
        market_frequency = strategy_cfg.get("market_state_config", {}).get("market_frequency", "d")
        return SignalsConfig.from_dict(signals_config, market_frequency)
    return None

def build_market_state_config(strategy_cfg: dict) -> MarketStateConfig:
    market_state_config = strategy_cfg.get("market_state_config", None)
    if market_state_config is None:
        raise ValueError("Error: Market state configuration must be present to run a backtest")
    return MarketStateConfig.from_dict(market_state_config)

def run_strategy_worker(strategy_cfg, market_store_config):
    market_store = MarketDataStore(market_store_config)
    portfolio = Portfolio()
    metrics_computer = MetricsCompute()

    state_config = build_market_state_config(strategy_cfg)
    state = MarketState(market_store, state_config)

    universe_meta = {
            "tickers": state.universe_tickers,
            "cash_allocation": state.cash_allocation,
            "asset_class_map": state.asset_class_map,
            "sector_map": state.sector_map
    }    

    rebalance_problem = RebalanceProblemBuilder(
        strategy_cfg["rebalance_problem"], 
          universe_meta,
          state_config.market_frequency
    signals_config = build_signal_config(strategy_cfg)

    optimizer = OptimizerFactory.create_optimizer(rebalance_problem.optimizer_type) 
    strategy = StrategyFactory.create_strategy(rebalance_problem, optimizer)

    engine = BacktestingEngine(
        portfolio,
        strategy,
        state,
        signals_config
    )

    portfolio = engine.run_backtest(rebalance_problem)

    result = metrics_computer.compute(
        rebalance_problem, 
        portfolio, 
        market_store_config, 
        state_config,
        market_store.prices[market_store_config.benchmark]
    )

    run_id = str(uuid.uuid4())
    return StrategyRun(
        run_id, 
        strategy_cfg["name"],
        rebalance_problem, 
        result, 
        {
            "timestamp": datetime.now(), 
            "username": "bkovalick", 
            "engine_version": "1.0.0"
        }
    )    

class ExperimentRunner:
    def __init__(self, config):
        self.config = config
        self.max_workers = min(8, multiprocessing.cpu_count())

    def run(self) -> Experiment:
        market_store_config = self._build_market_store_config()
        market_store = self._build_market_store(market_store_config)
        experiment = self._create_experiment(market_store_config)
        for strategy_cfg in self.config["strategies"]:
            run = self._run_strategy(strategy_cfg, market_store, market_store_config)
            experiment.add_run(run)

        return experiment
    
    def run_parallel(self) -> Experiment:
        market_store_config = self._build_market_store_config()
        experiment = self._create_experiment(market_store_config)
        strategies = self.config["strategies"]
        with ProcessPoolExecutor(max_workers=self.max_workers) as executor:
            futures = [
                executor.submit(run_strategy_worker,
                                strategy_cfg, market_store_config
                )
                for strategy_cfg in strategies
            ]

            for future in as_completed(futures):
                run = future.result()
                experiment.add_run(run)

        return experiment
    
    def _run_strategy(self, 
                      strategy_cfg: dict, 
                      market_store: MarketDataStore, 
                      market_store_config: MarketStoreConfig) -> StrategyRun:
        portfolio = Portfolio()
        metrics_computer = MetricsCompute()

        state_config = self._build_market_state_config(strategy_cfg)
        state = self._build_market_state(market_store, state_config)

        universe_meta = self._build_universe_meta(state)

        rebalance_problem = self._build_rebalance_problem(strategy_cfg, universe_meta)

        signals_config = self._build_signal_config(strategy_cfg)

        optimizer = OptimizerFactory.create_optimizer(rebalance_problem.optimizer_type) 
        strategy = StrategyFactory.create_strategy(rebalance_problem, optimizer)

        engine = BacktestingEngine(
            portfolio,
            strategy,
            state,
            signals_config
        )

        portfolio = engine.run_backtest(rebalance_problem)

        result = metrics_computer.compute(
            rebalance_problem, 
            portfolio, 
            market_store_config, 
            state_config,
            market_store.prices[market_store_config.benchmark]
        )

        run_id = str(uuid.uuid4())
        return StrategyRun(
            run_id, 
            strategy_cfg["name"],
            rebalance_problem, 
            result, 
            {
                "timestamp": datetime.now(), 
                "username": "bkovalick", 
                "engine_version": "1.0.0"
            }
        )
    
    def _create_experiment(self, market_store_cfg: dict) -> Experiment:
        return Experiment(
            experiment_id = str(uuid.uuid4()), 
            created_at = datetime.now(),
            market_config = market_store_cfg 
        )

    def _build_market_store_config(self) -> MarketStoreConfig:
        market_store_config = self.config.get("market_store_config", None)
        if market_store_config is None:
            raise ValueError("Error: Market store configuration must be present to run a backtest")
        return MarketStoreConfig.from_dict(market_store_config)

    def _build_market_store(self, 
                            market_store_config: MarketStoreConfig) -> MarketDataStore:
        return MarketDataStore(market_store_config)

    def _build_market_state_config(self, strategy_cfg: dict) -> MarketStateConfig:
        market_state_config = strategy_cfg.get("market_state_config", None)
        if market_state_config is None:
            raise ValueError("Error: Market state configuration must be present to run a backtest")
        return MarketStateConfig.from_dict(market_state_config)
    
    def _build_market_state(self, 
                            market_store: MarketDataStore, 
                            market_state_config: MarketStateConfig) -> MarketState:
        return MarketState(market_store, market_state_config)
    
    def _build_universe_meta(self, 
                             market_state: MarketState) -> dict:
        return {
            "tickers": market_state.universe_tickers,
            "cash_allocation": market_state.cash_allocation,
            "asset_class_map": market_state.asset_class_map,
            "sector_map": market_state.sector_map
        }        

    def _build_rebalance_problem(self, 
                                 strategy_cfg: dict, 
                                 universe_meta: dict) -> RebalanceProblem:
        builder = RebalanceProblemBuilder(
            strategy_cfg["rebalance_problem"],
            universe_meta,
            strategy_cfg.get("market_state_config", {}).get("market_frequency", "d")
        )
        try:
            rebalance_problem = builder.build()
            return rebalance_problem
        except ValueError as e:
            print(f"Error building rebalance problem for {strategy_cfg['strategy_type']}: {e}")

    def _build_signal_config(self, strategy_cfg: dict) -> SignalsConfig:
        signals_config = strategy_cfg.get("signals_config", None)
        if signals_config is not None:
            market_frequency = strategy_cfg.get("market_state_config", {}).get("market_frequency", "d")
            return SignalsConfig.from_dict(signals_config, market_frequency)
        return None    

    def _build_metadata(self) -> dict:
        return {
            "timestamp": datetime.now(), 
            "username": "bkovalick", 
            "engine_version": "1.0.0"
        }