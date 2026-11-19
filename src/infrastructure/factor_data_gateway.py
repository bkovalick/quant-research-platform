import logging
import time

import pandas as pd
from pandas_datareader import data as web

from infrastructure.market_data_cache import MarketDataCache, _atomic_write, cache_enabled

logger = logging.getLogger(__name__)

CACHE_MAX_AGE_DAYS = 7
HISTORY_START = "1963-07-01"   # first date of the daily Fama-French files
DOWNLOAD_ATTEMPTS = 3


class FactorDataGateway:
    """Daily factor returns from Ken French's data library, cached on disk."""

    @staticmethod
    def get_fama_french_daily(dataset: str) -> pd.DataFrame:
        """Whole history of one daily dataset (e.g. 'F-F_Research_Data_5_Factors_2x3_daily'), in
        percent, indexed by date. Served from <market cache>/factors/<dataset>.parquet when that
        file is younger than CACHE_MAX_AGE_DAYS. If the download fails and an older file exists,
        that file is used: the library is updated monthly, so a stale copy only misses recent days."""
        path = None
        if cache_enabled():
            folder = MarketDataCache().root / "factors"
            folder.mkdir(parents=True, exist_ok=True)
            path = folder / f"{dataset}.parquet"
            if path.exists() and time.time() - path.stat().st_mtime <= CACHE_MAX_AGE_DAYS * 86400:
                return pd.read_parquet(path)

        try:
            factors = FactorDataGateway._download(dataset)
        except Exception as exc:
            if path is not None and path.exists():
                logger.warning("Factor download failed for %s (%s: %s); using the cached copy from %s",
                               dataset, type(exc).__name__, exc,
                               pd.Timestamp(path.stat().st_mtime, unit="s").date())
                return pd.read_parquet(path)
            raise

        if path is not None:
            _atomic_write(path, lambda tmp: factors.to_parquet(tmp))
        return factors

    @staticmethod
    def _download(dataset: str) -> pd.DataFrame:
        """The server drops connections now and then, so a failed read is retried."""
        for attempt in range(1, DOWNLOAD_ATTEMPTS + 1):
            try:
                factors = web.DataReader(dataset, "famafrench", start=HISTORY_START)[0]
                break
            except Exception as exc:
                if attempt == DOWNLOAD_ATTEMPTS:
                    raise
                logger.warning("Factor download attempt %s/%s failed for %s (%s); retrying",
                               attempt, DOWNLOAD_ATTEMPTS, dataset, type(exc).__name__)
                time.sleep(2 * attempt)

        if isinstance(factors.index, pd.PeriodIndex):
            factors.index = factors.index.to_timestamp()
        factors.index = pd.to_datetime(factors.index)
        factors.columns = [str(c).strip() for c in factors.columns]
        return factors
