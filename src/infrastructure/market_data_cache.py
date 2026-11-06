"""On-disk cache for daily close prices and per-ticker reference data (sector, market cap).

Layout (default ``<repo>/data/market_cache``, override with the ``QRP_MARKET_CACHE`` env var;
set it to ``off`` to bypass the cache entirely):

    prices/<TICKER>.parquet   one ``close`` column, indexed by date
    prices/<TICKER>.json      {"start": ..., "end": ...}: the date range already fetched
    info/<TICKER>.json        {"sector": ..., "marketCap": ..., "totalAssets": ..., "fetched_at": ...}

How a request is served:

* New ticker: the whole requested range is downloaded.
* Requested range sticks out past what was fetched: only the missing piece is downloaded.
  The later piece starts a few days *before* the cached end, and if the overlap doesn't match
  (a split or dividend re-adjusted history), that ticker's full history is downloaded again.
* Today's bar is never cached (it may be partial), and a ticker that comes back with no data
  at all (rate limit, delisted) is not recorded, so it is retried next time.

Files are written atomically, so parallel workers can share one cache safely.
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, Iterable
from urllib.parse import quote

import pandas as pd

logger = logging.getLogger(__name__)

DEFAULT_ROOT = Path(__file__).resolve().parents[2] / "data" / "market_cache"
OVERLAP_DAYS = 10          # calendar days re-fetched before the cached end to detect re-adjustment
# Yahoo's adjusted closes wobble by ~1e-6 between identical requests; real dividend/split
# re-adjustments move history by >= ~5e-4, so 1e-5 separates the two with room either side.
OVERLAP_RTOL = 1e-5

Fetcher = Callable[[list, str, str], pd.DataFrame]   # (tickers, start, end) -> close prices


def cache_enabled() -> bool:
    return os.environ.get("QRP_MARKET_CACHE", "").strip().lower() not in {"off", "0", "false", "none"}


class MarketDataCache:
    def __init__(self, root: str | os.PathLike | None = None):
        env_root = os.environ.get("QRP_MARKET_CACHE", "").strip()
        self.root = Path(root or (env_root if cache_enabled() and env_root else DEFAULT_ROOT))
        self.price_dir = self.root / "prices"
        self.info_dir = self.root / "info"
        self.price_dir.mkdir(parents=True, exist_ok=True)
        self.info_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ prices

    def get_close(self, tickers: Iterable[str], start: str, end: str, fetch: Fetcher) -> pd.DataFrame:
        """Close prices for ``tickers`` on [start, end), downloading only what the cache lacks."""
        tickers = list(dict.fromkeys(tickers))
        start_ts = pd.Timestamp(start)
        end_ts = min(pd.Timestamp(end), pd.Timestamp(datetime.now().date()))   # never cache today's bar

        cached = {t: self._read_prices(t) for t in tickers}
        plans: dict[tuple[pd.Timestamp, pd.Timestamp], list[str]] = {}
        overlap_checks: dict[str, pd.Timestamp] = {}
        for ticker in tickers:
            coverage = self._read_coverage(ticker)
            for piece_start, piece_end, overlap_from in self._missing_pieces(coverage, start_ts, end_ts):
                plans.setdefault((piece_start, piece_end), []).append(ticker)
                if overlap_from is not None:
                    overlap_checks[ticker] = overlap_from

        if plans:
            n_missing = len({t for group in plans.values() for t in group})
            logger.info("Market cache: %s/%s tickers need downloads (%s batches)", n_missing, len(tickers), len(plans))
        refetch_full: set[str] = set()
        for (piece_start, piece_end), group in plans.items():
            fresh = self._download(fetch, group, piece_start, piece_end)
            for ticker in group:
                series = fresh.get(ticker)
                if series is None or series.dropna().empty:
                    logger.warning("Market cache: no data returned for %s %s..%s; not cached, will retry next run",
                                   ticker, piece_start.date(), piece_end.date())
                    continue
                series = series.dropna()
                if ticker in overlap_checks and not self._overlap_matches(cached[ticker], series):
                    refetch_full.add(ticker)
                    continue
                cached[ticker] = self._merge(cached[ticker], series)
                coverage = self._read_coverage(ticker)
                self._write_prices(ticker, cached[ticker], self._extend(coverage, piece_start, piece_end))

        if refetch_full:
            logger.info("Market cache: history re-adjusted for %s tickers; refetching them in full", len(refetch_full))
            for ticker in refetch_full:
                coverage = self._read_coverage(ticker) or {}
                full_start = min(start_ts, pd.Timestamp(coverage.get("start", start_ts)))
                fresh = self._download(fetch, [ticker], full_start, end_ts).get(ticker)
                if fresh is None or fresh.dropna().empty:
                    continue
                cached[ticker] = fresh.dropna()
                self._write_prices(ticker, cached[ticker], {"start": str(full_start.date()), "end": str(end_ts.date())})

        # Same column order yf.download returns (sorted), so downstream code sees identical frames.
        frame = pd.DataFrame({t: s for t, s in cached.items() if s is not None}).reindex(columns=sorted(tickers))
        frame.index.name, frame.columns.name = "Date", "Ticker"
        return frame.loc[(frame.index >= start_ts) & (frame.index < pd.Timestamp(end))]

    @staticmethod
    def _missing_pieces(coverage: dict | None, start: pd.Timestamp, end: pd.Timestamp):
        """(start, end, overlap_from) ranges to download; overlap_from marks an extension past the cached end."""
        if start >= end:
            return []
        if coverage is None:
            return [(start, end, None)]
        cov_start, cov_end = pd.Timestamp(coverage["start"]), pd.Timestamp(coverage["end"])
        pieces = []
        if start < cov_start:
            pieces.append((start, cov_start, None))
        if end > cov_end:
            overlap_from = max(cov_end - timedelta(days=OVERLAP_DAYS), cov_start)
            pieces.append((overlap_from, end, overlap_from))
        return pieces

    @staticmethod
    def _download(fetch: Fetcher, tickers: list, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
        data = fetch(list(tickers), str(start.date()), str(end.date()))
        if isinstance(data, pd.Series):
            data = data.to_frame(tickers[0])
        data.index = pd.DatetimeIndex(data.index).tz_localize(None).normalize()
        return data

    @staticmethod
    def _overlap_matches(old: pd.Series | None, new: pd.Series) -> bool:
        if old is None:
            return True
        common = old.index.intersection(new.index)
        if common.empty:
            return True
        a, b = old.loc[common].astype(float), new.loc[common].astype(float)
        return bool(((a - b).abs() <= OVERLAP_RTOL * b.abs().clip(lower=1e-12)).all())

    @staticmethod
    def _merge(old: pd.Series | None, new: pd.Series) -> pd.Series:
        if old is None:
            return new.sort_index()
        merged = pd.concat([old[~old.index.isin(new.index)], new])
        return merged.sort_index()

    @staticmethod
    def _extend(coverage: dict | None, start: pd.Timestamp, end: pd.Timestamp) -> dict:
        if coverage is None:
            return {"start": str(start.date()), "end": str(end.date())}
        return {"start": str(min(start, pd.Timestamp(coverage["start"])).date()),
                "end": str(max(end, pd.Timestamp(coverage["end"])).date())}

    def _price_path(self, ticker: str) -> Path:
        return self.price_dir / f"{quote(ticker, safe='')}.parquet"

    def _read_prices(self, ticker: str) -> pd.Series | None:
        path = self._price_path(ticker)
        if not path.exists():
            return None
        return pd.read_parquet(path)["close"]

    def _read_coverage(self, ticker: str) -> dict | None:
        path = self._price_path(ticker).with_suffix(".json")
        if not path.exists() or not self._price_path(ticker).exists():
            return None
        return json.loads(path.read_text())

    def _write_prices(self, ticker: str, series: pd.Series, coverage: dict) -> None:
        path = self._price_path(ticker)
        frame = series.rename("close").to_frame()
        frame.index.name = "date"
        _atomic_write(path, lambda tmp: frame.to_parquet(tmp))
        _atomic_write(path.with_suffix(".json"), lambda tmp: Path(tmp).write_text(json.dumps(coverage)))

    # ------------------------------------------------------------------ reference data

    def get_info(self, tickers: Iterable[str], field: str, fetch_info: Callable[[str], dict],
                 max_age_days: float) -> dict:
        """One ``Ticker.info`` field per ticker, re-fetched when older than ``max_age_days``.

        Each fetch stores sector, marketCap and totalAssets together, so asking for another
        field later rarely needs a second network call."""
        out = {}
        now = datetime.now()
        for ticker in tickers:
            path = self.info_dir / f"{quote(ticker, safe='')}.json"
            record = json.loads(path.read_text()) if path.exists() else None
            fresh = record is not None and field in record and \
                now - datetime.fromisoformat(record["fetched_at"]) <= timedelta(days=max_age_days)
            if not fresh:
                try:
                    info = fetch_info(ticker) or {}
                except Exception as exc:                       # same tolerance as before: log and move on
                    logger.warning("Could not fetch info for %s: %s", ticker, exc)
                    out[ticker] = None
                    continue
                record = {k: info.get(k) for k in ("sector", "marketCap", "totalAssets")}
                record["fetched_at"] = now.isoformat(timespec="seconds")
                _atomic_write(path, lambda tmp: Path(tmp).write_text(json.dumps(record)))
            out[ticker] = record.get(field)
        return out


def _atomic_write(path: Path, write: Callable[[str], None]) -> None:
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    os.close(fd)
    try:
        write(tmp)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
