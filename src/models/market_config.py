from dataclasses import dataclass
from typing import Dict, List, Any, Optional
from config.lookback_windows import LOOKBACK_WINDOWS

@dataclass(frozen=True)
class MarketStateConfig:
    lookback_window_key: str
    market_frequency: str
    lookback_window: int
    cash_allocation: float
    universe_tickers: List[str]

    @classmethod
    def from_dict(cls, d: dict):
        lookback_window_key = d.get("lookback_window_key", "1y")
        market_frequency = d.get("market_frequency", "w")
        lookback_window = LOOKBACK_WINDOWS[market_frequency][lookback_window_key]
        cash_allocation = d.get("cash_allocation", 0.0)
        universe_tickers = list(d.get("universe_tickers", ["AAPL"]))
        if cash_allocation > 0:
            universe_tickers = universe_tickers + ["CASH"] 

        return cls(
            lookback_window_key = lookback_window_key,
            market_frequency = market_frequency,
            lookback_window = lookback_window,
            cash_allocation = cash_allocation,
            universe_tickers = universe_tickers
        )

@dataclass(frozen=True)
class MarketStoreConfig:
    tickers: List[Any]
    start_date: str
    end_date: str
    data_source: Dict

    @classmethod
    def from_dict(cls, d: dict):
        return cls(
            tickers = d.get("tickers", ["AAPL"]),
            start_date = d.get("start_date", "2005-01-01"),
            end_date = d.get("end_date", "2026-02-19"),
            data_source = d.get("data_source", { "yfinance": None })  
        )