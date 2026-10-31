from domain.strategies.base_strategy import BaseStrategy
from domain.optimizers.optimizer import Optimizer
from models.rebalance_problem import RebalanceProblem
from models.rebalance_context import RebalanceContext
from models.rebalance_solution import RebalanceSolution
from signals.moving_average_signals import MovingAverageSignals

import numpy as np
import pandas as pd

class MeanReversionStrategy(BaseStrategy):
    """ 
    Mean Reversion Strategy that generates target weights based on mean reversion signals.`
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
                target_weights=pd.Series(
                    rebalance_context.current_weights,
                    index=rebalance_context.investment_universe,
                ),
                sell_allocations={},
                realized_tax_cost=0.0,
                tracking_error=0.0
            )

        rebalance_solution = self._generate_reversion_signals(rebalance_context, active_signal)
        return rebalance_solution

    def _generate_reversion_signals(self, 
                                     rebalance_context: RebalanceContext,
                                     signal: MovingAverageSignals) -> RebalanceSolution:
        """Evaluate the mean reversion strategy based on the provided signal."""
        if not isinstance(signal, MovingAverageSignals):
            raise TypeError("Expected signal to be of type MovingAverageSignals")

        current_weights = rebalance_context.current_weights
        z_scores = signal.bollinger_weighted_moving_average()['z_score']
        todays_z_scores = z_scores.iloc[-1]
        tuning_factor = 0.05
        tilts = -todays_z_scores * tuning_factor
        raw_weights = (current_weights + tilts).clip(lower = 0)
        target_weights = raw_weights / raw_weights.sum()
        return RebalanceSolution(
            target_weights=target_weights,
            sell_allocations={},
            realized_tax_cost=0.0,
            tracking_error=0.0
        )