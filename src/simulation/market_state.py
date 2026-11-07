from datetime import datetime
from typing import Optional
import pandas as pd

from models.market_config import MarketStateConfig
from infrastructure.market_data_store import MarketDataStore
from reference.market_metadata import MarketMetadata

class MarketState:
    def __init__(self, 
                 store: MarketDataStore, 
                 state_config: MarketStateConfig):
        """ Stores the current state of the market """

        # Store the market data store and related attributes
        self.store = store
        self.apply_market_caps = store.apply_market_caps
        self.transaction_cost = store.transaction_cost

        # Store the market state configuration
        self.state_config = state_config
        self.lookback_window_key = state_config.lookback_window_key
        self.market_frequency = state_config.market_frequency
        self.lookback_window = state_config.lookback_window
        self.investment_universe = state_config.investment_universe
        self.signal_universe = state_config.signal_universe
        self.security_to_etf_map = state_config.security_to_etf_map
        self.exogenous_tickers = state_config.exogenous_tickers
        self.cash_allocation = state_config.cash_allocation
        self.annual_trading_days = state_config.annual_trading_days
        self.setup()

    def setup(self):
        """Initialize the market state by setting up the investment and signal prices, returns, and exogenous universe."""
        self.cursor = 0
        self.investment_prices = self._resample(self.market_frequency, self._parse_universe(self.investment_universe))
        # NaN means "no price": before listing, after delisting, or a gap longer than the store bridges.
        self.investment_returns = self.investment_prices.pct_change(fill_method=None)
        # Last known price, used only to value and exit positions already held. Never feed it to signals.
        self.valuation_prices = self.investment_prices.ffill()
        self.signal_prices = self._resample(self.market_frequency, self._parse_universe(self.signal_universe))
        self.signal_returns = self.signal_prices.pct_change(fill_method=None)
        self.exogenous_universe = self._resample(self.market_frequency, self._parse_universe(self.exogenous_tickers)) \
                            if set(self.exogenous_tickers).issubset(self.store.prices.columns) else pd.DataFrame()        
        self.market_returns = self._build_market_returns()

    @property
    def asset_class_map(self):
        """Return a mapping of asset classes for the investment universe."""
        return MarketMetadata.build_asset_class_map(self.investment_universe)
    
    @property
    def sector_map(self):
        """Return a mapping of sectors for the investment universe."""
        return MarketMetadata.build_sector_map(self.investment_universe)

    @property
    def sector_dict(self) -> dict:
        """Return a dictionary mapping tickers to their corresponding sectors in the investment universe."""
        return self.store.sectors[self.investment_universe].to_dict()
    
    @property
    def sectors_to_tickers(self) -> dict:
        """Return a dictionary mapping sectors to their corresponding tickers in the investment universe."""
        sectors_to_tickers: dict[str, list] = {}
        for ticker, sector in self.sector_dict.items():
            if sector and ticker in self.investment_prices.columns:
                sectors_to_tickers.setdefault(sector, []).append(ticker)
        return sectors_to_tickers

    @property
    def market_caps(self):
        """Return the market capitalizations of the assets in the investment universe."""
        return self.store.market_caps[self.investment_universe]
    
    @property
    def etf_market_caps(self):
        """Return the market capitalizations of the ETFs in the investment universe."""
        return self.store.etf_market_caps[self.investment_universe]
        
    def _parse_universe(self, tickers: list) -> pd.DataFrame:
        """Parse the given list of tickers and return their corresponding price data from the store."""
        return self.store.prices[tickers]
        
    def _resample(self, market_frequency: str, universe: pd.DataFrame) -> pd.DataFrame:
        """Resample the given universe of prices to the specified market frequency."""
        if market_frequency == "d":
            return universe

        rule = {"w": "W-FRI", "m": "ME"}[market_frequency]
        return universe.resample(rule).last()

    def tradable(self, cursor: Optional[int] = None) -> pd.Series:
        """Boolean mask over the investment universe: True where the asset has a price at
        ``cursor`` and a complete (NaN-free) lookback window of returns, so signals for it are
        fully estimated. Strategies and the optimizer must give every other asset zero weight."""
        cursor = self.cursor if cursor is None else cursor
        has_price = self.investment_prices.iloc[cursor].notna() & (self.investment_prices.iloc[cursor] > 0)
        start = max(cursor - self.lookback_window, 1)       # row 0 of pct_change is always NaN
        window = self.investment_returns.iloc[start:cursor]
        full_window = window.notna().all() if len(window) else pd.Series(True, index=window.columns)
        mask = has_price & full_window
        return mask.reindex(self.investment_universe).fillna(False).astype(bool)

    def advance(self):
        """Advance the market state cursor by one step."""
        self.cursor += 1

    def lookback_prices(self) -> pd.DataFrame:
        """Return the historical prices of the investment universe over the lookback window."""
        window = self.investment_prices.iloc[
            self.cursor - self.lookback_window : self.cursor
        ]
        return window

    def lookback_returns(self) -> pd.DataFrame:
        """Return the historical returns of the investment universe over the lookback window."""
        lookback_returns = self.investment_returns.iloc[
            self.cursor - self.lookback_window : self.cursor
        ]
        return lookback_returns
    
    def signal_lookback_prices(self) -> pd.DataFrame:
        """Return the historical prices of the signal universe over the lookback window."""
        window = self.signal_prices.iloc[
            self.cursor - self.lookback_window : self.cursor
        ]
        return window

    def signal_lookback_returns(self) -> pd.DataFrame:
        """Return the historical returns of the signal universe over the lookback window."""
        lookback_returns = self.signal_returns.iloc[
            self.cursor - self.lookback_window : self.cursor
        ]
        return lookback_returns    
    
    def signal_normalized_prices(self) -> pd.DataFrame:
        """Return the normalized historical prices of the signal universe over the lookback window."""
        w = self.signal_lookback_prices()
        return w / w.iloc[0]
    
    def normalized_prices(self) -> pd.DataFrame:
        """Return the normalized historical prices of the investment universe over the lookback window."""
        w = self.lookback_prices()
        return w / w.iloc[0]
    
    def current_date(self) -> datetime:
        """Return the current date of the market state cursor."""
        return self.investment_prices.index[self.cursor]
    
    def has_next(self) -> bool:
        """Return True if there are more steps to advance in the market state."""
        return self.cursor < len(self.investment_prices) - 1

    def _build_market_returns(self) -> Optional[pd.Series]:
        """Build and return the market returns series based on the benchmark in the store."""
        benchmark = getattr(self.store, "benchmark", None)
        if benchmark is not None and benchmark not in self.store.prices.columns:
            raise ValueError(f"Benchmark ticker {benchmark!r} is missing from market prices")
        benchmark_prices = self.store.prices[[benchmark]] if benchmark is not None else None
        market_returns = (
            self._resample(self.market_frequency, benchmark_prices)[benchmark]
            .pct_change(fill_method=None)
            .fillna(0)
            .reindex(self.investment_returns.index)
            if benchmark_prices is not None
            else None
        )
        return market_returns