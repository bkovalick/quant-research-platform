from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from models.config_parsing import check_keys
from models.inverse_vol_config import InverseVolConfig
from models.machine_learning_config import MachineLearningConfig
from models.pairs_trading_config import PairsTradingConfig
from models.vix_basis_config import VixBasisConfig

MEAN_REVERSION_METHODS = ("rank_reversal", "bollinger")


@dataclass(frozen=True)
class SignalsConfig:
    """
    The `signals_config` block of a strategy. Every default lives here, once:
    a key missing from the JSON takes the field default, and an unknown key is
    an error. Signal-specific blocks (pairs, VIX, inverse vol, ML) are their own
    typed configs and are None unless the JSON includes them.
    """
    # Shared preprocessing
    apply_winsorizing: bool = True
    windsor_percentiles: Dict[str, float] = field(default_factory=lambda: {"lower": 0.05, "upper": 0.95})

    # Mean reversion (MeanReversionSignals)
    mean_reversion_method: str = "rank_reversal"
    mean_reversion_window: int = 4
    bollinger_window: int = 20
    bollinger_num_std: float = 2.0
    bollinger_scale: float = 0.01

    # Momentum (MomentumSignals)
    momentum_skip_periods: int = 4

    # Black-Litterman overlay settings (kept as a dict; read by BlackLittermanSignal)
    black_litterman: Optional[Dict[str, Any]] = None

    # Signal-specific configs
    ml_signals_config: Optional[MachineLearningConfig] = None
    pairs_trading: Optional[PairsTradingConfig] = None
    vix_basis: Optional[VixBasisConfig] = None
    inverse_vol: Optional[InverseVolConfig] = None

    def __post_init__(self):
        if self.mean_reversion_method not in MEAN_REVERSION_METHODS:
            raise ValueError(
                f"mean_reversion_method must be one of {MEAN_REVERSION_METHODS}, "
                f"got {self.mean_reversion_method!r}"
            )
        lower = self.windsor_percentiles.get("lower")
        upper = self.windsor_percentiles.get("upper")
        if lower is None or upper is None or not 0 <= lower < upper <= 1:
            raise ValueError(
                f"windsor_percentiles needs 0 <= lower < upper <= 1, got {self.windsor_percentiles}"
            )
        for name in ("mean_reversion_window", "bollinger_window"):
            if getattr(self, name) < 1:
                raise ValueError(f"{name} must be at least 1")

    @classmethod
    def from_dict(cls, d: dict, market_frequency: str = "d") -> "SignalsConfig":
        kwargs = check_keys(cls, d, "signals_config")
        if kwargs.get("ml_signals_config") is not None:
            kwargs["ml_signals_config"] = MachineLearningConfig.from_dict(kwargs["ml_signals_config"], market_frequency)
        for key, sub_config in (("pairs_trading", PairsTradingConfig),
                                ("vix_basis", VixBasisConfig),
                                ("inverse_vol", InverseVolConfig)):
            if kwargs.get(key) is not None:
                kwargs[key] = sub_config.from_dict(kwargs[key])
        return cls(**kwargs)
