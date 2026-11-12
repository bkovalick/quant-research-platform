import logging
import pandas as pd

from domain.optimizers.base_optimizer import BaseOptimizer
from domain.optimizers.target_weight_optimizer import TargetWeightOptimizer
from domain.optimizers.parameterized_optimizer import ParameterizedOptimizer
from domain.signals.signals import Signals
from models.rebalance_context import RebalanceContext
from models.rebalance_solution import RebalanceSolution

logger = logging.getLogger(__name__)

class FixedWeightOptimizer(BaseOptimizer):
    def __init__(self):
        super().__init__()

    def optimize(self, 
                 rebalance_context: RebalanceContext,
                 active_signal: Signals = None) -> RebalanceSolution:
        return RebalanceSolution(
            target_weights=pd.Series(
                rebalance_context.current_weights,
                index=rebalance_context.investment_universe,
            ),
            sell_allocations={},
            realized_tax_cost=0.0,
            tracking_error=0.0
        )

class OptimizerFactory:

    _optimizers = {
        "portfolio_optimizer": TargetWeightOptimizer,
        "fwp_optimizer": FixedWeightOptimizer,
        "parameterized_optimizer": ParameterizedOptimizer
    }

    """Concrete implementation of a optimizer factory."""
    @classmethod
    def create_optimizer(cls, optimizer_type, rebalance_problem=None):
        logger.info("Creating optimizer for type %s", optimizer_type)
        optimizer = cls._optimizers.get(optimizer_type)
        if optimizer_type == "None":
            logger.debug("Using fixed-weight optimizer for type None")
            return FixedWeightOptimizer()

        if optimizer is ParameterizedOptimizer:
            # Builds its problem once from the rebalance problem's structure.
            if rebalance_problem is None:
                raise ValueError("parameterized_optimizer needs the rebalance_problem")
            return ParameterizedOptimizer(rebalance_problem)
        if optimizer:
            logger.debug("Instantiated optimizer class %s", optimizer.__name__)
            return optimizer()
        else:
            logger.warning("Unknown optimizer type requested: %s", optimizer_type)
            raise ValueError(f"Unknown optimizer type: {optimizer_type}")