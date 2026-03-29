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
    n_estimators: int
    max_depth: int
    learning_rate: float

    @classmethod
    def from_dict(cls, d: dict, market_frequency: str = "d"):
        freq_map = LOOKBACK_WINDOWS.get(market_frequency, LOOKBACK_WINDOWS["d"])
        _default_training = {"d": "2y", "w": "2y", "m": "2y", "q": "2y", "y": "5y"}
        _default_horizon  = {"d": "1m", "w": "1m", "m": "1m", "q": "3m", "y": "1y"}
        _default_cadence = {"d": "1m", "w": "1m", "m": "3m", "q": "3m"}
        _default_stride  = {"d": "1w", "w": "1w", "m": "1m", "q": "1m"}        
        default_training_key = _default_training.get(market_frequency, "2y")
        default_horizon_key  = _default_horizon.get(market_frequency, "1m")
        default_cadence_key  = _default_cadence.get(market_frequency, "1m")
        default_stride_key   = _default_stride.get(market_frequency, "1w")

        def resolve(value, default_key: str) -> int:
            if isinstance(value, str):
                if value not in freq_map:
                    valid = sorted(freq_map.keys())
                    raise ValueError(
                        f"Invalid duration key {value!r} for market_frequency={market_frequency!r}. "
                        f"Valid keys: {valid}"
                    )
                return freq_map[value]
            if value is None:
                return freq_map[default_key]
            return int(value)

        resolved_stride = resolve(d.get("sample_stride"), default_stride_key)
        if resolved_stride < 1:
            raise ValueError("Sample Stride must be positive and greater than 0.")
        
        return cls(
            enabled = d.get("enabled", True),
            features_model = d.get("features_model", "cross_sectional_model"),
            features = d.get("features", []),
            signals_model = d.get("signals_model", "ridge"),
            training_window = resolve(d.get("training_window"), default_training_key),
            horizon = resolve(d.get("horizon"), default_horizon_key),
            alpha = d.get("alpha", 1.0),
            rebal_cadence = resolve(d.get("rebal_cadence"), default_cadence_key),
            sample_stride = resolved_stride,
            n_estimators = d.get("n_estimators", 100),
            max_depth = d.get("max_depth", 3),
            learning_rate = d.get("learning_rate", 0.05)
        )