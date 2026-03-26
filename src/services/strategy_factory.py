import abc
from domain.strategies.mean_variance_strategy import MeanVarianceStrategy
from domain.strategies.mean_reversion_strategy import MeanReversionStrategy
from domain.strategies.fixed_weight_strategy import FixedWeightStrategy
from domain.strategies.equal_weight_strategy import EqualWeightStrategy
from domain.strategies.systematic_strategy import SystematicStrategy

class IStrategyFactory(abc.ABC):
    """Interface for optimizer factories."""
    @abc.abstractmethod
    def create_strategy(self, rebalance_problem, optimizer):
        pass

class StrategyFactory(IStrategyFactory):

    _strategies = {
        "mean_variance_strategy": MeanVarianceStrategy,
        "mean_reversion_strategy": MeanReversionStrategy,
        "fwp_strategy": FixedWeightStrategy,
        "ewp_strategy": EqualWeightStrategy,
        "systematic_strategy": SystematicStrategy
    }

    """Concrete implementation of an optimizer factory."""
    @classmethod
    def create_strategy(cls, rebalance_problem, optimizer):
        strategy = cls._strategies.get(rebalance_problem.strategy_type)
        if strategy:
            return strategy(rebalance_problem, optimizer)
        else:
            raise ValueError(f"Unknown strategy type: {rebalance_problem.strategy_type}")