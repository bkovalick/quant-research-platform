
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
from data.market_data_gateway import MarketDataStore

import uuid
from datetime import datetime

class ExperimentRunner:
    def __init__(self, config):
        self.config = config

    def run(self):
        market_store = self._build_market_store()
        experiment = self._create_experiment()

        for strategy_cfg in self.config["strategies"]:
            run = self._run_strategy(strategy_cfg, market_store)
            experiment.add_run(run)

        return experiment

    def _run_strategy(self, strategy_cfg, market_store):
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
    
    def _create_experiment(self, market_store_cfg):
        return Experiment(
            experiment_id = str(uuid.uuid4()), 
            created_at = datetime.now(),
            market_config = market_store_cfg 
        )

    def _build_market_store(self):
        pass

    def _build_market_state(self, strategy_cfg: dict, market_store: MarketDataStore):
        market_state_config = strategy_cfg["market_state_config"]
        mkt_state = MarketState(market_store, market_state_config)
        # return MarketStateConfig(market_frequency=market_frequency,
        #                   lookback_window=LOOKBACK_WINDOWS[market_frequency][lookback_window_key],
        #                   annual_trading_days=LOOKBACK_WINDOWS[market_frequency]["1y"]
        #                   universe_tickers=tickers_with_cash),

    def _build_signal_config(self, strategy_cfg: dict):
        return 

    def _build_rebalance_problem(self, strategy_cfg: dict):
        builder = RebalanceProblemBuilder(strategy_cfg)
        try:
            rebalance_problem = builder.build()
            return rebalance_problem
        except ValueError as e:
            print(f"Error building rebalance problem for {strategy_cfg['strategy_type']}: {e}")

    def _build_metadata(self):
        return {
            "timestamp": datetime.now(), 
            "username": "bkovalick", 
            "engine_version": "1.0.0"
        }