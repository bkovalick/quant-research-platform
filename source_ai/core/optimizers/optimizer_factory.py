from .maximize_sharpe_optimizer import MaximizeSharpeOptimizer
from .mean_variance_optimizer import MeanVarianceOptimizer
from .optimizer_interface import IOptimizer

class FixedWeightOptimizer(IOptimizer):
    def optimize(self, rebalance_problem=None):
        return None

class OptimizerFactory:
    _optimizers = {
        "maximize_sharpe": MaximizeSharpeOptimizer,
        "mean_variance": MeanVarianceOptimizer,
        "fixed_weights": FixedWeightOptimizer
    }
    @classmethod
    def create_optimizer(cls, program_type):
        optimizer = cls._optimizers.get(program_type)
        if optimizer:
            return optimizer()
        else:
            raise ValueError(f"Unknown optimizer type: {program_type}")
