import pandas as pd
import numpy as np
from utils.lookback_windows import LOOKBACK_WINDOWS

class FeatureBuilder:
    def __init__(self, 
                 prices: pd.DataFrame, 
                 returns: pd.DataFrame,
                 market_frequency: str = "d"):
        self.prices = prices
        self.returns = returns
        self._w = LOOKBACK_WINDOWS.get(market_frequency, LOOKBACK_WINDOWS["d"])

    def build(self, date: pd.Timestamp) -> pd.DataFrame:
        """
        Build feature matrix for all assets as of a single date.
        Returns DataFrame of shape (n_assets, n_features), index=tickers.
        No future data is used — all lookbacks are strictly backward-looking.
        """
        px   = self.prices.loc[:date]
        rets = self.returns.loc[:date]

        if len(px) < self._w["1y"]:
            return pd.DataFrame(index=self.prices.columns)

        features = pd.DataFrame(index=self.prices.columns)
        features["mom_1m"]   = px.iloc[-1] / px.iloc[-self._w["1m"]] - 1
        features["mom_12m"]  = px.iloc[-self._w["1m"]] / px.iloc[-self._w["1y"]] - 1  # skip last month
        features["vol_1m"]   = rets.iloc[-self._w["1m"]:].std()
        features["vol_3m"]   = rets.iloc[-self._w["3m"]:].std()
        features["reversal"] = -(px.iloc[-1] / px.iloc[-self._w["1w"]] - 1)

        features = features.rank(axis=0, pct=True)
        return features.dropna()
    
    def build_forward_returns(self,
                               as_of_date: pd.Timestamp, # I think we can pass cursor instead
                               horizon: int = 21) -> pd.Series:
        """
        Forward returns starting from as_of_date over `horizon` days.
        Used as the label (y) during training.
        CRITICAL: only called during training, never at inference time.
        """
        px = self.prices
        idx = px.index.get_loc(as_of_date)
        if idx + horizon >= len(px):
            return pd.Series(dtype=float)
        fwd = px.iloc[idx + horizon] / px.iloc[idx] - 1
        return fwd