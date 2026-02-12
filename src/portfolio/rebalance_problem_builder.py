import numpy as np
from portfolio.rebalance_problem import RebalanceProblem
from infrastructure.market_data.marketdatautils import MarketDataUtils

class RebalanceProblemBuilder:
    """Orchestrates the pipeline to build a RebalanceProblem from input configuration."""

    def __init__(self, config: dict):
        """Initialize with configuration dictionary."""
        self.config = config

    def build_asset_class_map(self, tickers_with_cash) -> dict:
        """Build a mapping from asset class to list of indices in tickers_with_cash."""
        full_mapping_df = MarketDataUtils.get_full_mapping_universe()
        asset_class_df = full_mapping_df[full_mapping_df['ticker'].isin(tickers_with_cash)]
        ticker_to_index = {ticker: idx for idx, ticker in enumerate(tickers_with_cash)}
        asset_class_map = asset_class_df.groupby('asset_class')['ticker'].apply(
            lambda tickers: [(ticker_to_index[ticker], ticker) for ticker in tickers if ticker in ticker_to_index]
        ).to_dict()
        cash_idx = tickers_with_cash.index("CASH")
        asset_class_map.update({"Cash": (cash_idx, "CASH")})
        return asset_class_map
    
    def build_sector_map(self, tickers_with_cash) -> dict: # do the same as above
        """Build and asset/sector grouping related to the assets in the investable universe."""
        full_mapping_df = MarketDataUtils.get_full_mapping_universe()
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
        use_full_universe = self.config.get("use_full_universe", False)
        if use_full_universe:
            tickers = MarketDataUtils.get_universe_tickers()
            n_assets = len(tickers)
            initial_weights = np.ones(n_assets) / n_assets
            initial_weights = initial_weights.tolist() + [0]        
        else:
            tickers = [item["ticker"] for item in self.config["rebalance_sub_parameters"]]
            if self.config.get("use_init_weights", True):
                initial_weights = [ item["initial_weights"] 
                            for item in self.config["rebalance_sub_parameters"] ]                
            else:
                initial_weights = [ 1 / len(tickers) for t in tickers ]

            if cash_allocation == 0:
                initial_weights += [cash_allocation] 
            else:
                initial_weights = [ (1 - cash_allocation) / len(tickers) for t in tickers ] + [cash_allocation]

        tickers_with_cash = tickers + ["CASH"]
        lookback_window = self.config.get("lookback_window", "1y")
        trading_frequency = self.config.get("trading_frequency", "d")
        asset_class_map = self.build_asset_class_map(tickers_with_cash)
        sector_map = self.build_sector_map(tickers_with_cash)

        prepared_data = {
            "use_full_universe": self.config.get("use_full_universe", False),
            "benchmark_universe": self.config.get("benchmark_universe", "SPY"),
            "tickers": tickers_with_cash,
            "risk_free_rate": self.config["risk_free_rate"],
            "optimizer_type": self.config.get("optimizer_type"),
            "strategy_type": self.config.get("strategy_type"),
            "apply_max_return_objective": self.config.get("apply_max_return_objective", False),
            "apply_sharpe_objective": self.config.get("apply_sharpe_objective", False),
            "start_date": self.config["start_date"],
            "end_date": self.config["end_date"],
            "initial_weights": initial_weights,
            "cash_allocation": cash_allocation,
            "risk_tolerance": self.config.get("risk_tolerance", 0.0),
            "trading_frequency": trading_frequency,
            "lookback_window":  MarketDataUtils.get_lookback_window_mapping()\
                [trading_frequency][lookback_window],
            "first_rebal": self.config.get("first_rebal", 0),
            "apply_windsoring": self.config["constraints"].get("apply_windsoring", True),
            "windsor_percentiles": self.config["constraints"].get("windsor_percentiles", \
                                                                  {"lower": 0.05, "upper": 0.95}),
            "turnover_limit": self.config["constraints"].get("turnover_limit", None),
            "min_position_size": self.config["constraints"].get("min_position_size", None),
            "max_position_size": self.config["constraints"].get("max_position_size", None),
            "max_number_of_positions": self.config["constraints"].get("max_number_of_positions", None),
            "asset_class_constraints": self.config["constraints"].get("asset_class_constraints", None),
            "sector_constraints": self.config["constraints"].get("sector_constraints", None),
            "asset_class_map": asset_class_map,
            "sector_map": sector_map,
            "max_return": self.config["constraints"].get("max_return", 0.05),
            "concentration_strength": self.config["constraints"].get("concentration_strength", 1)
        }

        return RebalanceProblem(prepared_data)
