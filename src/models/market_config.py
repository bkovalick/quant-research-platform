from dataclasses import dataclass
from typing import Dict, List, Any, Optional

@dataclass(frozen=True)
class MarketStateConfig:
    lookback_window: str
    market_frequency: str
    apply_winsorizing: bool
    windsor_percentiles: Dict
    universe_tickers: List[str]

@dataclass(frozen=True)
class MarketStoreConfig:
    tickers: List[Any]
    start_date: str
    end_date: str
    data_source: Dict