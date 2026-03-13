import abc
import time
import numpy as np

from domain.portfolio.iportfolio import PortfolioInterface
from domain.strategies.istrategy import StrategyInterface
from domain.signals.risk_return_signals import RiskReturnSignals 
from domain.signals.moving_average_signals import MovingAverageSignals
from domain.signals.volatility_forecasting_signals import VolatilityForecastingSignals
from domain.signals.mean_reversion_signals import MeanReversionSignals
from domain.signals.momentum_signals import MomentumSignals
from domain.signals.black_litterman_signal import BlackLittermanSignal
from domain.machine_learning.cross_sectional_model import CrossSectionalModel
from domain.machine_learning.feature_builder import FeatureBuilder
from domain.signals.ml_signals import MLSignals, MLSignalsState
from models.rebalance_problem import RebalanceProblem
from models.signals_config import SignalsConfig
from models.machine_learning_config import MachineLearningConfig
from simulation.market_state import MarketState
from utils.rebalance_steps import FREQ_TO_STEPS

class BacktestingEngineInterface(abc.ABC):
    """Interface for backtesting engines."""
    @abc.abstractmethod
    def run_backtest(self, rebalance_problem: RebalanceProblem):
        raise NotImplementedError("Must implement run_backtest in derived classes.")

class BacktestingEngine(BacktestingEngineInterface):
    """Concrete implementation of a backtesting engine."""
    def __init__(self, 
                 portfolio: PortfolioInterface, 
                 strategy: StrategyInterface,
                 market_state: MarketState,
                 signals_config: SignalsConfig,
                 ml_signals_config: MachineLearningConfig):
        self.portfolio = portfolio
        self.strategy = strategy
        self.market_state = market_state
        self.signals_cfg = signals_config

        if ml_signals_config is not None:
            self.ml_signals_cfg = ml_signals_config
            self.feature_builder = FeatureBuilder(
                self.market_state.prices.copy(), 
                self.market_state.returns.copy()
            )
            self.cs_model = CrossSectionalModel(ml_signals_config)
            self.ml_signals_state = MLSignalsState(
                ml_signals_config,
                self.feature_builder,
                self.cs_model
            )
            self.ml_signals = MLSignals(
                self.market_state, 
                self.signals_cfg, 
                self.ml_signals_cfg, 
                self.ml_signals_state
            )

    def run_backtest(self, rebalance_problem: RebalanceProblem):
        """Run backtest on the given rebalance problem."""
        print("Running backtest...")
        start_time = time.time()
        self.rebalance_every = self._get_steps(rebalance_problem.rebalance_frequency)
        initial_weights = np.array(list(rebalance_problem.initial_weights.values()))
        self.portfolio.initialize(
            self.market_state.prices.index, 
            self.market_state.prices.columns, 
            initial_weights
        )
        
        prev_weights = np.array(initial_weights)
        while self.market_state.has_next():
            self.market_state.advance()

            cursor = self.market_state.cursor
            
            current_returns = self.market_state.returns.iloc[cursor]

            prev_weights = self.portfolio.drift(prev_weights, current_returns, cursor)
            if cursor < self.market_state.lookback_window:
                continue

            if not self._is_rebalance_step(cursor):
                continue

            signals = self._build_signals(self.market_state, self.signals_cfg, prev_weights)
            target_weights = self.strategy.rebalance(signals, prev_weights)
            self.portfolio.apply(target_weights, prev_weights, cursor)
            prev_weights = target_weights

        print(f"Backtest duration: {time.time() - start_time} seconds")
        return self.portfolio

    def _is_rebalance_step(self, step):
        return step % self.rebalance_every == 0
    
    def _get_steps(self, freq_param):
        key = (self.market_state.market_frequency, freq_param)
        return FREQ_TO_STEPS.get(key, 1)
    
    def _build_signals(self, 
                       market_state: MarketState, 
                       signals_config: SignalsConfig, 
                       current_weights: np.ndarray) -> dict:
        if self.ml_signals_cfg is not None:
            self.ml_signals_state.update(market_state.current_date)

        return {
            "risk_return": RiskReturnSignals(market_state, signals_config),
            "mean_reversion": MeanReversionSignals(market_state, signals_config),
            "moving_average": MovingAverageSignals(market_state, signals_config),
            "volatility_forecast": VolatilityForecastingSignals(market_state, signals_config),
            "momentum": MomentumSignals(market_state, signals_config),
            "black_litterman": BlackLittermanSignal(market_state, signals_config, current_weights),
            "ml_cross_sectional": self.ml_signals
        } 