from datetime import datetime

import numpy as np
import pandas as pd
import pytest

from infrastructure.market_data_cache import MarketDataCache

DAYS = pd.bdate_range("2019-01-01", "2021-12-31")


class FakeSource:
    """Deterministic price history per ticker; records every download request."""

    def __init__(self):
        self.calls = []
        self.scale = {}          # ticker -> multiplier, to simulate a split/dividend re-adjustment
        self.dead = set()        # tickers that return no data (rate limited / delisted)

    def history(self, ticker):
        seed = sum(map(ord, ticker))
        prices = 100 * np.cumprod(1 + np.random.default_rng(seed).normal(0, 0.01, len(DAYS)))
        return pd.Series(prices * self.scale.get(ticker, 1.0), index=DAYS)

    def __call__(self, tickers, start, end):
        self.calls.append((tuple(tickers), start, end))
        out = {}
        for t in tickers:
            h = self.history(t)
            out[t] = np.nan * h if t in self.dead else h
        frame = pd.DataFrame(out)
        return frame.loc[(frame.index >= start) & (frame.index < end)]

    def downloaded(self):
        return {t for tickers, _, _ in self.calls for t in tickers}


@pytest.fixture
def cache(tmp_path):
    return MarketDataCache(tmp_path)


def test_second_request_is_served_from_disk(cache):
    source = FakeSource()
    first = cache.get_close(["AAA", "BBB"], "2019-01-01", "2021-01-01", source)
    source.calls.clear()
    second = cache.get_close(["AAA", "BBB"], "2019-01-01", "2021-01-01", source)
    assert source.calls == []
    pd.testing.assert_frame_equal(first, second, check_freq=False)
    expected = pd.DataFrame({t: source.history(t) for t in ["AAA", "BBB"]})
    expected = expected.loc[(expected.index >= "2019-01-01") & (expected.index < "2021-01-01")]
    pd.testing.assert_frame_equal(second, expected, check_freq=False, check_names=False)


def test_new_ticker_downloads_only_that_ticker(cache):
    source = FakeSource()
    cache.get_close(["AAA", "BBB"], "2019-01-01", "2021-01-01", source)
    source.calls.clear()
    frame = cache.get_close(["AAA", "BBB", "CCC"], "2019-01-01", "2021-01-01", source)
    assert source.downloaded() == {"CCC"}
    assert list(frame.columns) == ["AAA", "BBB", "CCC"]
    assert frame["CCC"].notna().all()


def test_longer_range_downloads_only_the_missing_pieces(cache):
    source = FakeSource()
    cache.get_close(["AAA"], "2020-01-01", "2020-07-01", source)
    source.calls.clear()
    frame = cache.get_close(["AAA"], "2019-06-01", "2021-01-01", source)
    ranges = sorted((start, end) for _, start, end in source.calls)
    assert ranges[0] == ("2019-06-01", "2020-01-01")                 # earlier piece
    assert ranges[1][1] == "2021-01-01" and ranges[1][0] < "2020-07-01"   # later piece, with overlap
    expected = source.history("AAA")
    pd.testing.assert_series_equal(frame["AAA"], expected[(expected.index >= "2019-06-01") &
                                                          (expected.index < "2021-01-01")],
                                   check_freq=False, check_names=False)


def test_readjusted_history_is_refetched_in_full(cache):
    source = FakeSource()
    cache.get_close(["AAA"], "2019-01-01", "2020-01-01", source)
    source.scale["AAA"] = 0.5          # e.g. a 2:1 split re-adjusts the whole history
    source.calls.clear()
    frame = cache.get_close(["AAA"], "2019-01-01", "2021-01-01", source)
    assert ("AAA",) in [c[0] for c in source.calls]
    assert any(start == "2019-01-01" for _, start, _ in source.calls)   # full refetch happened
    expected = source.history("AAA")
    pd.testing.assert_series_equal(frame["AAA"], expected[expected.index < "2021-01-01"],
                                   check_freq=False, check_names=False)


def test_empty_downloads_are_not_cached(cache):
    source = FakeSource()
    source.dead.add("ZZZ")
    cache.get_close(["AAA", "ZZZ"], "2019-01-01", "2020-01-01", source)
    source.dead.clear()
    source.calls.clear()
    frame = cache.get_close(["AAA", "ZZZ"], "2019-01-01", "2020-01-01", source)
    assert source.downloaded() == {"ZZZ"}          # retried, AAA untouched
    assert frame["ZZZ"].notna().all()


def test_today_is_never_cached(cache, monkeypatch):
    source = FakeSource()
    cache.get_close(["AAA"], "2019-01-01", "2030-01-01", source)
    _, _, end = source.calls[0]
    assert end == str(datetime.now().date())


def test_info_cache_respects_max_age(cache):
    calls = []
    def fetch_info(ticker):
        calls.append(ticker)
        return {"sector": "Tech", "marketCap": 10, "totalAssets": None}

    assert cache.get_info(["AAA"], "sector", fetch_info, max_age_days=30) == {"AAA": "Tech"}
    assert cache.get_info(["AAA"], "marketCap", fetch_info, max_age_days=30) == {"AAA": 10}
    assert calls == ["AAA"]                                   # second field came from the same record
    cache.get_info(["AAA"], "marketCap", fetch_info, max_age_days=-1)
    assert calls == ["AAA", "AAA"]                            # stale -> refetched
