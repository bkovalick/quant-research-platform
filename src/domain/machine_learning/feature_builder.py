from typing import List, Optional

import pandas as pd
import numpy as np
import warnings

from utils.lookback_windows import LOOKBACK_WINDOWS
from simulation.market_state import MarketState

ALL_FEATURES = ["mom_1m", "mom_12m", "vol_1m", "vol_3m", "reversal", "mom_x_vol_regime",
                "reversal_x_vol_regime", "max_return", "high_52w", "beta_1m", "beta_1y", "idiosyncratic_vol"]

class FeatureBuilder:

    def __init__(self, 
                 market_state: MarketState,
                 market_frequency: str = "d",
                 features: Optional[List[str]] = None):
        features = features or []
        self.features = features
        self.prices = market_state.signal_prices.copy()
        self.returns = market_state.signal_returns.copy()
        self.fundamental_data = market_state.fundamental_data_by_metric.copy() \
            if market_state.fundamental_data_by_metric is not None else None
        self.exogenous_universe = market_state.exogenous_universe.copy()
        self.lookbacks = LOOKBACK_WINDOWS.get(market_frequency, LOOKBACK_WINDOWS["d"])
        self.reversal_window = self.lookbacks.get("1w", 1)        
        if market_state.market_returns is None:
            raise ValueError("Benchmark returns are required to build market features")
        
        self.market_returns = market_state.market_returns.reindex(self.returns.index).fillna(0)
        self.features_cache = None
        self.forward_returns_cache = None
        self.precomputed_horizon = None

    def precompute(self, horizon: int = 21):
        """
        Precompute features for all dates and cache them in memory for fast retrieval during training/inference.
        """
        self.precomputed_horizon = horizon
        self.features_cache = self._cache_features()
        self.forward_returns_cache = self._cache_forward_returns(horizon)

    def build(self, date: pd.Timestamp) -> pd.DataFrame:
        """ Build feature matrix for all assets as of a single date, using cached values if available. """
        if self.features_cache is None:
            warnings.warn("FeatureBuilder.precompute() has not been called. Falling back to _build_single_date() which is significantly slower.")
        if self.features_cache is not None:
            return self.features_cache.get(date, pd.DataFrame(index=self.prices.columns))
        return self._build_single_date(date)    

    def _build_single_date(self, date: pd.Timestamp) -> pd.DataFrame:
        """ Build feature matrix for all assets as of a single date. """
        px   = self.prices.loc[:date]
        rets = self.returns.loc[:date]
        market_rets = self.market_returns.reindex(rets.index).fillna(0)
        vix_prices = self.exogenous_universe["^VIX"].loc[:date] \
            if "^VIX" in self.exogenous_universe else pd.Series(dtype=float)
        high_vol = self._compute_high_vol(vix_prices)

        if len(px) < self.lookbacks["1y"]:
            return pd.DataFrame(index=self.prices.columns)

        features = pd.DataFrame(index=self.prices.columns)
        features["mom_1m"] = px.iloc[-1] / px.iloc[-self.lookbacks["1m"]] - 1
        features["mom_12m"] = px.iloc[-self.lookbacks["1m"]] / px.iloc[-self.lookbacks["1y"]] - 1
        features["vol_1m"] = rets.iloc[-self.lookbacks["1m"]:].std()
        features["vol_3m"] = rets.iloc[-self.lookbacks["3m"]:].std()
        features["reversal"] = -(px.iloc[-1] / px.iloc[-(self.reversal_window + 1)] - 1)
        features["mom_x_vol_regime"] = features["mom_12m"] * (1 - high_vol)
        features["reversal_x_vol_regime"] = features["reversal"] * high_vol
        features["max_return"] = rets.iloc[-self.lookbacks["1m"]:].max()
        features["high_52w"] = px.iloc[-1] / px.iloc[-self.lookbacks["1y"]:].max()
        features["beta_1m"] = self._compute_rolling_beta(rets, market_rets, self.lookbacks["1m"])
        beta_1y = self._compute_rolling_beta(rets, market_rets, self.lookbacks["1y"])
        features["beta_1y"] = beta_1y
        predicted = beta_1y.values * market_rets.iloc[-self.lookbacks["1y"]:].values[:, None]
        residuals = rets.iloc[-self.lookbacks["1y"]:].values - predicted
        features["idiosyncratic_vol"] = pd.Series(residuals.std(axis=0), index=rets.columns)
        features = features.replace([np.inf, -np.inf], np.nan).dropna(how="all")
        features = features.rank(axis=0, pct=True)
        if self.features:
            features = features[self.features]
        return features.fillna(0.5)
    
    def build_forward_returns(self,
                              as_of_date: pd.Timestamp,
                              horizon: int = 21) -> pd.Series:
        """ Build forward returns for all assets starting from as_of_date over `horizon` days, 
            using cached values if available.
        """
        if self.forward_returns_cache is not None and horizon == self.precomputed_horizon:
            return self.forward_returns_cache.get(as_of_date, pd.Series(dtype=float))
        return self._build_forward_returns_single(as_of_date, horizon)

    def _build_forward_returns_single(self,
                              as_of_date: pd.Timestamp,
                              horizon: int = 21) -> pd.Series:
        """ Forward returns starting from as_of_date over `horizon` days. Used as the label (y) during training. """
        px = self.prices
        idx = px.index.get_loc(as_of_date)
        if idx + horizon >= len(px):
            return pd.Series(dtype=float)
        fwd = px.iloc[idx + horizon] / px.iloc[idx] - 1
        return fwd

    def _cache_forward_returns(self,
                               horizon: int) -> dict:
        """ Cache forward returns for all assets over the specified horizon. """
        px = self.prices
        fwd_returns_cache = {}
        for i in range(len(px) - horizon):
            fwd = px.iloc[i + horizon] / px.iloc[i] - 1
            if not fwd.empty:
                fwd_returns_cache[px.index[i]] = fwd
        return fwd_returns_cache

    def _cache_features(self):
        """Build a cache of features for all assets over the historical price data."""
        px = self.prices
        names = self.features or ALL_FEATURES
        built_features = {feature: self._build_features(feature).replace([np.inf, -np.inf], np.nan)
                          for feature in names}
        # A name with no features at all on a date hasn't listed yet: it is left out of that date.
        listed = pd.DataFrame(False, index=px.index, columns=px.columns)
        for frame in built_features.values():
            listed |= frame.notna()
        ranked = {feature: frame.rank(axis=1, pct=True) for feature, frame in built_features.items()}

        features_cache = {}
        for date in px.index[self.lookbacks["1y"]:]:
            keep = listed.loc[date]
            if not keep.any():
                continue
            feat = pd.DataFrame({feature: ranked[feature].loc[date] for feature in names})
            features_cache[date] = feat[keep].fillna(0.5)
        return features_cache

    def _build_features(self, feature: str) -> pd.DataFrame:
        """ One feature for every date and asset (dates x tickers). """
        w = self.lookbacks
        px = self.prices
        rets = self.returns
        mret = self.market_returns
        if feature == "mom_1m":
            return self._compute_mom_1m(px, w)
        elif feature == "mom_12m":
            return self._compute_mom_12m(px, w)
        elif feature == "vol_1m":
            return self._compute_vol_1m(rets, w)
        elif feature == "vol_3m":
            return self._compute_vol_3m(rets, w)
        elif feature == "reversal":
            return self._compute_reversal(px)
        elif feature == "max_return":
            return self._compute_max_ret(rets, w)
        elif feature == "beta_1m":
            return self._compute_beta_frame(rets, mret, w["1m"])
        elif feature == "beta_1y":
            return self._compute_beta_frame(rets, mret, w["1y"])
        elif feature == "high_52w":
            return self._compute_high_52w(px, w)
        elif feature == "idiosyncratic_vol":
            return self._compute_idiosyncratic_vol(rets, mret, w)
        elif feature == "mom_x_vol_regime":
            return self._compute_mom_x_vol_regime(px, w)
        elif feature == "reversal_x_vol_regime":
            return self._compute_reversal_x_vol_regime(px, w)
        else:
            raise ValueError(f"Unsupported feature: {feature}")

    def _compute_high_vol_series(self) -> pd.Series:
        """ 1.0 on dates when VIX is above its 1-year median, else 0.0 (all 0.0 without VIX). """
        if "^VIX" not in self.exogenous_universe.columns:
            return pd.Series(0.0, index=self.prices.index)
        vix = self.exogenous_universe["^VIX"].reindex(self.prices.index).ffill()
        return (vix > vix.rolling(self.lookbacks["1y"]).median()).astype(float)

    def _compute_beta_frame(self, rets: pd.DataFrame, mret: pd.Series, window: int) -> pd.DataFrame:
        """ Rolling beta of each stock to the market, for every date. """
        market_variance = mret.rolling(window).var().replace(0, np.nan)
        return rets.rolling(window).cov(mret).div(market_variance, axis=0)

    def _compute_high_vol(self, vix_prices: pd.Series) -> float:
        """Compute whether the current volatility is high based on the 1-year median of VIX prices."""
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
        """ Beta of each stock to the market over the trailing window. """
        stocks = stock_returns.iloc[-window:]
        market = market_returns.iloc[-window:]
        if len(stocks) < window:
            return pd.Series(np.nan, index=stock_returns.columns)

        market_variance = market.var()
        if not market_variance > 0:
            return pd.Series(np.nan, index=stock_returns.columns)

        market_dev = market - market.mean()
        cov_with_market = stocks.sub(stocks.mean()).mul(market_dev, axis=0).sum(skipna=False) / (window - 1)
        return cov_with_market / market_variance

    def _compute_mom_1m(self, px: pd.DataFrame, w: dict) -> pd.DataFrame:
        return px / px.shift(w["1m"]) - 1

    def _compute_mom_12m(self, px: pd.DataFrame, w: dict) -> pd.DataFrame:
        return px.shift(w["1m"]) / px.shift(w["1y"]) - 1

    def _compute_vol_1m(self, rets: pd.DataFrame, w: dict) -> pd.DataFrame:
        return rets.rolling(w["1m"]).std()

    def _compute_reversal_x_vol_regime(self, px: pd.DataFrame, w: dict) -> pd.DataFrame:
        reversal = self._compute_reversal(px)
        high_vol = self._compute_high_vol_series()
        return reversal.mul(high_vol, axis=0)

    def _compute_reversal(self, px: pd.DataFrame) -> pd.DataFrame:
        return -(px / px.shift(self.reversal_window) - 1)

    def _compute_mom_x_vol_regime(self, px: pd.DataFrame, w: dict) -> pd.DataFrame:
        mom_12m = self._compute_mom_12m(px, w)
        high_vol = self._compute_high_vol_series()
        return mom_12m.mul(1 - high_vol, axis=0)

    def _compute_idiosyncratic_vol(self, rets: pd.DataFrame, mret: pd.Series, w: dict) -> pd.DataFrame:
        """Compute the idiosyncratic volatility of each stock over the trailing window."""
        beta_1y = self._compute_beta_frame(rets, mret, w["1y"])
        idio_vol = (rets - beta_1y.multiply(mret, axis=0)).rolling(w["1y"]).std()
        return idio_vol

    def _compute_vol_3m(self, rets: pd.DataFrame, w: dict) -> pd.DataFrame:
        return rets.rolling(w["3m"]).std()

    def _compute_max_ret(self, rets: pd.DataFrame, w: dict) -> pd.DataFrame:
        return rets.rolling(w["1m"]).max()

    def _compute_high_52w(self, px: pd.DataFrame, w: dict) -> pd.DataFrame:
        return px / px.rolling(w["1y"]).max() 