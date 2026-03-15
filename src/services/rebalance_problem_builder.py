from models.rebalance_problem import RebalanceProblem

class RebalanceProblemBuilder:
    """Orchestrates the pipeline to build a RebalanceProblem from input configuration."""

    def __init__(self, config: dict, universe_meta: dict):
        """Initialize with configuration dictionary."""
        self.config = config
        self.universe_meta = universe_meta
    
    def build(self) -> RebalanceProblem:
        """Build and return a RebalanceProblem instance."""
        cash_allocation = self.universe_meta.get("cash_allocation", 0.0)
        tickers = self.universe_meta.get("tickers", ["AAPL"])
        n_assets = len(tickers)
        explicit_weights = self.config.get("initial_weights", None)
        if explicit_weights:
            weights = explicit_weights
        elif cash_allocation > 0:
            weights = [(1 - cash_allocation) / (n_assets - 1)] * (n_assets - 1) + [cash_allocation]
        else:
            weights = [1 / n_assets] * n_assets

        if isinstance(weights, list):
            initial_weights = dict(zip(tickers, weights))
        elif isinstance(weights, dict):
            initial_weights = weights

        constraints = self.config.get("constraints", {})
        strategy_rules = self.config.get("strategy_rules", {}) 
        prepared_data = {
            "n_assets": n_assets,
            "optimizer_type": self.config.get("optimizer_type"),
            "strategy_type": self.config.get("strategy_type"),
            "apply_max_return_objective": self.config.get("apply_max_return_objective", False),
            "apply_sharpe_objective": self.config.get("apply_sharpe_objective", False),
            "initial_weights": initial_weights,
            "cash_allocation": cash_allocation,
            "rebalance_frequency": self.config.get("rebalance_frequency", None),
            "risk_aversion": constraints.get("risk_aversion", 1),
            "turnover_limit": constraints.get("turnover_limit", None),
            "min_position_size": constraints.get("min_position_size", None),
            "max_position_size": constraints.get("max_position_size", None),
            "max_number_of_positions": constraints.get("max_number_of_positions", None),
            "asset_class_constraints": constraints.get("asset_class_constraints", None),
            "sector_constraints": constraints.get("sector_constraints", None),
            "max_return": constraints.get("max_return", 0.05),
            "concentration_strength": constraints.get("concentration_strength", 1),
            "asset_class_map": self.universe_meta.get("asset_class_map", {}),
            "sector_map": self.universe_meta.get("sector_map", {}),
            "tickers": tickers,
            "optimizer_vol_constraint": constraints.get("optimizer_vol_constraint", None),
            "vol_target": strategy_rules.get("vol_target", None),
            "vol_lookback_days": strategy_rules.get("vol_lookback_days", None),
            "vol_max_leverage": strategy_rules.get("vol_max_leverage", None)
        }

        return RebalanceProblem(prepared_data)