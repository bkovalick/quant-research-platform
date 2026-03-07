from dataclasses import dataclass
from typing import Dict

@dataclass(frozen=True)
class SignalsConfig:
    apply_winsorizing: bool
    windsor_percentiles: Dict
    mean_reversion_window: int
    momentum_skip_periods: int
    
    @classmethod
    def from_dict(cls, d: dict):
        return cls(
            apply_winsorizing = d.get("apply_windsorizing", True),
            windsor_percentiles = d.get(
                "windsor_percentiles",
                {"lower": 0.05, "upper": 0.95}
            ),
            mean_reversion_window = d.get("mean_reversion_window", 4),
            momentum_skip_periods = d.get("momentum_skip_periods", 4)
        )
        