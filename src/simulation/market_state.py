from models.market_config import MarketStateConfig
from config.lookback_windows import LOOKBACK_WINDOWS
from data.market_data_gateway import MarketDataStore
import pandas as pd

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
        self.cursor = 0
        self.parsed_prices = self._parse_universe(self.universe_tickers)
        self.prices = self._resample(self.market_frequency)
        self.returns = self.prices.pct_change()
    
    def _parse_universe(self, universe_tickers):
        return self.store.prices[[universe_tickers]]
    
    def _resample(self, trading_frequency) -> pd.DataFrame:
        if trading_frequency == "d":
            return self.parsed_prices
        
        rule = {"w": "W-FRI", "m": "M"}[trading_frequency]
        resampled_prices = self.parsed_prices.resample(rule).last()

        if not self.apply_winsorizing:
            return resampled_prices
        
        lower_bound = resampled_prices.quantile(self.windsor_percentiles["lower"])
        upper_bound = resampled_prices.quantile(self.windsor_percentiles["upper"])
        return resampled_prices.clip(lower=lower_bound, upper=upper_bound, axis = 1)
    
    def advance(self):
        self.cursor +=1

    def lookback_prices(self) -> pd.DataFrame:
        window = self.prices.iloc[
            self.cursor - self.lookback : self.cursor
        ]
        return window

    def lookback_returns(self) -> pd.DataFrame:
        return self.returns.iloc[
            self.cursor - self.lookback : self.cursor
        ]
    
    def normalized_prices(self) -> pd.DataFrame:
        """ Normalize prices to start at 1 """
        w = self.lookback_prices()
        return w / w.iloc[0]
    
    def current_date(self):
        return self.prices.index[self.cursor]
    
    def has_next(self) -> bool:
        return self.cursor < len(self.prices) - 1