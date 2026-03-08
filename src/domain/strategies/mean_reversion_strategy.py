from domain.strategies.istrategy import StrategyInterface
from models.rebalance_problem import RebalanceProblem

import numpy as np

class MeanReversionStrategy(StrategyInterface):
    """Mean reversion strategy.

    Generates signals based on price deviations from a moving average and
    passes them to the optimizer to construct positions that bet on reversion
    to the mean. Optionally applies vol targeting.
    """
    def __init__(self, rebalance_problem: RebalanceProblem, optimizer=None):
        super().__init__(rebalance_problem, optimizer)

    def rebalance(self, signals: dict, current_weights: np.ndarray) -> np.ndarray:
        # reversion_signals = signals.get("mean_reversion", None)
        reversion_signals = signals.get("black_litterman", None)
        optimized_weights = self.optimizer.optimize(
            self.rebalance_problem, reversion_signals, current_weights
        )

        if getattr(self.rebalance_problem, 'vol_target', None):
            return self._apply_vol_targeting(reversion_signals, optimized_weights)
        return optimized_weights