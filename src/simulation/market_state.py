from models.market_config import MarketStateConfig
from config.lookback_windows import LOOKBACK_WINDOWS
from data.market_data_gateway import MarketDataStore
import pandas as pd
from datetime import datetime

class MarketState:
    def __init__(self, store: MarketDataStore, state_config: MarketStateConfig):
        """ Stores the current state of the market """
        self.store = store
        self.state_config = state_config
        self.lookback = state_config.lookback_window
        self.market_frequency = state_config.market_frequency
        self.apply_winsorizing = state_config.apply_winsorizing
        self.windsor_percentiles = state_config.windsor_percentiles
        self.universe_tickers = state_config.universe_tickers
        self.annual_trading_days = state_config.annual_trading_days
        self.cursor = 0
        self.parsed_prices = self._parse_universe(self.universe_tickers)
        self.prices = self._resample(self.market_frequency)
        self.returns = self.prices.pct_change().iloc[1:]
    
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
            self.cursor - self.lookback : self.cursor
        ]
        return window

    def lookback_returns(self) -> pd.DataFrame:
        lookback_returns = self.returns.iloc[
            self.cursor - self.lookback : self.cursor
        ]
        return lookback_returns
    
    def normalized_prices(self) -> pd.DataFrame:
        """ Normalize prices to start at 1 """
        w = self.lookback_prices()
        return w / w.iloc[0]
    
    def current_date(self) -> datetime:
        return self.prices.index[self.cursor]
    
    def has_next(self) -> bool:
        return self.cursor < len(self.prices) - 1