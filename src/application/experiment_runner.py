import numpy as np
import pandas as pd
import uuid
import logging
import multiprocessing 
import json
import threading
from datetime import datetime
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import Optional

from application.progress import ProgressCallback, QueueReporter
from domain.portfolio.portfolio import Portfolio
from domain.portfolio.tax_lot_ledger import TaxLotLedger
from reporting.performance_analyzer import PerformanceAnalyzer
from reporting.diagnostics import FactorRegressionDiagnostics, LongOnlyICDiagnostics, PairsSpreadDiagnostics
from simulation.backtesting_engine import BacktestingEngine
from simulation.market_state import MarketState
from services.strategy_factory import StrategyFactory
from services.optimizer_factory import OptimizerFactory
from services.rebalance_problem_builder import RebalanceProblemBuilder
from services.signals_factory import SignalFactory
from models.strategy_run import StrategyRun
from models.market_config import MarketStoreConfig, MarketStateConfig
from models.rebalance_config import RebalanceProblemConfig
from models.signals_config import SignalsConfig
from models.experiment import Experiment
from models.backtest_result import BacktestResult
from models.monitoring_stats import MonitoringStats
from infrastructure.market_data_gateway import MarketDataStore

logger = logging.getLogger(__name__)

_MARKET_STORE_CACHE = {}
_DRAIN_STOP = ("__stop__", {})


def _drain_progress(queue, progress: ProgressCallback) -> None:
    """Forward progress events from worker processes to the in-process callback."""
    while True:
        try:
            item = queue.get()
        except (EOFError, OSError):
            return
        if item == _DRAIN_STOP:
            return
        name, fields = item
        progress(name, **fields)

def _market_store_cache_key(market_store_config: MarketStoreConfig) -> str:
    """Build a stable, hashable cache key from config contents."""
    return json.dumps(market_store_config.to_dict(), sort_keys=True, default=str)

def get_market_store(market_store_config: MarketStoreConfig) -> MarketDataStore:
    """Cache market data store per process and config to avoid repeated loads."""
    cache_key = _market_store_cache_key(market_store_config)
    if cache_key not in _MARKET_STORE_CACHE:
        _MARKET_STORE_CACHE[cache_key] = MarketDataStore(market_store_config)
    return _MARKET_STORE_CACHE[cache_key]

def build_monitors(run, monitoring_type):
    monitors = []

    strategy_monitor = {
        "long_only": LongOnlyICDiagnostics,
        "pairs": PairsSpreadDiagnostics,
    }.get(monitoring_type)

    if strategy_monitor is not None:
        monitors.append(strategy_monitor(run))

    monitors.append(FactorRegressionDiagnostics(run))

    return monitors

def merge_monitoring_stats(*stats: Optional[MonitoringStats]) -> MonitoringStats:
    merged = {
        "ic_statistics": None,
        "ic_summary": None,
        "regression_summary": None,
    }

    for stat in stats:
        if stat is None:
            continue
        if stat.ic_statistics is not None:
            merged["ic_statistics"] = stat.ic_statistics
        if stat.ic_summary is not None:
            merged["ic_summary"] = stat.ic_summary
        if stat.regression_summary is not None:
            merged["regression_summary"] = stat.regression_summary

    return MonitoringStats(
        ic_statistics=merged["ic_statistics"],
        ic_summary=merged["ic_summary"],
        regression_summary=merged["regression_summary"],
    )
    
def build_signal_config(strategy_cfg: dict) -> Optional[SignalsConfig]:
    cfg = strategy_cfg.get("signals_config")
    if not cfg: 
        return None
    return SignalsConfig.from_dict(cfg, strategy_cfg.get("market_state_config", {}).get("market_frequency", "d"))

def build_market_state_config(strategy_cfg: dict) -> MarketStateConfig:
    cfg = strategy_cfg.get("market_state_config")
    if not cfg: raise ValueError("Error: Market state configuration must be present to run a backtest")
    return MarketStateConfig.from_dict(cfg)

