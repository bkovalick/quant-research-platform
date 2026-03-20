import numpy as np
from models.signals_config import SignalsConfig
from simulation.market_state import MarketState
from domain.signals.risk_return_signals import RiskReturnSignals

class MomentumSignals(RiskReturnSignals):
    def __init__(self, 
                market_state: MarketState, 
                signals_cfg: SignalsConfig):
        super().__init__(market_state, signals_cfg)

    def mean_returns(self) -> np.ndarray:
        p = self.market_state.lookback_prices()
        skip = getattr(self.signals_config, "momentum_skip_periods", 4)
        total_return = (p.iloc[-(skip + 1)] / p.iloc[0] - 1).values
        annualized = total_return * (self.ann_factor / (len(p) - skip))
        return annualized