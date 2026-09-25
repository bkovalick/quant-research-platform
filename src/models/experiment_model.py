from pydantic import BaseModel
from typing import Dict, List, Any, Optional

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
    ic_statistics: Dict[str, Any] | None = None
    ic_summary: Dict[str, Any] | None = None
    regression_summary: Dict[str, Any] | None = None

class StrategyRunModel(BaseModel):
    run_id: str
    strategy_name: str
    strategy_config: Dict[str, Any] | None = None
    metadata: Dict[str, Any] | None = None
    monitoring_stats: Optional[MonitoringStatsModel] = None
    result: BacktestResultModel

class ExperimentModel(BaseModel):
    experiment_id: str
    market_config: Dict[str, Any]
    strategy_runs: List[StrategyRunModel]