def build_signals_factory(strategy_cfg: dict, market_state: MarketState) -> SignalFactory:
    signal_config = build_signal_config(strategy_cfg)
    signals_factory = SignalFactory(signal_config, market_state)
    return signals_factory

def build_tax_lot_ledger(rebalance_problem) -> Optional[TaxLotLedger]:
    if rebalance_problem.apply_tax_objective:
        return TaxLotLedger()
    return None

def run_strategy_worker(strategy_cfg: dict,
                        market_store_config: MarketStoreConfig,
                        progress: Optional[ProgressCallback] = None) -> StrategyRun:
    name = strategy_cfg.get("name", "Unnamed Strategy")
    report = (lambda **fields: progress(name, **fields)) if progress is not None else (lambda **fields: None)
    try:
        run = _run_strategy(strategy_cfg, market_store_config, report)
    except Exception as exc:
        report(phase="failed", error=f"{type(exc).__name__}: {exc}")
        raise
    report(phase="done")
    return run

def _run_strategy(strategy_cfg: dict, market_store_config: MarketStoreConfig, report) -> StrategyRun:
    logger.info(f"Running strategy: {strategy_cfg.get('name', 'Unnamed Strategy')}")
    print(f"Running strategy: {strategy_cfg.get('name', 'Unnamed Strategy')}")
    report(phase="loading_data")
    market_store = get_market_store(market_store_config)
    market_state_config = build_market_state_config(strategy_cfg)
    market_state = MarketState(market_store, market_state_config)

    rebalance_problem = RebalanceProblemBuilder(
        RebalanceProblemConfig.from_dict(strategy_cfg["rebalance_problem"]), market_state
    ).build()
    
    optimizer = OptimizerFactory.create_optimizer(rebalance_problem.optimizer_type)
    tax_lot_ledger = build_tax_lot_ledger(rebalance_problem)
    strategy = StrategyFactory.create_strategy(rebalance_problem, optimizer)
    signals_factory = build_signals_factory(strategy_cfg, market_state)
    portfolio = Portfolio(
        financing_rate=market_store_config.risk_free_rate + rebalance_problem.financing_spread,
        periods_per_year=market_state_config.annual_trading_days
    )
    
    run = BacktestingEngine(
        portfolio, 
        strategy, 
        market_state, 
        signals_factory,
        tax_lot_ledger,
        progress_callback=lambda pct, as_of: report(
            phase="running", pct=pct, as_of=as_of.strftime("%Y-%m-%d")
        ),
    ).run_backtest(rebalance_problem)

    report(phase="analyzing", pct=100.0)

    portfolio_results = PerformanceAnalyzer().compute(
        run.portfolio,
        market_store_config,
        market_state_config,
        market_state.market_returns,
    )

    stats = [
        monitor.analyze()
        for monitor in build_monitors(run, rebalance_problem.monitoring_type)
    ]

    monitoring_stats = merge_monitoring_stats(*stats)
    
    return StrategyRun(
        run_id=str(uuid.uuid4()),
        strategy_name=strategy_cfg["name"],
        result=portfolio_results,
        monitoring_stats=monitoring_stats,
        strategy_config=strategy_cfg,
        metadata={"timestamp": datetime.now(), "username": "bkovalick", "engine_version": "1.0.0"},
    )

