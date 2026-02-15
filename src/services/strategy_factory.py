import abc
from domain.strategies.mean_variance_strategy import MeanVarianceStrategy
from domain.strategies.fixed_weight_strategy import FixedWeightStrategy

class IStrategyFactory(abc.ABC):
    """Interface for optimizer factories."""
    @abc.abstractmethod
    def create_strategy(self, rebalance_problem, optimizer):
        pass

class StrategyFactory(IStrategyFactory):

    _strategies = {
        "mean_variance_strategy": MeanVarianceStrategy,
        "fwp_strategy": FixedWeightStrategy
    }

    """Concrete implementation of an optimizer factory."""
    @classmethod
    def create_strategy(cls, rebalance_problem, optimizer):
        strategy = cls._strategies.get(rebalance_problem.strategy_type)
        if strategy:
            return strategy(rebalance_problem, optimizer)
        else:
            raise ValueError(f"Unknown strategy type: {rebalance_problem.strategy_type}")