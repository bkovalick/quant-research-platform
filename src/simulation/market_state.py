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
        self._pit_members: set = set()
        self.state_config = state_config
        self.lookback_window_key = state_config.lookback_window_key
        self.market_frequency = state_config.market_frequency
        self.lookback_window = state_config.lookback_window
        self.exogenous_tickers = state_config.exogenous_tickers
        self.cash_allocation = state_config.cash_allocation
        self.annual_trading_days = state_config.annual_trading_days
        self.setup(store, state_config)

    def setup(self, store: MarketDataStore, state_config: MarketStateConfig):
        """Initialize the market state by setting up the investment and signal prices, returns, and exogenous universe."""
        self.cursor = 0
        self.investment_universe = self._build_investment_universe(store, state_config)
        self.signal_universe = [t for t in self.investment_universe if t != "CASH"]
        self.investment_prices = self._resample(self.market_frequency, self._parse_universe(self.investment_universe))
        self.investment_returns = self.investment_prices.pct_change(fill_method=None)
        self.valuation_prices = self.investment_prices.ffill()
        self.signal_prices = self._resample(self.market_frequency, self._parse_universe(self.signal_universe))
        self.signal_returns = self.signal_prices.pct_change(fill_method=None)
        self.exogenous_universe = self._resample(self.market_frequency, self._parse_universe(self.exogenous_tickers)) \
                            if set(self.exogenous_tickers).issubset(self.store.prices.columns) else pd.DataFrame()        
        self.market_returns = self._build_market_returns()
        self.fundamental_data_by_metric = self._build_and_align_fundamental_data(store, self.signal_prices)

    @property
    def asset_class_map(self) -> dict:
        """Return a mapping of asset classes for the investment universe."""
        return MarketMetadata.build_asset_class_map(self.investment_universe)
    
    @property
    def sector_map(self) -> dict:
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
    def market_caps(self) -> pd.Series:
        """Return the market capitalizations of the assets in the investment universe."""
        return self.store.market_caps[self.investment_universe]
    
    def tradable(self, cursor: Optional[int] = None) -> pd.Series:
        """Return a boolean mask indicating which assets are tradable at the given cursor position."""
        cursor = self.cursor if cursor is None else cursor
        has_price = self.investment_prices.iloc[cursor].notna() & (self.investment_prices.iloc[cursor] > 0)
        start = max(cursor - self.lookback_window, 1)
        window = self.investment_returns.iloc[start:cursor]
        full_window = window.notna().all() if len(window) else pd.Series(True, index=window.columns)
        eligible = self._index_members(cursor).reindex(has_price.index).fillna(False).astype(bool)
        mask = has_price & full_window & eligible
        return mask.reindex(self.investment_universe).fillna(False).astype(bool)

    def _index_members(self, cursor: int) -> pd.Series:
        """Return a boolean mask indicating which tickers are eligible based on S&P 500 membership and explicit listings."""
        columns = self.investment_prices.columns
        if not self._pit_members:
            return pd.Series(True, index=columns)
        universe = self.store.historical_sp500_universe
        snapshots = universe.loc[:self.investment_prices.index[cursor]]
        members = set()
        if len(snapshots):
            members = {t.strip() for t in str(snapshots["tickers"].iloc[-1]).split(",")}
        return pd.Series([t not in self._pit_members or t in members for t in columns], index=columns)

    def advance(self) -> None:
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

    def _build_investment_universe(self, 
                                   store: MarketDataStore, state_config: MarketStateConfig) -> list:
        """Explicit tickers, or (include_sp500_members) every historical S&P 500 member with
        prices plus the explicit tickers. CASH stays last: cash-aware weights rely on it."""
        explicit = list(state_config.investment_universe)
        has_cash = "CASH" in explicit
        listed = [t for t in explicit if t != "CASH"]
        if not getattr(state_config, "include_sp500_members", False):
            if not listed:
                raise ValueError("investment_universe is empty: list tickers, or set "
                                 "include_sp500_members with a historical_sp500_tickers_path")
            return explicit

        if getattr(store, "_historical_sp500_universe", None) is None:
            raise ValueError("include_sp500_members needs market_store_config.historical_sp500_tickers_path")
        priced = set(store.prices.columns)
        members = sorted(t for t in store.historical_sp500_tickers if t in priced)
        self._pit_members = set(members)
        extras = [t for t in listed if t not in self._pit_members]
        return members + extras + (["CASH"] if has_cash else [])

    def _build_and_align_fundamental_data(self, 
                                          store: MarketDataStore, 
                                          signal_prices: pd.DataFrame) -> Optional[dict]:
        """Fundamentals by metric on the signal grid (same index and columns as signal_prices),
        or None if unavailable. A value is usable from the trading day after it was filed."""
        metric_data = getattr(store, "fundamental_data_by_metric", None)
        if metric_data is None:
            return None
        daily_fnd_data = {}
        for metric, data in metric_data.items():
            daily_index = store.prices.index.union(data.index)
            daily = data.reindex(daily_index).ffill(limit=400).shift(1)
            daily_fnd_data[metric] = daily.reindex(index=signal_prices.index, columns=signal_prices.columns)
        return daily_fnd_data
    
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

    def _parse_universe(self, tickers: list) -> pd.DataFrame:
        """Parse the given list of tickers and return their corresponding price data from the store."""
        return self.store.prices[tickers]
        
    def _resample(self, 
                  market_frequency: str, 
                  universe: pd.DataFrame) -> pd.DataFrame:
        """Resample the given universe of prices to the specified market frequency."""
        if market_frequency == "d":
            return universe

        rule = {"w": "W-FRI", "m": "ME"}[market_frequency]
        return universe.resample(rule).last()    