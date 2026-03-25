from domain.strategies.istrategy import StrategyInterface
from models.rebalance_problem import RebalanceProblem

import numpy as np

class SystematicStrategy(StrategyInterface):
    """ Systematic optimized strategy

    Systematic strategy that is entirely driven by configuration files. 
    The strategy logic is determined by the signal source specified in the rebalance problem, 
    and the optimizer is applied to those signals to generate new weights.
    """
    def __init__(self, 
                 rebalance_problem: RebalanceProblem, 
                 optimizer=None):
        super().__init__(rebalance_problem, optimizer)

    def rebalance(self, 
                  signals: dict, 
                  current_weights: np.ndarray) -> np.ndarray:
        """Calculate rebalance weights"""
        signal_key = self.rebalance_problem.signal_source  # "black_litterman", "risk_return", etc.
        active_signals = signals.get(signal_key)
        
        optimized = self.optimizer.optimize(
            self.rebalance_problem, active_signals, current_weights
        )
        
        if getattr(self.rebalance_problem, 'vol_target', None):
            return self._apply_vol_targeting(active_signals, optimized)
        return optimized