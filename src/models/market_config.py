from dataclasses import dataclass
from typing import Dict, List, Any

@dataclass(frozen=True)
class MarketStateConfig:
    lookback_window: int
    trading_frequency: str
    apply_winsorizing: bool
    windsor_percentiles: Dict

@dataclass(frozen=True)
class MarketStoreConfig:        
    tickers: List[Any]
    start_date: str
    end_date: str