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
        initial_weights = [ 1 / n_assets for t in range(n_assets) ]
        if cash_allocation > 0:
            initial_weights = [ (1 - cash_allocation) / n_assets for t in range(n_assets) ] + [cash_allocation]

        prepared_data = {
            "n_assets": self.config.get("n_assets", 5),
            "optimizer_type": self.config.get("optimizer_type"),
            "strategy_type": self.config.get("strategy_type"),
            "apply_max_return_objective": self.config.get("apply_max_return_objective", False),
            "apply_sharpe_objective": self.config.get("apply_sharpe_objective", False),
            "initial_weights": initial_weights,
            "cash_allocation": cash_allocation,
            "rebalance_frequency": self.config.get("rebalance_frequency", None),
            "risk_tolerance": self.config.get("constraints", {}).get("risk_tolerance", 0.05),
            "risk_free_rate": self.config.get("constraints", {}).get("risk_free_rate", 0.03),
            "turnover_limit": self.config.get("constraints", {}).get("turnover_limit", None),
            "min_position_size": self.config.get("constraints", {}).get("min_position_size", None),
            "max_position_size": self.config.get("constraints", {}).get("max_position_size", None),
            "max_number_of_positions": self.config.get("constraints", {}).get("max_number_of_positions", None),
            "asset_class_constraints": self.config.get("constraints", {}).get("asset_class_constraints", None),
            "sector_constraints": self.config.get("constraints", {}).get("sector_constraints", None),
            "max_return": self.config.get("constraints", {}).get("max_return", 0.05),
            "concentration_strength": self.config.get("constraints", {}).get("concentration_strength", 1),
            "asset_class_map": self.universe_meta.get("asset_class_map", {}),
            "sector_map": self.universe_meta.get("sector_map", {}),
            "tickers": tickers
        }

        return RebalanceProblem(prepared_data)