import pandas as pd
from utils.lookback_windows import LOOKBACK_WINDOWS

class FeatureBuilder:
    """
    Responsible for constructing features and forward 
    returns for ML model training and inference.
    """
    def __init__(self, 
                 prices: pd.DataFrame, 
                 returns: pd.DataFrame,
                 exogenous_universe: pd.DataFrame,
                 market_frequency: str = "d"):
        self.prices = prices
        self.returns = returns
        self.exogenous_universe = exogenous_universe
        self.w = LOOKBACK_WINDOWS.get(market_frequency, LOOKBACK_WINDOWS["d"])
        self.reversal_window = self.w.get("1w", 1)
        self.features_cache = None
        self.forward_returns_cache = None

    def precompute(self, horizon: int = 21):
        """
        Precompute features for all dates and cache them in memory for 
        fast retrieval during training/inference.
        """
        features_cache = {}
        fwd_returns_cache = {}
        for date in self.prices.index[self.w["1y"]:]:
            features = self._build_single_date(date)
            if not features.empty:
                features_cache[date] = features

            fwd_returns = self._build_forward_returns_single(date, horizon)
            if not fwd_returns.empty:
                fwd_returns_cache[date] = fwd_returns

        self.features_cache = features_cache
        self.forward_returns_cache = fwd_returns_cache

    def build(self, date: pd.Timestamp) -> pd.DataFrame:
        """
        Build feature matrix for all assets as of a single date, 
        using cached values if available.
        """
        if self.features_cache is not None:
            return self.features_cache.get(date, pd.DataFrame(index = self.prices.columns))
        return self._build_single_date(date)

    def _build_single_date(self, date: pd.Timestamp) -> pd.DataFrame:
        """
        Build feature matrix for all assets as of a single date.
        Returns DataFrame of shape (n_assets, n_features), index=tickers.
        No future data is used — all lookbacks are strictly backward-looking.
        """
        px   = self.prices.loc[:date]
        rets = self.returns.loc[:date]

        if len(px) < self.w["1y"]:
            return pd.DataFrame(index=self.prices.columns)

        features = pd.DataFrame(index=self.prices.columns)
        features["mom_1m"]   = px.iloc[-1] / px.iloc[-self.w["1m"]] - 1
        features["mom_12m"]  = px.iloc[-self.w["1m"]] / px.iloc[-self.w["1y"]] - 1
        features["vol_1m"]   = rets.iloc[-self.w["1m"]:].std()
        features["vol_3m"]   = rets.iloc[-self.w["3m"]:].std()
        features["reversal"] = -(px.iloc[-1] / px.iloc[-(self.reversal_window + 1)] - 1)
        features["vix_level"] = self.exogenous_universe.loc[:date].iloc[-1]
        features = features.rank(axis=0, pct=True)
        return features.dropna()
    
    def build_forward_returns(self,
                              as_of_date: pd.Timestamp,
                              horizon: int = 21) -> pd.Series:
        """
        Build forward returns for all assets starting from as_of_date 
        over `horizon` days, using cached values if available.
        """
        if self.forward_returns_cache is not None:
            return self.forward_returns_cache.get(as_of_date, pd.Series(dtype=float))
        return self._build_forward_returns_single(as_of_date, horizon)

    def _build_forward_returns_single(self,
                              as_of_date: pd.Timestamp,
                              horizon: int = 21) -> pd.Series:
        """
        Forward returns starting from as_of_date over `horizon` days.
        Used as the label (y) during training.
        """
        px = self.prices
        idx = px.index.get_loc(as_of_date)
        if idx + horizon >= len(px):
            return pd.Series(dtype=float)
        fwd = px.iloc[idx + horizon] / px.iloc[idx] - 1
        return fwd