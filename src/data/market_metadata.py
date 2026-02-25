import pandas as pd
from os import path

class MarketMetadata:
    @staticmethod
    def build_asset_class_map(tickers_with_cash: list) -> dict:
        """Build a mapping from asset class to list of indices in tickers_with_cash."""
        full_mapping_df = MarketMetadata.get_full_mapping_universe()
        asset_class_df = full_mapping_df[full_mapping_df['ticker'].isin(tickers_with_cash)]
        ticker_to_index = {ticker: idx for idx, ticker in enumerate(tickers_with_cash)}
        asset_class_map = asset_class_df.groupby('asset_class')['ticker'].apply(
            lambda tickers: [(ticker_to_index[ticker], ticker) for ticker in tickers if ticker in ticker_to_index]
        ).to_dict()

        if "CASH" in tickers_with_cash:
            cash_idx = tickers_with_cash.index("CASH")
            asset_class_map.update({"Cash": (cash_idx, "CASH")})
        return asset_class_map
    
    @staticmethod
    def build_sector_map(tickers_with_cash) -> dict:
        """Build and asset/sector grouping related to the assets in the investable universe."""
        full_mapping_df = MarketMetadata.get_full_mapping_universe()
        sector_df = full_mapping_df[full_mapping_df['ticker'].isin(tickers_with_cash)]
        ticker_to_index = {ticker: idx for idx, ticker in enumerate(tickers_with_cash)}
        sector_map = sector_df.groupby('sector')['ticker'].apply(
            lambda tickers: [(ticker_to_index[ticker], ticker) for ticker in tickers if ticker in ticker_to_index]
        ).to_dict()
        
        if "CASH" in tickers_with_cash:
            cash_idx = tickers_with_cash.index("CASH")
            sector_map.update({"Cash": (cash_idx, "CASH")})
        return sector_map
        
    
    def get_universe_tickers() -> list:
        """ Get combined universe tickers from fixed income and equity """
        fi_tickers = MarketMetadata.get_fixed_income_mapping_universe()['ticker'].tolist()
        equity_tickers = MarketMetadata.get_equity_mapping_universe()['ticker'].tolist()
        return fi_tickers + equity_tickers
    
    @staticmethod
    def get_full_mapping_universe() -> dict:
        fixed_income_df = MarketMetadata.get_fixed_income_mapping_universe()
        equity_df = MarketMetadata.get_equity_mapping_universe()
        combined = pd.concat([fixed_income_df, equity_df], axis = 0)
        return combined
    
    @staticmethod
    def get_fixed_income_mapping_universe() -> pd.DataFrame:
        """ Get fixed income universe dataframe """
        if not path.exists("data/fixed_income_universe.csv"):
            raise FileNotFoundError("Fixed income universe file not found.")
        return pd.read_csv("data/fixed_income_universe.csv")
        
    @staticmethod
    def get_fixed_income_sector_mapping() -> dict:
        """ Get sector mapping for fixed income """
        df = MarketMetadata.get_fixed_income_mapping_universe()
        sector_mapping = df.set_index('ticker')['sector'].to_dict()
        return sector_mapping

    @staticmethod
    def get_fixed_income_asset_class_mapping() -> dict:
        """ Get asset class mapping for fixed income """
        df = MarketMetadata.get_fixed_income_mapping_universe()
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
        df = MarketMetadata.get_equity_mapping_universe()
        sector_mapping = df.set_index('ticker')['sector'].to_dict()
        return sector_mapping
    
    @staticmethod
    def get_equity_asset_class_mapping() -> dict:
        """ Get asset class mapping for equities """
        df = MarketMetadata.get_equity_mapping_universe()
        asset_class_mapping = df.set_index('ticker')['asset_class'].to_dict()
        return asset_class_mapping    