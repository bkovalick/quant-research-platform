from dataclasses import dataclass
from typing import Dict, List, Any
from models.backtest_result import BacktestResult

@dataclass(frozen=True)
class StrategyRun:
    run_id: str
    strategy_name: str
    strategy_config: Dict[str, Any]
    result: BacktestResult
    metadata: Dict[str, Any]

    def to_dict(self):
        return {
            "run_id": self.run_id,
            "strategy_name": self.strategy_name,
            "strategy_config": self.strategy_config,
            "result": self.result.to_dict(),
            "metadata": self.metadata
        }