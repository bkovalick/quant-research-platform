import abc
from optimizers.maximize_sharpe_optimizer import MaximizeSharpeOptimizer
from optimizers.mean_variance_optimizer import MeanVarianceOptimizer
from core.optimizers.ioptimizer import IOptimizer
from strategies.mean_variance_strategy import MeanVarianceStrategy
from strategies.fixed_weight_strategy import FixedWeightStrategy

class IStrategyFactory(abc.ABC):
    """Interface for optimizer factories."""
    @abc.abstractmethod
    def create_strategy(self, rebalance_problem, optimizer):
        pass

class StrategyFactory(IStrategyFactory):

    _strategies = {
        "mean_variance": MeanVarianceStrategy,
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