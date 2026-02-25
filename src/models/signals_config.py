from dataclasses import dataclass
from typing import Dict

@dataclass(frozen=True)
class SignalsConfig:
    apply_winsorizing: bool
    windsor_percentiles: Dict
    
    @classmethod
    def from_dict(cls, d: dict):
        return cls(
            apply_winsorizing = d.get("apply_windsorizing", True),
            windsor_percentiles = d.get(
                "windsor_percentiles",
                {"lower": 0.05, "upper": 0.95}
            )
        )
        