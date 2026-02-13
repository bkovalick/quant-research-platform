from dataclasses import dataclass
from typing import Dict, List, Any

@dataclass(frozen=True)
class BacktestResult:
    summary: Dict[str, float]
    series: Dict[str, Any]
    trades: List[Dict[str, Any]]
    metadata: Dict[str, Any]