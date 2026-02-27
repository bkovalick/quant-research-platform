from models.market_config import MarketStateConfig
from data.market_data_gateway import MarketDataStore
from data.market_metadata import MarketMetadata

import pandas as pd
from datetime import datetime

class MarketState:
    def __init__(self, store: MarketDataStore, state_config: MarketStateConfig):
        """ Stores the current state of the market """
        self.store = store
        self.state_config = state_config
        self.lookback_window_key = state_config.lookback_window_key
        self.market_frequency = state_config.market_frequency
        self.lookback_window = state_config.lookback_window
        self.universe_tickers = state_config.universe_tickers
        self.cash_allocation = state_config.cash_allocation
        self.annual_trading_days = state_config.annual_trading_days
        self.cursor = 0
        self.parsed_prices = self._parse_universe(self.universe_tickers)
        self.prices = self._resample(self.market_frequency)
        self.returns = self.prices.pct_change().fillna(0)
    
    @property
    def asset_class_map(self):
        return MarketMetadata.build_asset_class_map(self.universe_tickers)
    
    @property
    def sector_map(self):
        return MarketMetadata.build_sector_map(self.universe_tickers)
    
    def _parse_universe(self, universe_tickers) -> pd.DataFrame:
        return self.store.prices[universe_tickers]
    
    def _resample(self, trading_frequency) -> pd.DataFrame:
        if trading_frequency == "d":
            return self.parsed_prices
        
        rule = {"w": "W-FRI", "m": "M"}[trading_frequency]
        return self.parsed_prices.resample(rule).last()
    
    def advance(self):
        self.cursor += 1

    def lookback_prices(self) -> pd.DataFrame:
        window = self.prices.iloc[
            self.cursor - self.lookback_window : self.cursor
        ]
        return window

    def lookback_returns(self) -> pd.DataFrame:
        lookback_returns = self.returns.iloc[
            self.cursor - self.lookback_window : self.cursor
        ]
        return lookback_returns
    
    def normalized_prices(self) -> pd.DataFrame:
        w = self.lookback_prices()
        return w / w.iloc[0]
    
    def current_date(self) -> datetime:
        return self.prices.index[self.cursor]
    
    def has_next(self) -> bool:
        return self.cursor < len(self.prices) - 1