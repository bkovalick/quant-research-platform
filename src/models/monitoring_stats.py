from dataclasses import dataclass
from typing import Dict, Any
import pandas as pd

@dataclass(frozen=True)
class MonitoringStats:
    ic_statistics: pd.Series
    ic_summary: Dict[str, Any]

    def to_dict(self):
        return {
            "ic_statistics": {
                "index": self.ic_statistics.index.astype(str).tolist(),
                "values": self.ic_statistics.values.tolist()
            },
            "ic_summary": self.ic_summary
        }