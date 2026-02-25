from dataclasses import dataclass
from typing import Dict, List, Any, Optional
from config.lookback_windows import LOOKBACK_WINDOWS

@dataclass(frozen=True)
class MarketStateConfig:
    lookback_window: str
    market_frequency: str
    annual_trading_days: int
    universe_tickers: List[str]

    @classmethod
    def from_dict(cls, d: dict):
        lookback_window = d.get("lookback_window", "1y"),
        market_frequency = d.get("market_frequency", "w"),
        annual_trading_days = LOOKBACK_WINDOWS[market_frequency][lookback_window],
        universe_tickers = list(d.get("universe_tickers", ["AAPL"])) + ["CASH"]        
        return cls(
            lookback_window = lookback_window,
            market_frequency = market_frequency,
            annual_trading_days = annual_trading_days,
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