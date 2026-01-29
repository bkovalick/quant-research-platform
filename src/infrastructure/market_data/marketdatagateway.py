from os import path
import yfinance as yf
import pandas as pd
import numpy as np

class MarketDataGateway:
    """ Data gateway for fetching market data using yfinance """
    @staticmethod
    def get_price_data(tickers, start_date, end_date):
        data = yf.download(tickers, start=start_date, end=end_date)
        return data.xs('Close', axis=1, level=0)
    
class MarketEnvironment:
    """ Environment to interact with market data gateway """

    def __init__(self, gateway = None, market_params = None):
        """ Initialize with market data gateway and parameters """
        self.gateway = gateway or MarketDataGateway()
        self.market_params = market_params
        tickers = [t for t in self.market_params["tickers"] if t.upper() != "CASH"]
        self._market_data = self.gateway.get_price_data(
            tickers, self.market_params["start_date"], self.market_params["end_date"]
        )
        self._market_data["CASH"] = 1.0
        self._market_data = self._market_data[self.market_params["tickers"]]
        self._normalized_prices = None
    
    @property
    def normalized_prices(self) -> pd.DataFrame:
        """ Normalize prices to start at 1 """
        if self._normalized_prices is not None:
            return self._normalized_prices
        normalized = self._market_data / self._market_data.iloc[0]
        normalized = normalized.asfreq(
            self.market_params["trading_frequency"], method='ffill'
        )
        re_normalized = normalized / normalized.iloc[0]
        re_normalized = re_normalized.dropna(axis=0)
        return re_normalized

    @normalized_prices.setter
    def normalized_prices(self, df: pd.DataFrame):
        self._normalized_prices = df

    @property
    def get_universe_tickers(self) -> list:
        """ Get combined universe tickers from fixed income and equity """
        fi_tickers = self.get_fixed_income_mapping_universe['ticker'].tolist()
        equity_tickers = self.get_equity_mapping_universe['ticker'].tolist()
        return fi_tickers + equity_tickers

    @property
    def get_fixed_income_mapping_universe(self) -> pd.DataFrame:
        """ Get fixed income universe dataframe """
        if not path.exists("src/config/fixed_income_universe.csv"):
            raise FileNotFoundError("Fixed income universe file not found.")
        return pd.read_csv("src/config/fixed_income_universe.csv")

    @property
    def get_fixed_income_sector_mapping(self) -> dict:
        """ Get sector mapping for fixed income """
        df = self.get_fixed_income_mapping_universe
        sector_mapping = df.set_index('ticker')['sector'].to_dict()
        return sector_mapping

    @property
    def get_fixed_income_asset_class_mapping(self) -> dict:
        """ Get asset class mapping for fixed income """
        df = self.get_fixed_income_mapping_universe
        asset_class_mapping = df.set_index('ticker')['asset_class'].to_dict()
        return asset_class_mapping
    
    @property
    def get_equity_mapping_universe(self) -> pd.DataFrame:
        """ Get equity universe dataframe """
        if not path.exists("src/config/equity_universe.csv"):
            raise FileNotFoundError("Equity universe file not found.")
        return pd.read_csv("src/config/equity_universe.csv")    

    @property
    def get_equity_sector_mapping(self) -> dict:
        """ Get sector mapping for equities """
        df = self.get_equity_mapping_universe
        sector_mapping = df.set_index('ticker')['sector'].to_dict()
        return sector_mapping
    
    @property
    def get_equity_asset_class_mapping(self) -> dict:
        """ Get asset class mapping for equities """
        df = self.get_equity_mapping_universe
        asset_class_mapping = df.set_index('ticker')['asset_class'].to_dict()
        return asset_class_mapping    

if __name__ == "__main__":
    market_params = {
        "tickers": ["AAPL", "MSFT", "GOOGL"],
        "start_date": "2020-01-01",
        "end_date": "2021-01-01",
        "trading_frequency": "d"
    }

    mkt = MarketEnvironment(market_params=market_params)
    # mkt.fetch_market_data(tickers, "2020-01-01", "2021-01-01")
    print(mkt.normalized_prices)
    print(mkt.mean_returns)
    print(mkt.covariance_matrix)    
    data = mkt.normalized_prices.iloc[100:] # iloc[100:] gets rows from index 100 onwards, [100:] gets first 100 rows
    mkt.normalized_prices = data
    print(mkt.normalized_prices)
    print(mkt.mean_returns)
    print(mkt.covariance_matrix)
