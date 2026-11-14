import pandas as pd
import logging
import os
from pathlib import Path

from infrastructure.market_data_gateway import MarketDataGateway
from infrastructure.fundamental_data_gateway import FundamentalDataGateway
from models.market_config import MarketStoreConfig

logger = logging.getLogger(__name__)

MAX_FILL_DAYS = 5
FUNDAMENTAL_LOOKBACK_DAYS = 730
REPO_ROOT = Path(__file__).resolve().parents[2]

class MarketDataStore:
    """ Environment to interact with market data gateway """
    def __init__(self, 
                 market_store_config: MarketStoreConfig):
        """ Initialize with market data gateway and parameters """
        self.benchmark = market_store_config.benchmark
        self.transaction_cost = market_store_config.transaction_cost
        self.apply_market_caps = market_store_config.apply_market_caps
        self.fundamental_data_source = market_store_config.fundamental_data_source
        logger.info("Initializing MarketDataStore for %s to %s", market_store_config.start_date, market_store_config.end_date)
        self._prices = self.get_prices(market_store_config)
        self._prices = self._prices.sort_index()
        self._prices = self._prices.where(self._prices > 0)
        self._prices = self._prices.dropna(how='all')
        self._market_caps = None
        self._sectors = None

        if len(self._prices) == 0:
            raise ValueError("Market Data Store not created properly, please check inputs.")

        self._raw_fundamental_data = self._load_fundamental_data(market_store_config)

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

        members = self._get_historical_sp500_tickers(self._historical_sp500_universe)
        member_set = set(members)
        extras = [t for t in market_store_config.tickers if t not in member_set]
        return MarketDataGateway.get_price_data(market_store_config, members + extras)

    def _load_fundamental_data(self, market_store_config: MarketStoreConfig) -> pd.DataFrame | None:
        """Fundamentals for every priced ticker, or None when no source is configured. The window
        opens FUNDAMENTAL_LOOKBACK_DAYS before the price start so that filings made before the
        first backtest date are available on day one."""
        if not self.fundamental_data_source:
            return None
        tickers = [t for t in self._prices.columns if t != "CASH"]
        start = pd.Timestamp(market_store_config.start_date) - pd.Timedelta(days=FUNDAMENTAL_LOOKBACK_DAYS)
        return FundamentalDataGateway.get_fundamental_market_data(
            self.fundamental_data_source, tickers, start, market_store_config.end_date
        )

    def _get_historical_sp500_universe(self, ticker_path: str) -> pd.DataFrame:
        """ Load historical S&P 500 universe from CSV file """
        path = Path(ticker_path)
        ticker_path = str(path if path.is_absolute() else REPO_ROOT / path)
        if not os.path.exists(ticker_path):
            raise FileNotFoundError(f"Ticker file not found: {ticker_path}")
        return pd.read_csv(ticker_path, index_col=0, parse_dates=True).sort_index()

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
    def sectors(self) -> pd.Series:
        if self._sectors is None:
            self._sectors = MarketDataGateway.get_sector_data(self.prices.columns.tolist())
        return pd.Series(self._sectors).fillna("Unknown")

    @property
    def fundamental_data(self) -> pd.DataFrame | None:
        """Long-format fundamentals, or None when the config has no fundamental_data_source."""
        return self._raw_fundamental_data

    @property
    def fundamental_data_by_metric(self) -> dict[str, pd.DataFrame]:
        if self._raw_fundamental_data is None:
            return {}
        result = {}
        for metric in self._raw_fundamental_data["metric"].unique():
            metric_data = self._raw_fundamental_data[self._raw_fundamental_data["metric"] == metric]
            metric_data = metric_data.pivot_table(index="filing_date", columns="ticker", values="value", aggfunc="last")
            result[metric] = metric_data
        return result