import abc
from core.optimizers.maximize_sharpe_optimizer.maximize_sharpe import MaximizeSharpeOptimizer
from core.optimizers.mean_variance_optimizer.mean_variance_optimizer import MeanVarianceOptrimizer

class IOptimizerFactory(abc.ABC):
    """Interface for optimizer factories."""
    @abc.abstractmethod
    def create_optimizer(self, program_type):
        pass

class OptimizerFactory(IOptimizerFactory):

    _optimizers = {
        "maximize_sharpe": MaximizeSharpeOptimizer,
        "mean_variance": MeanVarianceOptrimizer,
        "fixed_weights": None
    }

    """Concrete implementation of an optimizer factory."""
    @classmethod
    def create_optimizer(cls, program_type):
        optimizer = cls._optimizers.get(program_type)
        if optimizer:
            return optimizer()
        else:
            raise ValueError(f"Unknown optimizer type: {program_type}")