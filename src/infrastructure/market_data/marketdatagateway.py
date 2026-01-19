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
    def __init__(self, gateway=None, market_params = None):
        self.gateway = gateway or MarketDataGateway()
        self.market_params = market_params
        self._market_data = self.gateway.get_price_data(
            self.market_params["tickers"], self.market_params["start_date"], self.market_params["end_date"]
        )
        self._normalized_prices = None
    
    def fetch_market_data(self, tickers, start_date, end_date):
        self._market_data = self.gateway.get_price_data(tickers, start_date, end_date)
        self._market_data["CASH"] = 1.0

    @property
    def normalized_prices(self) -> pd.DataFrame:
        """ Normalize prices to start at 1 """
        if self._normalized_prices is not None:
            return self._normalized_prices
        normalized = self._market_data / self._market_data.iloc[0]
        normalized = normalized.asfreq(
            self.market_params["trading_frequency"], method='ffill'
        )

        normalized = normalized.dropna(axis = 0)        
        return normalized
    
    @normalized_prices.setter
    def normalized_prices(self, df: pd.DataFrame):
        self._normalized_prices = df
        
    @property
    def returns_data(self) -> pd.DataFrame:
        """ Calculate returns from price data """
        return self.normalized_prices.pct_change().iloc[1:]
    
    @property
    def covariance_matrix(self) -> np.ndarray:
        """ Calculate covariance matrix from returns data """
        return np.cov(self.returns_data, rowvar = False)
    
    @property
    def mean_returns(self) -> np.ndarray:
        """ Calculate mean returns from returns data """
        return np.array(self.returns_data.mean())
    
if __name__ == "__main__":
    # from portfolio.rebalance_problem_builder import RebalanceProblemBuilder
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
