from dataclasses import dataclass
from typing import List, Dict, Any

@dataclass(frozen=True)
class MachineLearningConfig:
    enabled: bool
    features_model: str
    features: List[str]
    signals_model: str
    training_window: int
    horizon: int
    alpha: float
    rebal_cadence: int

    @classmethod
    def from_dict(cls, d: dict):
        return cls(
            enabled = d.get("enabled", True),
            features_model = d.get("features_model", "cross_sectional_model"),
            features = d.get("features", []),
            signals_model = d.get("signals_model", "ridge"),
            training_window = d.get("training_window", 504),
            horizon = d.get("horizon", 21),
            alpha = d.get("alpha", 1.0),
            rebal_cadence = d.get("rebal_cadence", 5)
        )