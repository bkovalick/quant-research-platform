import pandas as pd
import logging
import os

from infrastructure.market_data_gateway import MarketDataGateway
from models.market_config import MarketStoreConfig

logger = logging.getLogger(__name__)

MAX_FILL_DAYS = 5

class MarketDataStore:
    """ Environment to interact with market data gateway """
    def __init__(self, 
                 market_store_config: MarketStoreConfig):
        """ Initialize with market data gateway and parameters """
        self.benchmark = market_store_config.benchmark
        self.transaction_cost = market_store_config.transaction_cost
        self.apply_market_caps = market_store_config.apply_market_caps
        logger.info("Initializing MarketDataStore for %s to %s", market_store_config.start_date, market_store_config.end_date)
        self._prices = self.get_prices(market_store_config)
        self._prices = self._prices.sort_index()
        self._prices = self._prices.dropna(how='all')
        self._market_caps = None
        self._etf_market_caps = None
        self._sectors = None

        if len(self._prices) == 0:
            raise ValueError("Market Data Store not created properly, please check inputs.")

        logger.info("Loaded market prices with shape %s", self._prices.shape)
        self._prices = self._prices.ffill(limit=MAX_FILL_DAYS)
        if "CASH" not in self._prices.columns:
            daily_rate = market_store_config.risk_free_rate / 252
            n = len(self._prices)
            self._prices["CASH"] = (1 + daily_rate) ** pd.Series(range(n), index=self._prices.index)

    def get_prices(self, market_store_config: MarketStoreConfig) -> pd.DataFrame:
        """ Get price data based on market store configuration """
        if market_store_config.historical_sp500_tickers_path is None:
            return MarketDataGateway.get_price_data(market_store_config)
        
        self._historical_sp500_universe = self._get_historical_sp500_universe(
            market_store_config.historical_sp500_tickers_path
        )
        return MarketDataGateway.get_price_data(
            market_store_config, 
            self._get_historical_sp500_tickers(self._historical_sp500_universe)
        )

    def _get_historical_sp500_universe(self, ticker_path: str) -> pd.DataFrame:
        """ Load historical S&P 500 universe from CSV file """
        if not os.path.exists(ticker_path):
            raise FileNotFoundError(f"Ticker file not found: {ticker_path}")
        return pd.read_csv(ticker_path, index_col=0, parse_dates=True)

    def _get_historical_sp500_tickers(self, historical_sp500_universe: pd.DataFrame) -> list[str]:
        """Return distinct historical tickers in order of first appearance."""
        if historical_sp500_universe is None:
            raise ValueError("Historical S&P 500 tickers not loaded.")
        
        tickers = {}
        for date, row in historical_sp500_universe["tickers"].items():
            if isinstance(row, str):
                row = row.split(",")
            if not isinstance(row, (list, tuple)):
                raise ValueError(f"Invalid ticker list for {date}: {row!r}")
            for ticker in row:
                if not isinstance(ticker, str) or not ticker.strip():
                    raise ValueError(f"Invalid ticker for {date}: {ticker!r}")
                tickers[ticker.strip()] = None
        return list(tickers)

    @property
    def historical_sp500_universe(self) -> pd.DataFrame:
        if not hasattr(self, "_historical_sp500_universe"):
            raise ValueError("Historical S&P 500 universe not loaded.")
        return self._historical_sp500_universe

    @property
    def historical_sp500_tickers(self) -> list:
        if not hasattr(self, "_historical_sp500_universe"):
            raise ValueError("Historical S&P 500 universe not loaded.")
        return self._get_historical_sp500_tickers(self._historical_sp500_universe)

    @property
    def prices(self) -> pd.DataFrame:
        return self._prices
    
    @property
    def market_caps(self) -> pd.Series:
        if not self.apply_market_caps:
            return pd.Series(dtype=float)
        if self._market_caps is None:
            self._market_caps = MarketDataGateway.get_market_caps(self.prices.columns.tolist())
            if "CASH" not in self._market_caps:
                self._market_caps["CASH"] = 0
        return pd.Series(self._market_caps).fillna(0)
    
    @property
    def etf_market_caps(self) -> pd.Series:
        if not self.apply_market_caps:
            return pd.Series(dtype=float)
        if self._etf_market_caps is None:
            self._etf_market_caps = MarketDataGateway.get_etf_market_caps(self.prices.columns.tolist())
        return pd.Series(self._etf_market_caps).fillna(0)
    
    @property
    def sectors(self) -> pd.Series:
        if self._sectors is None:
            self._sectors = MarketDataGateway.get_sector_data(self.prices.columns.tolist())
        return pd.Series(self._sectors).fillna("Unknown")