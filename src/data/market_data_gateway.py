import yfinance as yf

from models.market_config import MarketStoreConfig
from config.lookback_windows import LOOKBACK_WINDOWS

class MarketDataGateway:
    """ Data gateway for fetching market data using yfinance """
    @staticmethod
    def get_price_data(tickers, start_date, end_date):
        data = yf.download(tickers, start=start_date, end=end_date)
        return data.xs('Close', axis=1, level=0)
    
class MarketDataStore:
    """ Environment to interact with market data gateway """
    def __init__(self, market_store_config: MarketStoreConfig):
        """ Initialize with market data gateway and parameters """
        tickers = market_store_config.tickers
        start_date = market_store_config.start_date
        end_date = market_store_config.end_date
        self._prices = MarketDataGateway.get_price_data(tickers, start_date, end_date)

        self._prices = self._prices.sort_index()
        self._prices = self._prices.dropna(how='all')
        self._prices = self._prices.bfill().ffill()
        if "CASH" not in self._prices.columns:
            self._prices["CASH"] = 1.0

    @property
    def prices(self):
        return self._prices