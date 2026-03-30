from dataclasses import dataclass
from typing import Dict, Any
import pandas as pd

@dataclass(frozen=True)
class MonitoringStats:
    ic_statistics: pd.Series
    half_life: float
    t_test: Dict[str, Any]

    def to_dict(self):
        return {
            "ic_statistics": {
                "index": self.ic_statistics.index.astype(str).tolist(),
                "values": self.ic_statistics.values.tolist()
            },
            "half_life": self.half_life if not pd.isna(self.half_life) else None,
            "t_test": self.t_test
        }