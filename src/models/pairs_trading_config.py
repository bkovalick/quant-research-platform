from dataclasses import dataclass

@dataclass
class PairsTradingConfig:
    pairs_lookback_horizon: int
    cointegration_threshold: float
    correlation_filter: float
    pairs_entry: float
    pairs_exit: float
    pairs_stop_loss: float
    per_pair_gross: float
    pairs_reselect_every: int
    pairs_max_gross: float

    @classmethod
    def from_dict(cls, d: dict):
        return cls(
            pairs_lookback_horizon = d.get("pairs_lookback_horizon", 50),
            cointegration_threshold = d.get("cointegration_threshold", 0.05),
            correlation_filter = d.get("correlation_filter", 0.70),
            pairs_entry = d.get("pairs_entry", 2),
            pairs_exit = d.get("pairs_exit", 0.5),
            pairs_stop_loss = d.get("pairs_stop_loss", 3.5),
            per_pair_gross = d.get("per_pair_gross", 0.04),
            pairs_reselect_every = d.get("pairs_reselect_every", 20),
            pairs_max_gross = d.get("pairs_max_gross", 1.0)
        )