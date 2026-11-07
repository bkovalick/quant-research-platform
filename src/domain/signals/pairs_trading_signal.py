import numpy as np
import pandas as pd
from statsmodels.tsa.stattools import coint
from typing import Dict, List, Tuple

from models.pairs_trading_config import PairsTradingConfig
from simulation.market_state import MarketState

MIN_OBSERVATIONS = 30
Pair = Tuple[str, str]

class PairsTradingSignal:
    """
    Pairs are selected (cointegration test + hedge ratio) only every
    `pairs_reselect_every` calls. Between selections the hedge ratio is frozen
    and only the spread z-score is recomputed. Position state is owned by the
    strategy and passed in as `position_book`.
    """
    def __init__(self,
                 market_state: MarketState,
                 pairs_trading_config: PairsTradingConfig):
        self.market_state = market_state
        self.pairs_trading_config = pairs_trading_config
        self.pairs_lookback_horizon = pairs_trading_config.pairs_lookback_horizon
        self.cointegration_threshold = pairs_trading_config.cointegration_threshold
        self.correlation_filter = pairs_trading_config.correlation_filter
        self.pairs_entry = pairs_trading_config.pairs_entry
        self.pairs_exit = pairs_trading_config.pairs_exit
        self.pairs_stop_loss = pairs_trading_config.pairs_stop_loss
        self.per_pair_gross = pairs_trading_config.per_pair_gross
        self.max_gross = pairs_trading_config.pairs_max_gross
        self.reselect_every = max(1, pairs_trading_config.pairs_reselect_every)
        self._hedge_ratios: Dict[Pair, float] = {}
        self._calls = 0

    def compute_trading_pairs(self,
                              position_book: Dict[Pair, float]) -> pd.DataFrame:
        """
        Return one row per tracked pair with its z-score, hedge ratio, state and
        sizing weight. `position_book` maps open pairs to +1 (long spread) or -1 (short).
        """
        prices = self.market_state.lookback_prices()
        log_prices = np.log(prices)
        if self._calls % self.reselect_every == 0:
            # Select only among names priced over the whole window and tradable today, so a pair
            # can't be formed around a leg the engine will force to zero (an unhedged position).
            complete = prices.columns[prices.notna().all()]
            tradable = getattr(self.market_state, "tradable", None)
            if tradable is not None:
                mask = tradable()
                complete = [t for t in complete if bool(mask.get(t, False))]
            self._reselect_pairs(prices[complete], log_prices[complete], position_book)
        self._calls += 1

        rows = []
        for pair, hedge_ratio in self._hedge_ratios.items():
            log_a, log_b = log_prices[pair[0]], log_prices[pair[1]]
            spread = self._compute_spread(log_a, log_b, hedge_ratio)
            spread_vol = spread.diff().rolling(self.pairs_lookback_horizon).std()
            zscores = self._compute_zscores(spread)
            if pd.isna(zscores.iloc[-1]) or pd.isna(spread_vol.iloc[-1]):
                continue
            return_a = prices[pair[0]].iloc[-1] / prices[pair[0]].iloc[-2] - 1
            return_b = prices[pair[1]].iloc[-1] / prices[pair[1]].iloc[-2] - 1
            rows.append({
                "Date": self.market_state.current_date(),
                "Pair": pair[0] + "_" + pair[1],
                "AssetA": pair[0],
                "AssetB": pair[1],
                "ReturnA": return_a,
                "ReturnB": return_b,
                "RealizedReturn": return_a - hedge_ratio * return_b,
                "HedgeRatio": hedge_ratio,
                "Spread": spread.iloc[-1],
                "SpreadVol": spread_vol.iloc[-1],
                "Zscore": zscores.iloc[-1],
                "State": self._determine_state(pair, zscores.iloc[-1], position_book),
            })

        frame = pd.DataFrame(rows)
        if frame.empty:
            return frame
        frame["FinalWeight"] = self._pair_sizing(frame)
        return frame

    def _pair_sizing(self, frame: pd.DataFrame) -> pd.Series:
        """Per-pair gross, tilted toward lower spread volatility (equal-risk), within 0.5x-2x."""
        inv_vol = 1.0 / frame["SpreadVol"].where(frame["SpreadVol"] > 0)
        relative = inv_vol / inv_vol.mean()
        return self.per_pair_gross * relative.clip(0.5, 2.0).fillna(1.0)

    def _reselect_pairs(self,
                        prices: pd.DataFrame,
                        log_prices: pd.DataFrame,
                        position_book: Dict[Pair, float]) -> None:
        selected = {
            pair: self._hedge_ratio(log_prices[pair[0]], log_prices[pair[1]])
            for pair in self._determine_pairs(prices, self.market_state.sectors_to_tickers)
        }
        # Open positions keep their original hedge ratio until they exit
        for pair in position_book:
            if pair not in selected and pair in self._hedge_ratios:
                selected[pair] = self._hedge_ratios[pair]
        self._hedge_ratios = selected

    def _hedge_ratio(self, log_a: pd.Series, log_b: pd.Series) -> float:
        """Slope of log(A) on log(B)"""
        valid = log_a.notna() & log_b.notna()
        return float(np.polyfit(log_b[valid], log_a[valid], 1)[0])

    def _compute_spread(self,
                        log_a: pd.Series,
                        log_b: pd.Series,
                        beta: float) -> pd.Series:
        return log_a - beta * log_b

    def _compute_zscores(self, spread: pd.Series) -> pd.Series:
        mean = spread.rolling(self.pairs_lookback_horizon).mean()
        std = spread.rolling(self.pairs_lookback_horizon).std()
        return (spread - mean) / std

    def _determine_pairs(self,
                         prices: pd.DataFrame,
                         sectors_to_tickers: Dict[str, List[str]]) -> List[Pair]:
        """Correlated and cointegrated pairs, within the same sector."""
        pairs = []
        for tickers in sectors_to_tickers.values():
            tickers = [t for t in tickers if t in prices.columns]
            if len(tickers) < 2:
                continue
            log_ret = np.log(prices[tickers]).diff().dropna(how="all")
            correlation_matrix = log_ret.corr()
            candidates = [(tickers[i], tickers[j]) for i, j in
                          zip(*np.where(correlation_matrix > self.correlation_filter)) if i < j]
            for pair_a, pair_b in candidates:
                both = prices[[pair_a, pair_b]].dropna()
                if len(both) < MIN_OBSERVATIONS:
                    continue
                pvalue = coint(np.log(both[pair_a]), np.log(both[pair_b]))[1]
                if pvalue < self.cointegration_threshold:
                    pairs.append((pair_a, pair_b))
        return pairs

    def _determine_state(self,
                         pair: Pair,
                         zscore: float,
                         position_book: Dict[Pair, float]) -> str:
        """Entry/exit decision from the z-score and the strategy's own position book."""
        side = position_book.get(pair)
        if side is not None:
            if abs(zscore) < self.pairs_exit or abs(zscore) > self.pairs_stop_loss:
                return "Exit"
            return "HoldLong" if side > 0 else "HoldShort"

        if abs(zscore) > self.pairs_stop_loss:
            return "Flat"
        if zscore < -self.pairs_entry:
            return "EnterLong"
        if zscore > self.pairs_entry:
            return "EnterShort"
        return "Flat"
