from dataclasses import dataclass
from typing import Dict, Any
from models.machine_learning_config import MachineLearningConfig

@dataclass(frozen=True)
class SignalsConfig:
    apply_winsorizing: bool
    windsor_percentiles: Dict
    mean_reversion_window: int
    momentum_skip_periods: int
    black_litterman: Dict[str, Any]
    ml_signals_config: MachineLearningConfig
    
    @classmethod
    def from_dict(cls, d: dict):
        ml_config = d.get("ml_signals_config", None)
        return cls(
            apply_winsorizing = d.get("apply_winsorizing", True),
            windsor_percentiles = d.get(
                "windsor_percentiles",
                {"lower": 0.05, "upper": 0.95}
            ),
            mean_reversion_window = d.get("mean_reversion_window", 4),
            momentum_skip_periods = d.get("momentum_skip_periods", 4),
            black_litterman = d.get("black_litterman", None),
            ml_signals_config = MachineLearningConfig.from_dict(ml_config) if ml_config is not None else None
        )
        