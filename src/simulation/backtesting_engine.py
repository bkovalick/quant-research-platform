import abc
import time

from domain.portfolio.iportfolio import PortfolioInterface
from domain.strategies.istrategy import StrategyInterface
from domain.signals.signals import Signals
from models.rebalance_problem import RebalanceProblem
from models.signals_config import SignalsConfig
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
                 signals_cfg: SignalsConfig):
        self.portfolio = portfolio
        self.strategy = strategy
        self.market_state = market_state
        self.signals_cfg = signals_cfg

    def run_backtest(self, rebalance_problem: RebalanceProblem):
        """Run backtest on the given rebalance problem."""
        print("Running backtest...")
        start_time = time.time()
        self.rebalance_every = self._get_steps(rebalance_problem.rebalance_frequency)
        initial_weights = rebalance_problem.initial_weights
        self.portfolio.initialize(
            self.market_state.prices.index, 
            self.market_state.prices.columns, 
            initial_weights
        )
        
        prev_weights = initial_weights
        while self.market_state.has_next():
            self.market_state.advance()

            print(f"Backtesting Date: {self.market_state.current_date()}")
            cursor = self.market_state.cursor
            
            current_returns = self.market_state.returns.iloc[cursor]

            prev_weights = self.portfolio.drift(prev_weights, current_returns, cursor)
            if cursor < self.market_state.lookback_window:
                continue

            if not self._is_rebalance_step(cursor):
                continue

            signals = Signals(self.market_state, self.signals_cfg)
            target_weights = self.strategy.rebalance(signals, prev_weights)
            self.portfolio.apply(target_weights, prev_weights, cursor)
            prev_weights = target_weights

        print(f"Backtest duration: {time.time() - start_time} seconds")
        return self.portfolio

    def _is_rebalance_step(self, step):
        return step % self.rebalance_every == 0
    
    def _get_steps(self, freq_param):
        key = (freq_param['from'], freq_param['to'])
        return FREQ_TO_STEPS.get(key)