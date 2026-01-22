import abc
from optimizers.maximize_sharpe_optimizer import MaximizeSharpeOptimizer
from optimizers.mean_variance_optimizer import MeanVarianceOptimizer
from core.optimizers.ioptimizer import IOptimizer

class IOptimizerFactory(abc.ABC):
    """Interface for optimizer factories."""
    @abc.abstractmethod
    def create_optimizer(self, program_type):
        pass

class FixedWeightOptimizer(IOptimizer):
    def __init__(self):
        super().__init__()

    def optimize(self):
        return None

class OptimizerFactory(IOptimizerFactory):

    _optimizers = {
        "maximize_sharpe": MaximizeSharpeOptimizer,
        "mean_variance": MeanVarianceOptimizer,
        "fixed_weights": FixedWeightOptimizer
    }

    """Concrete implementation of an optimizer factory."""
    @classmethod
    def create_optimizer(cls, program_type):
        optimizer = cls._optimizers.get(program_type)
        if optimizer:
            return optimizer()
        else:
            raise ValueError(f"Unknown optimizer type: {program_type}")