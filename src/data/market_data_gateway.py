import yfinance as yf
import pandas as pd
from models.market_config import MarketStoreConfig
from config.lookback_windows import LOOKBACK_WINDOWS

class MarketDataGateway:
    """ Data gateway for fetching market data using yfinance """
    @staticmethod
    def get_price_data(market_store_config: MarketStoreConfig):
        data_source = market_store_config.data_source
        tickers = market_store_config.data_source
        start_date = market_store_config.data_source
        end_date = market_store_config.data_source
        csv_file = market_store_config.csv_file
        match data_source:
            case "yfinance":
                return MarketDataGateway.get_price_data_y_finance(tickers, start_date, end_date)
            case "csv":
                return MarketDataGateway.get_price_data_csv(csv_file)
            case _:
                raise ValueError(f"Unknown source type: {data_source}")            

    @staticmethod
    def get_price_data_y_finance(tickers, start_date, end_date):
        data = yf.download(tickers, start=start_date, end=end_date)
        return data.xs('Close', axis=1, level=0)        

    @staticmethod
    def get_price_data_csv(csv_file):
        return pd.read_csv(csv_file)

class MarketDataStore:
    """ Environment to interact with market data gateway """
    def __init__(self, market_store_config: MarketStoreConfig):
        """ Initialize with market data gateway and parameters """
        self._prices = MarketDataGateway.get_price_data(market_store_config)

        self._prices = self._prices.sort_index()
        self._prices = self._prices.dropna(how='all')
        self._prices = self._prices.bfill().ffill()
        if "CASH" not in self._prices.columns:
            self._prices["CASH"] = 1.0

    @property
    def prices(self):
        return self._prices