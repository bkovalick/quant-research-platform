from typing import Optional

import pandas as pd

from domain.strategies.base_strategy import BaseStrategy
from domain.signals.vix_basis_signal import VixBasisSignal
from domain.optimizers.target_weight_optimizer import TargetWeightOptimizer
from models.rebalance_problem import RebalanceProblem
from models.rebalance_context import RebalanceContext
from models.rebalance_solution import RebalanceSolution
from models.vix_basis_config import VixBasisConfig

FLAT, SHORT, LONG = "Flat", "Short", "Long"
CASH = "CASH"


class VixBasisStrategy(BaseStrategy):
    """
    Short vol in contango, long vol (optional) in backwardation, cash otherwise.
    Holds 100% of the book in exactly one of short_vol_ticker / long_vol_ticker / CASH.
    """
    def __init__(self,
                 rebalance_problem: RebalanceProblem,
                 optimizer: TargetWeightOptimizer = None):
        super().__init__(rebalance_problem, optimizer)
        self.side = FLAT

    def rebalance(self, rebalance_context: RebalanceContext) -> RebalanceSolution:
        active_signal = rebalance_context.signals.get(self.rebalance_problem.signal_source)
        if active_signal is None:
            target_weights = pd.Series(
                rebalance_context.current_weights,
                index=rebalance_context.investment_universe,
            )
        else:
            target_weights = self._run_vix_basis_strategy(rebalance_context, active_signal)
        return RebalanceSolution(
            target_weights=target_weights,
            sell_allocations={},
            realized_tax_cost=0.0,
            tracking_error=0.0
        )

    def _run_vix_basis_strategy(self,
                                rebalance_context: RebalanceContext,
                                active_signal: VixBasisSignal) -> pd.Series:
        if not isinstance(active_signal, VixBasisSignal):
            raise TypeError("Active signal must be of type VixBasisSignal")

        config = active_signal.config
        universe = list(rebalance_context.investment_universe)
        required = [config.short_vol_ticker, CASH] + ([config.long_vol_ticker] if config.enable_long else [])
        missing = [t for t in required if t not in universe]
        if missing:
            raise ValueError(
                f"VixBasisStrategy needs {missing} in the investment universe "
                f"(CASH is added when cash_allocation > 0)"
            )

        self.side = self.next_side(self.side, active_signal.generate_signal(), config)
        holding = {SHORT: config.short_vol_ticker, LONG: config.long_vol_ticker, FLAT: CASH}[self.side]

        target_weights = pd.Series(0.0, index=universe)
        target_weights[holding] = 1.0
        return target_weights

    @staticmethod
    def next_side(side: str, ratio: Optional[float], config: VixBasisConfig) -> str:
        """Hysteresis state machine on the front/back term-structure ratio."""
        if ratio is None:
            return side
        if side == SHORT and ratio <= config.short_exit:
            return SHORT
        if side == LONG and ratio >= config.long_exit:
            return LONG

        if ratio < config.short_entry:
            return SHORT
        if config.enable_long and ratio > config.long_entry:
            return LONG
        return FLAT
