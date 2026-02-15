import abc
import time

from domain.portfolio.iportfolio import PortfolioInterface
from domain.strategies.istrategy import StrategyInterface
from domain.signals.signals import Signals
from models.rebalance_problem import RebalanceProblem
from simulation.market_state import MarketState

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
                 market_state: MarketState):
        self.portfolio = portfolio
        self.strategy = strategy
        self.market_state = market_state

    def run_backtest(self, rebalance_problem: RebalanceProblem):
        """Run backtest on the given rebalance problem."""
        print("Running backtest...")
        start_time = time.time()
        initial_weights = rebalance_problem.initial_weights
        self.portfolio.initialize(
            self.market_state.prices.index, 
            self.market_state.prices.columns, 
            initial_weights
        )
        
        prev_weights = initial_weights
        while self.market_state.has_next():
            self.market_state.advance()

            cursor = self.market_state.cursor

            current_returns = self.market_state.returns.iloc[cursor]
            
            prev_weights = self.portfolio.drift(prev_weights, current_returns, cursor)

            if cursor < self.market_state.lookback:
                continue

            signals = Signals(self.market_state)

            target_weights = self.strategy.rebalance(signals, prev_weights)

            self.portfolio.apply(target_weights, prev_weights, cursor)

            prev_weights = target_weights

        print(f"Backtest duration: {time.time() - start_time} seconds")
        return self.portfolio
