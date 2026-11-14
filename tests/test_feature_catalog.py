import numpy as np
import pandas as pd
import pytest

from domain.machine_learning.feature_builder import ALL_FEATURES, FEATURE_GROUPS, FeatureBuilder


class _State:
    def __init__(self):
        rng = np.random.default_rng(0)
        idx = pd.bdate_range("2020-01-01", periods=560)
        cols = ["A", "B", "C", "D"]
        self.signal_prices = pd.DataFrame(100 * np.exp(rng.normal(0, 0.01, (560, 4)).cumsum(0)), index=idx, columns=cols)
        self.signal_returns = self.signal_prices.pct_change(fill_method=None)
        self.market_returns = self.signal_returns.mean(axis=1)
        self.exogenous_universe = pd.DataFrame({"^VIX": 20 + rng.normal(0, 2, 560)}, index=idx)
        self.fundamental_data_by_metric = {
            m: pd.DataFrame(rng.uniform(1, 9, (560, 4)), index=idx, columns=cols) for m in ("equity", "assets")
        }


def test_groups_list_each_feature_once_and_cover_the_defaults():
    grouped = [f for features in FEATURE_GROUPS.values() for f in features]
    assert len(grouped) == len(set(grouped))
    assert set(ALL_FEATURES) == set(FEATURE_GROUPS["price"]) | set(FEATURE_GROUPS["regime"])
    assert not set(ALL_FEATURES) & set(FEATURE_GROUPS["fundamental"])


@pytest.mark.parametrize("feature", [f for features in FEATURE_GROUPS.values() for f in features])
def test_every_listed_feature_builds(feature):
    builder = FeatureBuilder(_State(), "d", [feature])
    builder.precompute(21)
    frame = builder.build(builder.prices.index[-1])
    assert list(frame.columns) == [feature]
    assert frame[feature].between(0, 1).all()


def test_ml_features_endpoint_serves_the_catalog():
    from application.controller import ml_features
    assert ml_features() == {"groups": FEATURE_GROUPS, "default": ALL_FEATURES}
