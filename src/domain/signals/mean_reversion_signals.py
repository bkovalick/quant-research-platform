import numpy as np
from scipy.stats import rankdata

from models.signals_config import SignalsConfig
from simulation.market_state import MarketState
from domain.signals.risk_return_signals import RiskReturnSignals
from domain.signals.moving_average_signals import MovingAverageSignals

class MeanReversionSignals(RiskReturnSignals):
    """Mean reversion signals based on short-term returns."""
    def __init__(self, 
                 market_state: MarketState, 
                 signals_cfg: SignalsConfig):
        super().__init__(market_state, signals_cfg)

    def mean_returns(self) -> np.ndarray:
        method = self.signals_config.mean_reversion_method
        if method == "bollinger":
            return self._bollinger_signal()
        if method == "rank_reversal":
            return self._rank_reversal_signal()
        raise ValueError(f"Unknown mean_reversion_method: {method}")

    def _rank_reversal_signal(self) -> np.ndarray:
        mean_reversion_window = self.signals_config.mean_reversion_window
        if mean_reversion_window is None:
            return super().mean_returns()        
        
        lookback_prices = self.market_state.lookback_prices()
        short_returns = lookback_prices.pct_change(mean_reversion_window, fill_method=None).iloc[-1]
        if self.apply_winsorizing:
            lower_bound = short_returns.quantile(self.windsor_percentiles["lower"])
            upper_bound = short_returns.quantile(self.windsor_percentiles["upper"])
            short_returns = short_returns.clip(lower=lower_bound, upper=upper_bound)

        values = short_returns.values.astype(float)
        finite = np.isfinite(values)
        ranked = np.zeros(len(values))
        if finite.any():
            ranked[finite] = rankdata(-values[finite]) / finite.sum() - 0.5
        return ranked        

    def _bollinger_signal(self) -> np.ndarray:
        """Expected return view: negative z-score, so stretched-up assets are expected to fall."""
        moving_average_signal = MovingAverageSignals(self.market_state, self.signals_config)
        window = self.signals_config.bollinger_window
        num_std = self.signals_config.bollinger_num_std
        z_score = moving_average_signal.bollinger_weighted_moving_average(window, num_std)["z_score"].iloc[-1]
        scale = self.signals_config.bollinger_scale
        values = z_score.values.astype(float)
        return np.where(np.isfinite(values), -values, 0.0) * scale
    