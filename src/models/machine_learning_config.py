from dataclasses import dataclass
from typing import List
from utils.lookback_windows import LOOKBACK_WINDOWS

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
    sample_stride: int

    @classmethod
    def from_dict(cls, d: dict, market_frequency: str = "d"):
        freq_map = LOOKBACK_WINDOWS.get(market_frequency, LOOKBACK_WINDOWS["d"])

        def resolve(value, default_key: str) -> int:
            if isinstance(value, str):
                return freq_map[value]
            if value is None:
                return freq_map[default_key]
            return int(value)

        return cls(
            enabled = d.get("enabled", True),
            features_model = d.get("features_model", "cross_sectional_model"),
            features = d.get("features", []),
            signals_model = d.get("signals_model", "ridge"),
            training_window = resolve(d.get("training_window"), "2y"),
            horizon = resolve(d.get("horizon"), "1m"),
            alpha = d.get("alpha", 1.0),
            rebal_cadence = d.get("rebal_cadence", 5),
            sample_stride = d.get("sample_stride", 5)
        )