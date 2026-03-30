from dataclasses import dataclass
from typing import Dict, Any
import pandas as pd

@dataclass(frozen=True)
class MonitoringStats:
    ic_statistics: pd.Series
    ic_summary: Dict[str, Any]
    half_life: float

    def to_dict(self):
        return {
            "ic_statistics": {
                "index": self.ic_statistics.index.astype(str).tolist(),
                "values": self.ic_statistics.values.tolist()
            },
            "ic_summary": self.ic_summary,
            "half_life": self.half_life if not pd.isna(self.half_life) else None
        }