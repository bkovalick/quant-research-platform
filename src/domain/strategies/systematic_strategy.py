import logging

from domain.strategies.base_strategy import BaseStrategy
from domain.optimizers.optimizer import Optimizer
from models.rebalance_problem import RebalanceProblem
from models.rebalance_context import RebalanceContext
from models.rebalance_solution import RebalanceSolution

import pandas as pd

logger = logging.getLogger(__name__)

class SystematicStrategy(BaseStrategy):
    """ 
    Systematic strategy that is entirely driven by configuration files. 
    The strategy logic is determined by the signal source specified in the rebalance problem, 
    and the optimizer is applied to those signals to generate new weights.
    """
    def __init__(self, 
                 rebalance_problem: RebalanceProblem, 
                 optimizer: Optimizer = None):
        super().__init__(rebalance_problem, optimizer)
    
    def rebalance(self, rebalance_context: RebalanceContext) -> RebalanceSolution:
        """Calculate rebalance weights"""
        signal_key = self.rebalance_problem.signal_source
        active_signal = rebalance_context.signals.get(signal_key)
        
        if active_signal is None:
            logger.warning(
                "reason_code=signal_missing strategy=systematic signal_key=%s cursor=%s",
                signal_key,
                rebalance_context.cursor,
            )
            return RebalanceSolution(
                target_weights=pd.Series(
                    rebalance_context.current_weights,
                    index=rebalance_context.investment_universe,
                ),
                sell_allocations={},
                realized_tax_cost=0.0,
                tracking_error=0.0
            )

        rebalance_solution = self.optimizer.optimize(
            rebalance_context, active_signal
        )
        logger.debug(
            "reason_code=signal_present strategy=systematic signal_key=%s cursor=%s",
            signal_key,
            rebalance_context.cursor,
        )

        return rebalance_solution