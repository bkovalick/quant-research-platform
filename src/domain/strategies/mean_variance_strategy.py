from domain.optimizers.portfolio_optimizer import PortfolioOptimizer
from domain.strategies.istrategy import StrategyInterface
from domain.signals.signals import Signals, MovingAverageSignals, VolatilityForecastingSignals
from models.rebalance_problem import RebalanceProblem

import numpy as np

class MeanVarianceStrategy(StrategyInterface):
    def __init__(self, 
                 rebalance_problem: RebalanceProblem, 
                 optimizer=None):
        self.rebalance_problem = rebalance_problem
        self.optimizer = optimizer or PortfolioOptimizer()

    def rebalance(self, 
                  signals: dict, 
                  current_weights: np.ndarray) -> np.ndarray:
        """Calculate rebalance weights"""
        risk_return_signals = signals.get("base", None)
        optimized_weights = self.optimizer.optimize(
            self.rebalance_problem, risk_return_signals, current_weights
        )

        if getattr(self.rebalance_problem, 'vol_target', None):
            self._apply_vol_targeting(risk_return_signals, optimized_weights)
            
        return optimized_weights
    
    def _apply_vol_targeting(self, 
                             risk_return_signals: Signals, 
                             current_weights: np.ndarray) -> np.ndarray:
        vol_target = getattr(self.rebalance_problem, "vol_target")
        vol_max_leverage = getattr(self.rebalance_problem, "vol_max_leverage")
        realized_vol = risk_return_signals.portfolio_vol(current_weights)
        scaling_factor = min(vol_target / realized_vol, vol_max_leverage) if realized_vol > 0 else 1.0

        adjusted_weights = current_weights.copy()
        adjusted_weights[:-1] = current_weights[:-1] * scaling_factor
        adjusted_weights[-1] = 1.0 - np.sum(adjusted_weights[:-1])

        return adjusted_weights
