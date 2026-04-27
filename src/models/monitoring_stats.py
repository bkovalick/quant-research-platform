from dataclasses import dataclass
from typing import Dict, Any
import pandas as pd
import numpy as np

def _sanitize_value(v):
    if isinstance(v, float) and (np.isnan(v) or np.isinf(v)):
        return None
    if isinstance(v, np.floating) and (np.isnan(v) or np.isinf(v)):
        return None
    return v

def _sanitize_dict(d):
    return {k: _sanitize_value(v) for k, v in d.items()}

def _sanitize_list(values):
    return [_sanitize_value(v) for v in values]

@dataclass(frozen=True)
class MonitoringStats:
    ic_statistics: Dict[str, Any]
    ic_summary: Dict[str, Any]

    def to_dict(self):
        return {
            "ic_statistics": { 
                k: self._serialize(v) 
                for k,v in self.ic_statistics.items()
            },       
            "ic_summary": _sanitize_dict(self.ic_summary)
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