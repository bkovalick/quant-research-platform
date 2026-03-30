from dataclasses import dataclass
from typing import Dict, Any
import pandas as pd
import numpy as np

def _sanitize_list(values):
    return [
        None if (isinstance(v, float) and (np.isnan(v) or np.isinf(v)))
        else v
        for v in values
    ]    

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
            values = obj.values.tolist()
            return {
                "index": obj.index.astype(str).tolist(),
                "values": _sanitize_list(values)
            }
        if isinstance(obj, pd.DataFrame):
            values = obj.values.tolist()
            sanitized = [ _sanitize_list(row) for row in values ]            
            return {
                "index": obj.index.astype(str).tolist(),
                "columns": obj.columns.tolist(),
                "values": sanitized
            }
        return obj