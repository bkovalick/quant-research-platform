import pandas as pd
import numpy as np

class FeatureBuilder:
    def __init__(self, 
                 prices: pd.DataFrame, 
                 returns: pd.DataFrame):
        self.prices = prices
        self.returns = returns

    def build(self, date: pd.Timestamp):
        """
        Build feature matrix for all assets as of a single date.
        Returns DataFrame of shape (n_assets, n_features), index=tickers.
        No future data is used — all lookbacks are strictly backward-looking.
        """
        px   = self.prices.loc[:date]
        rets = self.returns.loc[:date]

        features = pd.DataFrame(index=self.prices.columns)
        features["mom_1m"]   = px.iloc[-1] / px.iloc[-21]  - 1
        features["mom_12m"]  = px.iloc[-21] / px.iloc[-252] - 1   # skip last month, this breaks outside of the backtest engine b/c it needs a lookback date check
        features["vol_1m"]   = rets.iloc[-21:].std()
        features["vol_3m"]   = rets.iloc[-63:].std()
        features["reversal"] = -(px.iloc[-1] / px.iloc[-6] - 1)   # negative = reversal

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