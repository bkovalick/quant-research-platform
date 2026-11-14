from typing import List, Optional

import pandas as pd
import numpy as np

from utils.lookback_windows import LOOKBACK_WINDOWS
from simulation.market_state import MarketState

# Built when no feature list is given. Fundamental features are opt-in: they need a data source.
ALL_FEATURES = ["mom_1m", "mom_12m", "vol_1m", "vol_3m", "reversal", "mom_x_vol_regime",
                "reversal_x_vol_regime", "max_return", "high_52w", "beta_1m", "beta_1y", "idiosyncratic_vol"]

# Every supported feature by what it needs: prices only, ^VIX as an exogenous ticker, or a
# fundamental_data_source. The UI builds its feature checklist from this.
FEATURE_GROUPS = {
    "price": ["mom_1m", "mom_12m", "vol_1m", "vol_3m", "reversal", "max_return", "high_52w",
              "beta_1m", "beta_1y", "idiosyncratic_vol"],
    "regime": ["mom_x_vol_regime", "reversal_x_vol_regime"],
    "fundamental": ["equity_to_assets"],
}

class FeatureBuilder:
    """ Cross-sectionally ranked features and forward returns for ML training and inference. """

    def __init__(self,
                 market_state: MarketState,
                 market_frequency: str = "d",
                 features: Optional[List[str]] = None):
        if market_state.market_returns is None:
            raise ValueError("Benchmark returns are required to build market features")

        self.features = features or ALL_FEATURES
        self.prices = market_state.signal_prices
        self.returns = market_state.signal_returns
        self.market_returns = market_state.market_returns.reindex(self.returns.index).fillna(0)
        self.fundamental_data = market_state.fundamental_data_by_metric or {}
        self.exogenous_universe = market_state.exogenous_universe
        self.lookbacks = LOOKBACK_WINDOWS.get(market_frequency, LOOKBACK_WINDOWS["d"])
        self.reversal_window = self.lookbacks.get("1w", 1)
        self.features_cache = None
        self.forward_returns_cache = None
        self.precomputed_horizon = None

    def precompute(self, horizon: int = 21):
        """ Compute features and forward returns for every date once, for fast lookup afterwards. """
        self.precomputed_horizon = horizon
        self.features_cache = self._cache_features()
        self.forward_returns_cache = {date: self._forward_returns(date, horizon)
                                      for date in self.prices.index[:-horizon]}

    def build(self, date: pd.Timestamp) -> pd.DataFrame:
        """ Ranked feature matrix (assets x features) as of one date; empty during warm-up. """
        if self.features_cache is None:
            raise RuntimeError("FeatureBuilder.precompute() must be called before build()")
        return self.features_cache.get(date, pd.DataFrame(index=self.prices.columns))

    def build_forward_returns(self, as_of_date: pd.Timestamp, horizon: int = 21) -> pd.Series:
        """ Return of each asset over the `horizon` periods after as_of_date: the training label.
            Empty when the horizon runs past the end of the data. """
        if self.forward_returns_cache is not None and horizon == self.precomputed_horizon:
            return self.forward_returns_cache.get(as_of_date, pd.Series(dtype=float))
        return self._forward_returns(as_of_date, horizon)

    def _forward_returns(self, as_of_date: pd.Timestamp, horizon: int) -> pd.Series:
        px = self.prices
        idx = px.index.get_loc(as_of_date)
        if idx + horizon >= len(px):
            return pd.Series(dtype=float)
        return px.iloc[idx + horizon] / px.iloc[idx] - 1

    def _cache_features(self) -> dict:
        """ Per date: each feature ranked across assets (0-1), missing values at the neutral 0.5. """
        px = self.prices
        raw = {name: self._build_feature(name).replace([np.inf, -np.inf], np.nan) for name in self.features}
        ranked = {name: frame.rank(axis=1, pct=True) for name, frame in raw.items()}
        # A name with no features at all on a date hasn't listed yet: it is left out of that date.
        listed = pd.DataFrame(False, index=px.index, columns=px.columns)
        for frame in raw.values():
            listed |= frame.notna()

        cache = {}
        for date in px.index[self.lookbacks["1y"]:]:
            keep = listed.loc[date]
            if keep.any():
                feat = pd.DataFrame({name: frame.loc[date] for name, frame in ranked.items()})
                cache[date] = feat[keep].fillna(0.5)
        return cache

    def _build_feature(self, name: str) -> pd.DataFrame:
        """ One raw feature for every date and asset (dates x tickers). """
        px, rets, w = self.prices, self.returns, self.lookbacks
        builders = {
            "mom_1m": lambda: px / px.shift(w["1m"]) - 1,
            "mom_12m": lambda: self._mom_12m(),
            "vol_1m": lambda: rets.rolling(w["1m"]).std(),
            "vol_3m": lambda: rets.rolling(w["3m"]).std(),
            "reversal": lambda: self._reversal(),
            "mom_x_vol_regime": lambda: self._mom_12m().mul(1 - self._high_vol(), axis=0),
            "reversal_x_vol_regime": lambda: self._reversal().mul(self._high_vol(), axis=0),
            "max_return": lambda: rets.rolling(w["1m"]).max(),
            "high_52w": lambda: px / px.rolling(w["1y"]).max(),
            "beta_1m": lambda: self._beta(w["1m"]),
            "beta_1y": lambda: self._beta(w["1y"]),
            "idiosyncratic_vol": lambda: self._idiosyncratic_vol(),
            "equity_to_assets": lambda: self._equity_to_assets(),
        }
        if name not in builders:
            raise ValueError(f"Unsupported feature: {name}")
        return builders[name]()

    def _mom_12m(self) -> pd.DataFrame:
        """ 12-month momentum that skips the most recent month. """
        return self.prices.shift(self.lookbacks["1m"]) / self.prices.shift(self.lookbacks["1y"]) - 1

    def _reversal(self) -> pd.DataFrame:
        """ Negative of the short-term return: recent losers score high. """
        return -(self.prices / self.prices.shift(self.reversal_window) - 1)

    def _high_vol(self) -> pd.Series:
        """ 1.0 on dates when VIX is above its 1-year median, else 0.0 (all 0.0 without VIX). """
        if "^VIX" not in self.exogenous_universe.columns:
            return pd.Series(0.0, index=self.prices.index)
        vix = self.exogenous_universe["^VIX"].reindex(self.prices.index).ffill()
        return (vix > vix.rolling(self.lookbacks["1y"]).median()).astype(float)

    def _beta(self, window: int) -> pd.DataFrame:
        """ Rolling beta of each asset to the market. """
        market_variance = self.market_returns.rolling(window).var().replace(0, np.nan)
        return self.returns.rolling(window).cov(self.market_returns).div(market_variance, axis=0)

    def _idiosyncratic_vol(self) -> pd.DataFrame:
        """ Volatility of the return left over after removing the 1-year market beta. """
        window = self.lookbacks["1y"]
        residuals = self.returns - self._beta(window).multiply(self.market_returns, axis=0)
        return residuals.rolling(window).std()

    def _equity_to_assets(self) -> pd.DataFrame:
        """ Book equity over total assets as last filed. Higher means less leverage. """
        equity = self._fundamental_metric("equity")
        assets = self._fundamental_metric("assets")
        return equity / assets.where(assets > 0)

    def _fundamental_metric(self, metric: str) -> pd.DataFrame:
        """ One fundamental metric on the price grid, blank wherever the asset has no price. """
        if metric not in self.fundamental_data:
            raise ValueError(f"Fundamental metric '{metric}' is not loaded; "
                             "set fundamental_data_source in market_store_config.")
        data = self.fundamental_data[metric].reindex(index=self.prices.index, columns=self.prices.columns)
        return data.where(self.prices.notna())
