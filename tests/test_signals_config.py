import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from models.signals_config import SignalsConfig
from models.inverse_vol_config import InverseVolConfig


def test_empty_block_uses_field_defaults():
    c = SignalsConfig.from_dict({})
    assert c.apply_winsorizing is True
    assert c.windsor_percentiles == {"lower": 0.05, "upper": 0.95}
    assert (c.mean_reversion_method, c.mean_reversion_window, c.momentum_skip_periods) == ("rank_reversal", 4, 4)
    assert (c.bollinger_window, c.bollinger_scale) == (20, 0.01)
    assert c.inverse_vol is None and c.vix_basis is None and c.pairs_trading is None


def test_typo_in_key_is_rejected_with_valid_keys_listed():
    with pytest.raises(ValueError, match=r"mean_reversion_windw.*Valid keys"):
        SignalsConfig.from_dict({"mean_reversion_windw": 10})


def test_invalid_values_fail_at_load_time():
    with pytest.raises(ValueError, match="mean_reversion_method"):
        SignalsConfig.from_dict({"mean_reversion_method": "bolinger"})
    with pytest.raises(ValueError, match="windsor_percentiles"):
        SignalsConfig.from_dict({"windsor_percentiles": {"lower": 0.9, "upper": 0.1}})


def test_sub_configs_are_parsed_and_strict():
    c = SignalsConfig.from_dict({"inverse_vol": {"forecast_type": "GARCH"}})
    assert c.inverse_vol == InverseVolConfig(forecast_type="garch", window=20)
    with pytest.raises(ValueError, match="inverse_vol"):
        SignalsConfig.from_dict({"inverse_vol": {"forecast": "ewma"}})
    with pytest.raises(ValueError, match="forecast_type"):
        SignalsConfig.from_dict({"inverse_vol": {"forecast_type": "parkinson"}})
    with pytest.raises(ValueError, match="vix_basis"):
        SignalsConfig.from_dict({"vix_basis": {"short_entr": 0.9}})
