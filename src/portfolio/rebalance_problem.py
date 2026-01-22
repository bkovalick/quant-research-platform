import pandas as pd
import numpy as np

from signals.signals import Signals

class RebalanceProblem:    
    """
    Pure data container for a prepared rebalance problem.
    Attributes are accessed via properties.
    """

    def __init__(self, prepared_data: dict):
        self._data = dict(prepared_data)

    @property
    def signals(self):
        class DummyMarketEnv:
            @property
            def normalized_prices(self):
                return self_outer.price_data
        self_outer = self
        return Signals(DummyMarketEnv())
    
    @property
    def n_constituents(self) -> int:
        return len(self.tickers)

    @property
    def tickers(self) -> list:
        return self._data.get("tickers", [])
    
    @property
    def program_type(self) -> str:
        return self._data.get("program_type", "fixed_weights")
    
    @property
    def start_date(self) -> str:
        return self._data.get("start_date")
    
    @property
    def end_date(self) -> str:
        return self._data.get("end_date")

    @property
    def risk_free_rate(self) -> float:
        return self._data.get("risk_free_rate")

    @property
    def target_weights(self) -> list:
        return self._data.get("target_weights")

    @property
    def initial_weights(self) -> list:
        return self._data.get("initial_weights")

    @property
    def rebalanced_weights(self) -> list:
        """Get the initial portfolio weights."""
        return self._data.get("rebalanced_weights")
    
    @rebalanced_weights.setter
    def rebalanced_weights(self, weights):
        """Set the initial portfolio weights."""
        self._data["rebalanced_weights"] = weights

    @property
    def cash_allocation(self) -> float:
        return self._data.get("cash_allocation")
    
    @property
    def trading_frequency(self) -> str:
        return self._data.get("trading_frequency", "d")
    
    @property
    def lookback_window(self) -> int:
        return self._data.get("lookback_window", 252)
    
    @property
    def first_rebal(self) -> int:
        return self._data.get("first_rebal", 0)
    
    @property
    def risk_tolerance(self) -> int:
        return self._data.get("risk_tolerance", 0)
    
    @property
    def model_constraints(self) -> dict:
        return self._data.get("model_constraints", {})
    
    @property
    def apply_windsoring(self) -> bool:
        return self._data.get("apply_windsoring", True)
    
    @property
    def windsor_percentiles(self) -> dict:
        return self._data.get("windsor_percentiles", {"lower": 0.05, "upper": 0.95})

    @property
    def trading_buffer(self) -> float:
        return self._data.get("trading_buffer", 0.0)
    
    @property
    def apply_max_return_objective(self) -> bool:
        return self._data.get("apply_max_return_objective", False)
    
    @property
    def apply_sharpe_objective(self) -> bool:
        return self._data.get("apply_sharpe_objective", False)
    
