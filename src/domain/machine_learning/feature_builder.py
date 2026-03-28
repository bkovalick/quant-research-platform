import pandas as pd
import numpy as np

from utils.lookback_windows import LOOKBACK_WINDOWS
from simulation.market_state import MarketState

class FeatureBuilder:
    """
    Responsible for constructing features and forward 
    returns for ML model training and inference.
    """
    def __init__(self, 
                 market_state: MarketState,
                 benchmark: pd.Series,
                 market_frequency: str = "d"):
        self.prices = market_state.prices.copy()
        self.returns = market_state.returns.copy()
        self.exogenous_universe = market_state.exogenous_universe.copy()
        self.benchmark = benchmark
        self.benchmark_returns = benchmark.pct_change(fill_method=None).fillna(0)
        self.lookbacks = LOOKBACK_WINDOWS.get(market_frequency, LOOKBACK_WINDOWS["d"])
        self.reversal_window = self.lookbacks.get("1w", 1)
        self.features_cache = None
        self.forward_returns_cache = None

    def precompute(self, horizon: int = 21):
        """
        Precompute features for all dates and cache them in memory for 
        fast retrieval during training/inference.
        """
        features_cache = {}
        fwd_returns_cache = {}
        for date in self.prices.index[self.lookbacks["1y"]:]:
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
        market_rets = self.benchmark_returns.loc[:date]
        vix_prices = self.exogenous_universe["^VIX"].loc[:date] \
            if "^VIX" in self.exogenous_universe else pd.Series(dtype=float)
        high_vol = self._compute_high_vol(vix_prices)

        if len(px) < self.lookbacks["1y"]:
            return pd.DataFrame(index=self.prices.columns)

        features = pd.DataFrame(index=self.prices.columns)
        features["mom_1m"]   = px.iloc[-1] / px.iloc[-self.lookbacks["1m"]] - 1          # Short-term momentum: 1-month price return
        features["mom_12m"]  = px.iloc[-self.lookbacks["1m"]] / px.iloc[-self.lookbacks["1y"]] - 1  # Long-term momentum: 2–12 month price return, skipping the most recent month to avoid reversal contamination
        features["vol_1m"]   = rets.iloc[-self.lookbacks["1m"]:].std()                    # Realised volatility over the past month
        features["vol_3m"]   = rets.iloc[-self.lookbacks["3m"]:].std()                    # Realised volatility over the past quarter
        features["reversal"] = -(px.iloc[-1] / px.iloc[-(self.reversal_window + 1)] - 1)  # Short-term reversal: negative 1-week return, capturing mean-reversion of recent winners/losers
        features["mom_x_vol_regime"] = features["mom_12m"] * (1 - high_vol)  # momentum only in low vol
        features["reversal_x_vol_regime"] = features["reversal"] * high_vol  # reversal only in high vol
        features["max_return"] = rets.iloc[-self.lookbacks["1m"]:].max()
        features["high_52w"] = px.iloc[-1] / px.iloc[-self.lookbacks["1y"]:].max()
        features["beta_1m"] = self._compute_rolling_beta(rets, market_rets, self.lookbacks["1m"])
        features["beta_1y"] = self._compute_rolling_beta(rets, market_rets, self.lookbacks["1y"])
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
    
    def _compute_high_vol(self, vix_prices: pd.Series) -> float:
        if vix_prices.empty:
            return 0.0
        vix_now = vix_prices.iloc[-1]
        vix_median = vix_prices.iloc[-self.lookbacks["1y"]:].median()
        high_vol = (vix_now > vix_median).astype(float)
        return high_vol

    def _compute_rolling_beta(self, 
                              stock_returns: pd.DataFrame, 
                              market_returns: pd.Series, 
                              window: int = 21) -> pd.Series:
        """ Compute rolling beta of each stock to the market over the specified window. """
        cov_with_market = stock_returns.iloc[-window:].apply(
            lambda col: col.cov(market_returns.iloc[-window:])
        )

        market_variance = market_returns.iloc[-window:].var()

        if market_variance == 0:
            return pd.Series(np.nan, index=stock_returns.columns)
        
        return cov_with_market / market_variance