from dataclasses import dataclass

from models.config_parsing import check_keys

FORECAST_TYPES = ("rolling", "ewma", "garch")


@dataclass(frozen=True)
class InverseVolConfig:
    """
    Inverse-volatility allocation: risky weight proportional to 1 / forecast vol.

    forecast_type: "rolling" (rolling std of returns), "ewma" (exponentially
                   weighted std of returns) or "garch" (GARCH(1,1) per asset).
    window:        rolling window / EWMA span, in market periods. Ignored by garch,
                   which fits on the full lookback window.
    """
    forecast_type: str = "ewma"
    window: int = 20
    refit_every: str = "12M"

    def __post_init__(self):
        if self.forecast_type not in FORECAST_TYPES:
            raise ValueError(f"inverse_vol.forecast_type must be one of {FORECAST_TYPES}, got {self.forecast_type!r}")
        if self.window < 2:
            raise ValueError("inverse_vol.window must be at least 2")

    @classmethod
    def from_dict(cls, d: dict) -> "InverseVolConfig":
        kwargs = check_keys(cls, d, "signals_config.inverse_vol")
        if isinstance(kwargs.get("forecast_type"), str):
            kwargs["forecast_type"] = kwargs["forecast_type"].lower()
        return cls(**kwargs)