class ExperimentRunner:
    def __init__(self, config: dict):
        self.config = config
        # self.max_workers = min(8, multiprocessing.cpu_count())
        self.max_workers = 4
        logger.info("ExperimentRunner initialized with %s strategies", len(self.config.get("strategies", [])))
        print(f"ExperimentRunner initialized with {len(self.config.get('strategies', []))} strategies")

    def _get_market_config(self) -> MarketStoreConfig:
        cfg = self.config.get("market_store_config")
        if not cfg: raise ValueError("Error: Market store configuration must be present")
        return MarketStoreConfig.from_dict(cfg)

    def _create_experiment(self, m_cfg: MarketStoreConfig) -> Experiment:
        return Experiment(experiment_id=str(uuid.uuid4()), created_at=datetime.now(), market_config=m_cfg)

    def run(self, progress: Optional[ProgressCallback] = None) -> Experiment:
        m_cfg = self._get_market_config()
        experiment = self._create_experiment(m_cfg)
        logger.info("Starting sequential experiment run")
        for strategy_cfg in self.config["strategies"]:
            experiment.add_run(run_strategy_worker(strategy_cfg, m_cfg, progress))
        experiment.add_run(self._build_benchmark_run(m_cfg, experiment))
        logger.info("Sequential experiment run complete with %s strategy runs", len(experiment.strategy_runs))
        print("Sequential experiment run complete with %s strategy runs" % len(experiment.strategy_runs))
        return experiment

    def run_parallel(self, progress: Optional[ProgressCallback] = None) -> Experiment:
        m_cfg = self._get_market_config()
        experiment = self._create_experiment(m_cfg)
        strategies = self.config["strategies"]

        logger.info(f"Running {len(strategies)} strategies in parallel with max_workers={self.max_workers}")
        manager = multiprocessing.Manager() if progress is not None else None
        drainer = None
        try:
            worker_progress = None
            if manager is not None:
                queue = manager.Queue()
                worker_progress = QueueReporter(queue)
                drainer = threading.Thread(target=_drain_progress, args=(queue, progress), daemon=True)
                drainer.start()
            with ProcessPoolExecutor(max_workers=self.max_workers) as executor:
                futures = [executor.submit(run_strategy_worker, s_cfg, m_cfg, worker_progress) for s_cfg in strategies]
                for future in as_completed(futures):
                    experiment.add_run(future.result())
        finally:
            if drainer is not None:
                queue.put(_DRAIN_STOP)
                drainer.join(timeout=5)
            if manager is not None:
                manager.shutdown()
        experiment.add_run(self._build_benchmark_run(m_cfg, experiment))
        logger.info("Parallel experiment run complete with %s strategy runs", len(experiment.strategy_runs))
        print("Parallel experiment run complete with %s strategy runs" % len(experiment.strategy_runs))
        return experiment

    def _build_benchmark_run(self, m_cfg: MarketStoreConfig, experiment: Experiment) -> StrategyRun:
        first = experiment.strategy_runs[0]
        state_cfg = build_market_state_config(self.config["strategies"][0])
        dates = first.result.series["portfolio_returns"].index

        store = get_market_store(m_cfg)
        market_state = MarketState(store, state_cfg)
        if market_state.market_returns is None:
            raise ValueError("Benchmark returns are required to build the benchmark run")
        bench_returns = market_state.market_returns.reindex(dates).fillna(0)

        result = self._benchmark_result(m_cfg, state_cfg, bench_returns, dates)
        return StrategyRun(
            run_id=str(uuid.uuid4()),
            strategy_name=m_cfg.benchmark,
            result=result,
            monitoring_stats=None,
            strategy_config=None,
            metadata={"timestamp": datetime.now(), "username": "bkovalick", "engine_version": "1.0.0"},
        )
    
    def _benchmark_result(self, 
                          market_store_config: MarketStoreConfig,
                          market_state_config: MarketStateConfig, 
                          benchmark_returns: pd.Series,
                          dates: pd.DatetimeIndex) -> BacktestResult:
        """Compute benchmark results for comparison."""
        benchmark_name = market_store_config.benchmark
        portfolio = Portfolio()
        portfolio.initialize(dates, np.array([benchmark_name]), np.array([1.0]))
        portfolio.returns = benchmark_returns
        portfolio.weights = pd.DataFrame(1.0, index=dates, columns=[benchmark_name])
        portfolio.turnover = pd.Series(0.0, index=dates)
        analyzer = PerformanceAnalyzer()
        return analyzer.compute(
            portfolio, market_store_config, market_state_config, benchmark_returns
        )        

if __name__ == "__main__":
    pass