from dataclasses import dataclass
from typing import Dict, List, Any
from models.strategy_run import StrategyRun

@dataclass
class Experiment:
    experiment_id: str
    base_config: Dict[str, Any]
    runs: List[StrategyRun]
    created_at: str    
