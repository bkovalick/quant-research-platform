import os
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
    def get_price_data(market_store_config: MarketStoreConfig, tickers: list = None):
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
    def get_price_data_csv(csv_file: str):
        logger.info("Loading price data from CSV %s", csv_file)
        if not os.path.exists(csv_file):
            raise FileNotFoundError(f"CSV file not found: {csv_file}")
        return pd.read_csv(csv_file, index_col=0, parse_dates=True)