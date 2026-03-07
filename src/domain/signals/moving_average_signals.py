import pandas as pd
from models.signals_config import SignalsConfig
from simulation.market_state import MarketState

class MovingAverageSignals:
    def __init__(self, 
                 market_state: MarketState, 
                 signals_cfg: SignalsConfig):
        self.market_state = market_state
        self.ann_factor = market_state.annual_trading_days
        self.signals_cfg = signals_cfg
        self.apply_winsorizing = signals_cfg.apply_winsorizing
        self.windsor_percentiles = signals_cfg.windsor_percentiles

    def simple_moving_average(self, window: int) -> float:
        p = self.market_state.lookback_prices()
        return p.rolling(window).mean()

    def exponential_weighted_moving_average(self, span: int = 20) -> pd.DataFrame:
        p = self.market_state.lookback_prices()
        return p.ewm(span=span, adjust=False).mean()

    def bollinger_weighted_moving_average(self, window: int = 20, num_std: float = 2.0) -> dict:
        p = self.market_state.lookback_prices()
        sma = p.rolling(window).mean()
        rolling_std = p.rolling(window).std()
        upper_band = sma + num_std * rolling_std
        lower_band = sma - num_std * rolling_std
        return { 'middle': sma, 'upper': upper_band, 'lower': lower_band }