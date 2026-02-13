from dataclasses import dataclass
from typing import Dict, List, Any
from models.backtest_result import BacktestResult

@dataclass(frozen=True)
class StrategyRun:
    run_id: str
    strategy_config: Dict[str, Any]
    result: BacktestResult