from pydantic import BaseModel
from typing import Dict, List, Any

class SeriesData(BaseModel):
    class Config:
        extra = "allow"

class SummaryData(BaseModel):
    class Config:
        extra = "allow"

class BacktestResultModel(BaseModel):
    summary: Dict[str, Any]
    series: Dict[str, Any]

class MonitoringStatsModel(BaseModel):
    ic_statistics: Dict[str, Any]
    ic_summary: Dict[str, Any]    

class StrategyRunModel(BaseModel):
    run_id: str
    strategy_name: str
    strategy_config: Dict[str, Any] = {}
    metadata: Dict[str, Any] = {}
    monitoring_stats: MonitoringStatsModel = None
    result: BacktestResultModel

class ExperimentModel(BaseModel):
    experiment_id: str
    market_config: Dict[str, Any]
    strategy_runs: List[StrategyRunModel]