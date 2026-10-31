from domain.strategies.base_strategy import BaseStrategy
from domain.optimizers.optimizer import Optimizer
from models.rebalance_problem import RebalanceProblem
from models.rebalance_context import RebalanceContext
from models.rebalance_solution import RebalanceSolution

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
            return RebalanceSolution(
                target_weights=rebalance_context.current_weights,
                sell_allocations={},
                realized_tax_cost=0.0,
                tracking_error=0.0
            )

        rebalance_solution = self.optimizer.optimize(
            rebalance_context, active_signal
        )

        return rebalance_solution