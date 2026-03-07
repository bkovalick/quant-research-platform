from domain.optimizers.portfolio_optimizer import Optimizer
from domain.strategies.istrategy import StrategyInterface
from models.rebalance_problem import RebalanceProblem

import numpy as np

class MeanVarianceStrategy(StrategyInterface):
    """Mean-variance optimized strategy.

    Maximizes risk-adjusted return using the portfolio optimizer subject to
    constraints (vol cap, turnover, asset class limits). Optionally applies
    post-optimization vol targeting to scale weights toward a target volatility.
    """
    def __init__(self, 
                 rebalance_problem: RebalanceProblem, 
                 optimizer=None):
        super().__init__(rebalance_problem, optimizer)
        self.optimizer = optimizer or Optimizer()

    def rebalance(self, 
                  signals: dict, 
                  current_weights: np.ndarray) -> np.ndarray:
        """Calculate rebalance weights"""
        risk_return_signals = signals.get("risk_return", None)
        optimized_weights = self.optimizer.optimize(
            self.rebalance_problem, risk_return_signals, current_weights
        )

        if getattr(self.rebalance_problem, 'vol_target', None):
            return self._apply_vol_targeting(risk_return_signals, optimized_weights)
        return optimized_weights
    
