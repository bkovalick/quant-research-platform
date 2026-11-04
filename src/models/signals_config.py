from dataclasses import dataclass
from typing import Dict, Any, Optional
from models.machine_learning_config import MachineLearningConfig
from models.pairs_trading_config import PairsTradingConfig
from models.vix_basis_config import VixBasisConfig

@dataclass(frozen=True)
class SignalsConfig:
    apply_winsorizing: bool
    windsor_percentiles: Dict
    mean_reversion_window: int
    momentum_skip_periods: int
    black_litterman: Optional[Dict[str, Any]]
    ml_signals_config: Optional[MachineLearningConfig]
    pairs_trading: Optional[PairsTradingConfig]
    mean_reversion_method: str = "rank_reversal"
    bollinger_window: int = 20
    bollinger_num_std: float = 2.0
    bollinger_scale: float = 0.01
    vix_basis: Optional[VixBasisConfig] = None

    @classmethod
    def from_dict(cls, d: dict, market_frequency: str = "d"):
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
            ml_signals_config = MachineLearningConfig.from_dict(ml_config, market_frequency) if ml_config is not None else None,
            pairs_trading = PairsTradingConfig.from_dict(d.get("pairs_trading", {})) if d.get("pairs_trading", None) is not None else None,
            mean_reversion_method = d.get("mean_reversion_method", "rank_reversal"),
            bollinger_window = d.get("bollinger_window", 20),
            bollinger_num_std = d.get("bollinger_num_std", 2.0),
            bollinger_scale = d.get("bollinger_scale", 0.01),
            vix_basis = VixBasisConfig.from_dict(d["vix_basis"]) if d.get("vix_basis") is not None else None
        )