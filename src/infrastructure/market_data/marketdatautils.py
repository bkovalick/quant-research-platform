import pandas as pd
from os import path

class MarketDataUtils:

    @staticmethod
    def get_lookback_window_mapping():
        """Return mapping of lookback windows for different frequencies and periods."""
        return {
            "d": {"1m": 21, "3m": 63, "6m": 126, "9m": 189, "1y": 252, "5y": 252*5, "10y": 252*10, "20y": 252*20, "30y": 252*30},
            "w": {"1m": 4, "3m": 12, "6m": 26, "9m": 39, "1y": 52, "5y": 52*5, "10y": 52*10, "20y": 52*20, "30y": 52*30},
            "m": {"1m": 1, "3m": 3, "6m": 6, "9m": 9, "1y": 12, "5y": 12*5, "10y": 12*10, "20y": 12*20, "30y": 12*30},
            "q": {"3m": 1, "6m": 2, "9m": 3, "1y": 4, "5y": 4*5, "10y": 4*10, "20y": 4*20, "30y": 4*30},
            "y": {"1y": 1, "5y": 5, "10y": 10, "20y": 20, "30y": 30},
        }
    
    @staticmethod
    def get_universe_tickers() -> list:
        """ Get combined universe tickers from fixed income and equity """
        fi_tickers = MarketDataUtils.get_fixed_income_mapping_universe()['ticker'].tolist()
        equity_tickers = MarketDataUtils.get_equity_mapping_universe()['ticker'].tolist()
        return fi_tickers + equity_tickers
    
    @staticmethod
    def get_fixed_income_mapping_universe() -> pd.DataFrame:
        """ Get fixed income universe dataframe """
        if not path.exists("data/fixed_income_universe.csv"):
            raise FileNotFoundError("Fixed income universe file not found.")
        return pd.read_csv("data/fixed_income_universe.csv")
        
    @staticmethod
    def get_fixed_income_sector_mapping() -> dict:
        """ Get sector mapping for fixed income """
        df = MarketDataUtils.get_fixed_income_mapping_universe()
        sector_mapping = df.set_index('ticker')['sector'].to_dict()
        return sector_mapping

    @staticmethod
    def get_fixed_income_asset_class_mapping() -> dict:
        """ Get asset class mapping for fixed income """
        df = MarketDataUtils.get_fixed_income_mapping_universe()
        asset_class_mapping = df.set_index('ticker')['asset_class'].to_dict()
        return asset_class_mapping
    
    @staticmethod
    def get_equity_mapping_universe() -> pd.DataFrame:
        """ Get equity universe dataframe """
        if not path.exists("data/equity_universe.csv"):
            raise FileNotFoundError("Equity universe file not found.")
        return pd.read_csv("data/equity_universe.csv")    

    @staticmethod
    def get_equity_sector_mapping() -> dict:
        """ Get sector mapping for equities """
        df = MarketDataUtils.get_equity_mapping_universe()
        sector_mapping = df.set_index('ticker')['sector'].to_dict()
        return sector_mapping
    
    @staticmethod
    def get_equity_asset_class_mapping() -> dict:
        """ Get asset class mapping for equities """
        df = MarketDataUtils.get_equity_mapping_universe()
        asset_class_mapping = df.set_index('ticker')['asset_class'].to_dict()
        return asset_class_mapping    