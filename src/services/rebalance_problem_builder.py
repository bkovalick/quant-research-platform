import numpy as np
from models.rebalance_problem import RebalanceProblem
from models.market_config import MarketStateConfig
from data.market_metadata import MarketMetadata
from config.lookback_windows import LOOKBACK_WINDOWS

class RebalanceProblemBuilder:
    """Orchestrates the pipeline to build a RebalanceProblem from input configuration."""

    def __init__(self, config: dict):
        """Initialize with configuration dictionary."""
        self.config = config

    def build_asset_class_map(self, tickers_with_cash: list) -> dict:
        """Build a mapping from asset class to list of indices in tickers_with_cash."""
        full_mapping_df = MarketMetadata.get_full_mapping_universe()
        asset_class_df = full_mapping_df[full_mapping_df['ticker'].isin(tickers_with_cash)]
        ticker_to_index = {ticker: idx for idx, ticker in enumerate(tickers_with_cash)}
        asset_class_map = asset_class_df.groupby('asset_class')['ticker'].apply(
            lambda tickers: [(ticker_to_index[ticker], ticker) for ticker in tickers if ticker in ticker_to_index]
        ).to_dict()
        cash_idx = tickers_with_cash.index("CASH")
        asset_class_map.update({"Cash": (cash_idx, "CASH")})
        return asset_class_map
    
    def build_sector_map(self, tickers_with_cash) -> dict:
        """Build and asset/sector grouping related to the assets in the investable universe."""
        full_mapping_df = MarketMetadata.get_full_mapping_universe()
        sector_df = full_mapping_df[full_mapping_df['ticker'].isin(tickers_with_cash)]
        ticker_to_index = {ticker: idx for idx, ticker in enumerate(tickers_with_cash)}
        sector_map = sector_df.groupby('sector')['ticker'].apply(
            lambda tickers: [(ticker_to_index[ticker], ticker) for ticker in tickers if ticker in ticker_to_index]
        ).to_dict()
        cash_idx = tickers_with_cash.index("CASH")
        sector_map.update({"Cash": (cash_idx, "CASH")})
        return sector_map
    
    def build(self) -> RebalanceProblem:
        """Build and return a RebalanceProblem instance."""
        cash_allocation = self.config.get("cash_allocation", 0.0)
        tickers = self.config.get("universe_tickers", ["AAPL"])
        initial_weights = [ 1 / len(tickers) for t in tickers ]
        if cash_allocation == 0:
            initial_weights += [cash_allocation] 
        else:
            initial_weights = [ (1 - cash_allocation) / len(tickers) for t in tickers ] + [cash_allocation]

        tickers_with_cash = tickers + ["CASH"]
        lookback_window_key = self.config["market_state_config"].get("lookback_window_key", "1y")
        market_frequency = self.config["market_state_config"].get("market_frequency", "w")
        apply_winsorizing = self.config["market_state_config"].get("apply_winsorizing", True)
        windsor_percentiles = self.config["market_state_config"].get("windsor_percentiles", {"lower": 0.05, "upper": 0.95})         

        prepared_data = {
            "benchmark_universe": self.config.get("benchmark_universe", "SPY"),
            "tickers": tickers_with_cash,
            "optimizer_type": self.config.get("optimizer_type"),
            "strategy_type": self.config.get("strategy_type"),
            "apply_max_return_objective": self.config.get("apply_max_return_objective", False),
            "apply_sharpe_objective": self.config.get("apply_sharpe_objective", False),
            "initial_weights": initial_weights,
            "cash_allocation": cash_allocation,
            "rebalance_frequency": self.config.get("rebalance_frequency", None),
            "market_state_config": MarketStateConfig(market_frequency=market_frequency,
                                                     lookback_window=LOOKBACK_WINDOWS[market_frequency][lookback_window_key],
                                                     annual_trading_days=LOOKBACK_WINDOWS[market_frequency]["1y"],
                                                     apply_winsorizing= apply_winsorizing,
                                                     windsor_percentiles=windsor_percentiles,
                                                     universe_tickers=tickers_with_cash),
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
            "asset_class_map": self.build_asset_class_map(tickers_with_cash),
            "sector_map": self.build_sector_map(tickers_with_cash),            
        }

        return RebalanceProblem(prepared_data)