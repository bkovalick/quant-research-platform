from signals.signals import Signals

class RebalanceProblem:    
    """
    Pure data container for a prepared rebalance problem.
    Attributes are accessed via properties.
    """

    def __init__(self, prepared_data: dict):
        self._data = dict(prepared_data)

    @property
    def use_full_universe(self) -> bool:
        return self._data.get("use_full_universe", False)
    
    @property
    def benchmark_universe(self) -> str:
        return self._data.get("benchmark_universe", "SPY")
        
    @property
    def n_constituents(self) -> int:
        return len(self.tickers)

    @property
    def tickers(self) -> list:
        return self._data.get("tickers", [])
    
    @property
    def optimizer_type(self) -> str:
        return self._data.get("optimizer_type", "fwp_optimizer")
    
    @property
    def strategy_type(self) -> str:
        return self._data.get("strategy_type", "fwp_strategy")
    
    @property
    def apply_max_return_objective(self) -> bool:
        return self._data.get("apply_max_return_objective", False)
    
    @property
    def apply_sharpe_objective(self) -> bool:
        return self._data.get("apply_sharpe_objective", False)    

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
    def apply_windsoring(self) -> bool:
        return self._data.get("apply_windsoring", True)
    
    @property
    def windsor_percentiles(self) -> dict:
        return self._data.get("windsor_percentiles", {"lower": 0.05, "upper": 0.95})

    @property
    def turnover_limit(self) -> float:
        return self._data.get("turnover_limit", 0.0)
    
    @property
    def min_position_size(self) -> float:
        return self._data.get("min_position_size", None) 
        
    @property
    def max_position_size(self) -> float:
        return self._data.get("max_position_size", None) 

    @property
    def max_number_of_positions(self) -> int:
        return self._data.get("max_number_of_positions", None)
    
    @property
    def asset_class_constraints(self) -> int:
        return self._data.get("asset_class_constraints", None)
    
    @property
    def sector_constraints(self) -> int:
        return self._data.get("sector_constraints", None)
