import numpy as np
from scipy.stats import rankdata

from models.signals_config import SignalsConfig
from simulation.market_state import MarketState
from domain.signals.risk_return_signals import RiskReturnSignals

class MeanReversionSignals(RiskReturnSignals):
    def __init__(self, 
                 market_state: MarketState, 
                 signals_cfg: SignalsConfig):
        super().__init__(market_state, signals_cfg)

    def mean_returns(self) -> np.ndarray:
        mean_reversion_window = getattr(self.signals_cfg, "mean_reversion_window", None)
        if mean_reversion_window is None:
            return super().mean_returns()        
        
        lookback_prices = self.market_state.lookback_prices()
        short_returns = lookback_prices.pct_change(mean_reversion_window).iloc[-1]
        if self.apply_winsorizing:
            lower_bound = short_returns.quantile(self.windsor_percentiles["lower"])
            upper_bound = short_returns.quantile(self.windsor_percentiles["upper"])
            short_returns = short_returns.clip(lower=lower_bound, upper=upper_bound)
            
        ranked = rankdata(-short_returns.values) / len(short_returns) - 0.5
        return ranked