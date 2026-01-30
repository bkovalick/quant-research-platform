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
        self._market_data = pd.concat([self._market_data, pd.DataFrame(1.0, \
                                index=self._market_data.index, columns=["CASH"])], axis=1)
        self._market_data = self._market_data[self.market_params["tickers"]]
        tickers_not_in_market_data = [ticker for ticker in tickers \
                                      if ticker not in self._market_data.columns]
        if len(tickers_not_in_market_data) > 0:
            raise ValueError(f"Tickers not found in market data: {tickers_not_in_market_data}")
        
        self._normalized_prices = None
    
    @property
    def normalized_prices(self) -> pd.DataFrame:
        """ Normalize prices to start at 1 """
        if self._normalized_prices is not None:
            return self._normalized_prices
        
        trading_frequency = self.market_params["trading_frequency"]
        if trading_frequency == 'w':
            trading_frequency = 'W'
        normalized = self._market_data / self._market_data.iloc[0]
        normalized = normalized.asfreq(trading_frequency, method='ffill')
        re_normalized = normalized / normalized.iloc[0]

        for col in re_normalized.columns:
            if re_normalized[col].notna().any():
                re_normalized[col] = re_normalized[col].ffill()
            else:
                re_normalized[col] = 1.0
        return re_normalized

    @normalized_prices.setter
    def normalized_prices(self, df: pd.DataFrame):
        self._normalized_prices = df 

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
