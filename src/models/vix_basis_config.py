from dataclasses import dataclass


@dataclass(frozen=True)
class VixBasisConfig:
    """
    Term-structure strategy on the ratio front_index / back_index (default ^VIX / ^VIX3M).
    ratio < 1 is contango (short vol earns the roll), ratio > 1 is backwardation.

    Hysteresis bands:
        Flat  -> Short when ratio < short_entry;  Short -> Flat when ratio > short_exit
        Flat  -> Long  when ratio > long_entry;   Long  -> Flat when ratio < long_exit
    """
    front_index: str = "^VIX"
    back_index: str = "^VIX3M"
    short_vol_ticker: str = "SVXY"
    long_vol_ticker: str = "VIXM"
    short_entry: float = 0.90
    short_exit: float = 0.95
    long_entry: float = 1.05
    long_exit: float = 1.00
    enable_long: bool = True
    use_prior_close: bool = True

    def __post_init__(self):
        if not self.short_entry < self.short_exit:
            raise ValueError("vix_basis: short_entry must be below short_exit")
        if not self.long_exit < self.long_entry:
            raise ValueError("vix_basis: long_exit must be below long_entry")
        if not self.short_exit <= self.long_exit:
            raise ValueError("vix_basis: short band must sit below long band (short_exit <= long_exit)")

    @classmethod
    def from_dict(cls, d: dict):
        defaults = cls()
        return cls(**{k: d.get(k, getattr(defaults, k)) for k in cls.__dataclass_fields__})
