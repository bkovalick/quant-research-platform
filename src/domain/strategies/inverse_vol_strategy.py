import numpy as np
import pandas as pd

from domain.strategies.base_strategy import BaseStrategy
from domain.signals.volatility_forecasting_signals import VolatilityForecastingSignals
from domain.optimizers.target_weight_optimizer import TargetWeightOptimizer
from models.inverse_vol_config import InverseVolConfig
from models.rebalance_problem import RebalanceProblem
from models.rebalance_context import RebalanceContext
from models.rebalance_solution import RebalanceSolution

CASH = "CASH"


class InverseVolStrategy(BaseStrategy):
    """
    Inverse volatility strategy. Risky weights are proportional to 1 / forecast vol
    and sum to (1 - cash_allocation); CASH, when in the universe, holds cash_allocation.
    Assets without a usable forecast (zero or undefined vol, e.g. prices backfilled
    before an ETF listed) get no weight.
    """
    def __init__(self,
                 rebalance_problem: RebalanceProblem,
                 optimizer: TargetWeightOptimizer = None):
        super().__init__(rebalance_problem, optimizer)

    def rebalance(self, rebalance_context: RebalanceContext) -> RebalanceSolution:
        active_signal = rebalance_context.signals.get(self.rebalance_problem.signal_source)
        if active_signal is None:
            target_weights = pd.Series(
                rebalance_context.current_weights,
                index=rebalance_context.investment_universe,
            )
        else:
            target_weights = self._run_inverse_vol_strategy(rebalance_context, active_signal)
        return RebalanceSolution(
            target_weights=target_weights,
            sell_allocations={},
            realized_tax_cost=0.0,
            tracking_error=0.0
        )

    def _run_inverse_vol_strategy(self,
                                  rebalance_context: RebalanceContext,
                                  active_signal: VolatilityForecastingSignals) -> pd.Series:
        if not isinstance(active_signal, VolatilityForecastingSignals):
            raise TypeError("Active signal must be of type VolatilityForecastingSignals")
        config = active_signal.signals_cfg.inverse_vol
        if config is None:
            raise ValueError("inverse_vol_strategy needs a signals_config.inverse_vol block")

        universe = list(rebalance_context.investment_universe)
        risky = [t for t in universe if t != CASH]
        vols = self._get_volatility_forecast(active_signal, config).reindex(risky)
        usable = vols.where(np.isfinite(vols) & (vols > 0))
        if usable.notna().sum() == 0:
            return pd.Series(rebalance_context.current_weights, index=universe)

        inverse_vol = 1.0 / usable
        cash_weight = float(self.rebalance_problem.cash_allocation or 0.0) if CASH in universe else 0.0

        weights = pd.Series(0.0, index=universe)
        weights[risky] = (inverse_vol / inverse_vol.sum()).fillna(0.0) * (1.0 - cash_weight)
        if CASH in universe:
            weights[CASH] = cash_weight
        return weights

    @staticmethod
    def _get_volatility_forecast(active_signal: VolatilityForecastingSignals,
                                 config: InverseVolConfig) -> pd.Series:
        if config.forecast_type == "ewma":
            return active_signal.ewma_volatility(span=config.window)
        if config.forecast_type == "rolling":
            return active_signal.rolling_realized_vol(window=config.window)
        if config.forecast_type == "garch":
            return active_signal.garch_volatility()
        raise ValueError(f"Unsupported forecast type: {config.forecast_type}")
