from dataclasses import dataclass, field
from typing import Dict, Any
from models.backtest_result import BacktestResult
from models.monitoring_stats import MonitoringStats

@dataclass(frozen=True)
class StrategyRun:
    run_id: str
    strategy_name: str
    strategy_config: Dict[str, Any]
    result: BacktestResult
    monitoring_stats: MonitoringStats
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self):
        return {
            "run_id": self.run_id,
            "strategy_name": self.strategy_name,
            "strategy_config": self.strategy_config,
            "result": self.result.to_dict(),
            "monitoring_stats": self.monitoring_stats.to_dict(),
            "metadata": self.metadata
        }