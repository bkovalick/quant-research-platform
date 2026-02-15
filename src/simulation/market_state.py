from models.market_config import MarketStateConfig
from config.lookback_windows import LOOKBACK_WINDOWS
from data.market_data_gateway import MarketDataStore

class MarketState:
    def __init__(self, store: MarketDataStore, state_config: MarketStateConfig):
        """ Stores the current state of the market """
        self.store = store
        self.state_config = state_config
        self.lookback_key = state_config.lookback_window
        self.trading_frequency = state_config.trading_frequency
        self.lookback = LOOKBACK_WINDOWS[self.trading_frequency][self.lookback_key]
        self.cursor = 0
        self.apply_winsorizing = state_config.apply_winsorizing
        self.windsor_percentiles = state_config.windsor_percentiles
        self.prices = self._resample(self.trading_frequency)
        self.returns = self.prices.pct_change()
    
    def _resample(self, trading_frequency):  
        if trading_frequency == "d":
            return self.store.prices        
        
        rule = {"w": "W-FRI", "m": "M"}[trading_frequency]
        resampled_prices = self.store.prices.resample(rule).last()

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
    
    def has_next(self):
        return self.cursor < len(self.prices) - 1