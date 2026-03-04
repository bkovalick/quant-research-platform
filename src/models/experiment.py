from dataclasses import dataclass, field
from typing import Dict, List, Any
from models.strategy_run import StrategyRun
from datetime import datetime

@dataclass
class Experiment:
    experiment_id: str
    created_at: datetime
    market_config: Dict[str, Any]
    strategy_runs: List["StrategyRun"] = field(default_factory=list) 

    def add_run(self, run: "StrategyRun"):
        self.strategy_runs.append(run)

    @property
    def summary_table(self):
        return [
            {
                "strategy_name": run.strategy_name,
                **run.result.summary
            }
            for run in self.strategy_runs
        ]
    
    def to_dict(self):
        return {
            "experiment_id": self.experiment_id,
            "created_at": self.created_at.isoformat(),
            "market_config": self.market_config,
            "strategy_runs": [ run.to_dict() for run in self.strategy_runs ]
        }
