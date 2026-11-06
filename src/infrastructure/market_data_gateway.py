import logging
import yfinance as yf
import pandas as pd

from models.market_config import MarketStoreConfig
from infrastructure.market_data_cache import MarketDataCache, cache_enabled

logger = logging.getLogger(__name__)

SECTOR_MAX_AGE_DAYS = 180
MARKET_CAP_MAX_AGE_DAYS = 7

class MarketDataGateway:
    """ Data gateway for fetching market data using yfinance """
    @staticmethod
    def get_price_data(
        market_store_config: MarketStoreConfig,
        tickers: list = None):

        tickers = tickers if tickers is not None else market_store_config.tickers
        benchmark_ticker = market_store_config.benchmark
        if benchmark_ticker not in tickers:
            tickers.append(benchmark_ticker)
        data_source = market_store_config.data_source
        start_date = market_store_config.start_date
        end_date = market_store_config.end_date
        logger.info(
            "Fetching market data for %s tickers from source %s",
            len(tickers),
            list(data_source.keys()),
        )
        
        for source, content in data_source.items():
            if source == "yfinance":
                return MarketDataGateway.get_price_data_y_finance(tickers, start_date, end_date)
            elif source == "csv":
                return MarketDataGateway.get_price_data_csv(content)
            else:
                raise ValueError(f"Unknown source type: {data_source}")

    @staticmethod
    def get_sector_data(tickers: list) -> dict:
        return MarketDataGateway._get_info_field(tickers, "sector", SECTOR_MAX_AGE_DAYS)

    @staticmethod
    def get_market_caps(tickers: list) -> dict:
        caps = MarketDataGateway._get_info_field(tickers, "marketCap", MARKET_CAP_MAX_AGE_DAYS)
        return {ticker: value or 0 for ticker, value in caps.items()}

    @staticmethod
    def get_etf_market_caps(tickers: list) -> dict:
        caps = MarketDataGateway._get_info_field(tickers, "totalAssets", MARKET_CAP_MAX_AGE_DAYS)
        return {ticker: value or 0 for ticker, value in caps.items()}

    @staticmethod
    def _get_info_field(tickers: list, field: str, max_age_days: float) -> dict:
        """One yfinance ``Ticker.info`` field per ticker, via the on-disk cache unless it's turned off."""
        fetch_info = lambda ticker: yf.Ticker(ticker).info
        if cache_enabled():
            return MarketDataCache().get_info(tickers, field, fetch_info, max_age_days)
        out = {}
        for ticker in tickers:
            try:
                out[ticker] = fetch_info(ticker).get(field)
            except Exception as e:
                logger.warning("Could not fetch %s for %s: %s", field, ticker, e)
                out[ticker] = None
        return out

    @staticmethod
    def get_price_data_y_finance(tickers, start_date, end_date):
        """Close prices, served from the on-disk cache; only missing tickers/dates are downloaded."""
        if not cache_enabled():
            return MarketDataGateway._download_close(tickers, start_date, end_date)
        return MarketDataCache().get_close(tickers, start_date, end_date, MarketDataGateway._download_close)

    @staticmethod
    def _download_close(tickers, start_date, end_date) -> pd.DataFrame:
        logger.info("Downloading price data from yfinance for %s tickers (%s to %s)", len(tickers), start_date, end_date)
        data = yf.download(list(tickers), start=start_date, end=end_date, progress=False)
        logger.debug("Downloaded yfinance data with shape %s", getattr(data, "shape", None))
        return data.xs('Close', axis=1, level=0)

    @staticmethod
    def get_price_data_csv(csv_file):
        logger.info("Loading price data from CSV %s", csv_file)
        return pd.read_csv(csv_file)

    @staticmethod
    def get_sp500_tickers() -> list:
        """Fetches the current S&P 500 ticker list from Wikipedia."""
        url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
        table = pd.read_html(url)
        df = table[0]

        tickers = df["Symbol"].str.replace(".", "-", regex=False).tolist()
        return tickers
    

class MarketDataStore:
    """ Environment to interact with market data gateway """
    def __init__(self, 
                 market_store_config: MarketStoreConfig):
        """ Initialize with market data gateway and parameters """
        self.benchmark = market_store_config.benchmark
        self.transaction_cost = market_store_config.transaction_cost
        self.apply_market_caps = market_store_config.apply_market_caps
        logger.info("Initializing MarketDataStore for %s to %s", market_store_config.start_date, market_store_config.end_date)
        self._prices = MarketDataGateway.get_price_data(market_store_config)
        self._prices = self._prices.sort_index()
        self._prices = self._prices.dropna(how='all')
        self._market_caps = None
        self._etf_market_caps = None
        self._sectors = None

        if len(self._prices) == 0:
            raise ValueError("Market Data Store not created properly, please check inputs.")

        logger.info("Loaded market prices with shape %s", self._prices.shape)
        
        self._prices = self._prices.bfill().ffill()
        if "CASH" not in self._prices.columns:
            daily_rate = market_store_config.risk_free_rate / 252
            n = len(self._prices)
            self._prices["CASH"] = (1 + daily_rate) ** pd.Series(range(n), index=self._prices.index)

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