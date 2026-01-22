import abc
from strategies.mv_optimization_strategy import MVOptimizationStrategy
from strategies.fixed_weight_strategy import FixedWeightStrategy

class IStrategyFactory(abc.ABC):
    """Interface for optimizer factories."""
    @abc.abstractmethod
    def create_strategy(self, rebalance_problem, optimizer):
        pass

class StrategyFactory(IStrategyFactory):

    _strategies = {
        "mv_optimizer": MVOptimizationStrategy,
        "fixed_weights": FixedWeightStrategy
    }

    """Concrete implementation of an optimizer factory."""
    @classmethod
    def create_strategy(cls, rebalance_problem, optimizer):
        strategy = cls._strategies.get(rebalance_problem.program_type)
        if strategy:
            return strategy(rebalance_problem, optimizer)
        else:
            raise ValueError(f"Unknown strategy type: {rebalance_problem.program_type}")