from dataclasses import dataclass
from typing import Dict, List, Any
import pandas as pd

@dataclass(frozen=True)
class BacktestResult:
    summary: Dict[str, float]
    series: Dict[str, Any]

    def to_dict(self):
        return {
            "summary": self.summary,
            "series": { 
                k: self._serialize(v) 
                for k,v in self.series.items()
            }
        }
    
    def _serialize(self, obj):
        if isinstance(obj, pd.Series):
            return {
                "index": obj.index.astype(str).tolist(),
                "values": obj.values.tolist()
            }
        if isinstance(obj, pd.DataFrame):
            return {
                "index": obj.index.astype(str).tolist(),
                "columns": obj.columns.tolist(),
                "values": obj.values.tolist()
            }
        return obj