from dataclasses import fields


def check_keys(cls, d: dict, section: str) -> dict:
    """
    Reject keys the config dataclass doesn't define, so a typo in an experiment
    JSON fails at load time instead of silently running with the default.
    """
    allowed = {f.name for f in fields(cls)}
    unknown = sorted(set(d) - allowed)
    if unknown:
        raise ValueError(
            f"Unknown key(s) in {section}: {unknown}. Valid keys: {sorted(allowed)}"
        )
    return dict(d)
