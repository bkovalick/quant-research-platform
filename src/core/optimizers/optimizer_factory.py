import abc
from optimizers.scipy_optimizer import ScipyOptimizer
from optimizers.cvxpy_optimizer import CvxpyOptimizer
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
        "scipy_optimizer": ScipyOptimizer,
        "cvxpy_optimizer": CvxpyOptimizer,
        "fwp_optimizer": FixedWeightOptimizer
    }

    """Concrete implementation of an optimizer factory."""
    @classmethod
    def create_optimizer(cls, optimizer_type):
        optimizer = cls._optimizers.get(optimizer_type)
        if optimizer:
            return optimizer()
        else:
            raise ValueError(f"Unknown optimizer type: {optimizer_type}")