import logging
import time
from typing import List, Optional
from urllib.parse import quote

import pandas as pd
from edgar import Company, set_identity

from infrastructure.market_data_cache import MarketDataCache, _atomic_write, cache_enabled

logger = logging.getLogger(__name__)

CACHE_MAX_AGE_DAYS = 7

COLUMNS = ["ticker", "metric", "concept", "period_start", "period_end", "filing_date",
           "value", "unit", "fiscal_year", "fiscal_period", "form_type"]

class FundamentalDataGateway:
    set_identity("kovalickbenjamin@gmail.com")
    tag_map = {
        "shares" : [
            "dei:EntityCommonStockSharesOutstanding",
            "us-gaap:CommonStockSharesOutstanding"
        ],
        "equity": [
            "us-gaap:StockholdersEquity",
            "us-gaap:StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"
        ],
        "net_income": [
            "us-gaap:NetIncomeLoss"
        ],
        "revenue": [
            "us-gaap:Revenues",
            "us-gaap:SalesRevenueNet",
            "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax"
        ],
        "gross_profit": [
            "us-gaap:GrossProfit"
        ],
        "assets": [
            "us-gaap:Assets"
        ],
        "liabilities": [
            "us-gaap:Liabilities"
        ],
        "ocf": [
            "us-gaap:NetCashProvidedByUsedInOperatingActivities"
        ]
    }

    @staticmethod
    def get_fundamental_market_data(data_source: dict,
                                    tickers: List[str],
                                    start_date: Optional[pd.Timestamp] = None,
                                    end_date: Optional[pd.Timestamp] = None) -> pd.DataFrame:
        """ Fetch fundamental data for exactly the tickers given """
        logger.info("Fetching fundamental data for %s tickers from source %s", len(tickers), data_source)
        return FundamentalDataGateway._determine_source(data_source, list(tickers), start_date, end_date)

    @staticmethod
    def get_fund_data_edgar(tickers: List[str],
                            start_date: Optional[pd.Timestamp] = None,
                            end_date: Optional[pd.Timestamp] = None) -> pd.DataFrame:
        """Long-format fundamentals from SEC EDGAR: one row per ticker, metric, reporting period
        and first filing. start_date / end_date bound the filing date (when the value became
        public), not the fiscal period it describes."""
        logger.info("Fetching fundamental data from EDGAR for %s tickers (%s to %s)", len(tickers), start_date, end_date)
        start = pd.Timestamp(start_date) if start_date is not None else None
        end = pd.Timestamp(end_date) if end_date is not None else None

        frames = []
        for ticker in tickers:
            ticker_df = FundamentalDataGateway._ticker_fundamentals(ticker)
            if ticker_df is None:
                continue
            if start is not None:
                ticker_df = ticker_df[ticker_df["filing_date"] >= start]
            if end is not None:
                ticker_df = ticker_df[ticker_df["filing_date"] <= end]
            if not ticker_df.empty:
                frames.append(ticker_df)

        if not frames:
            logger.warning("No fundamental data returned for any of %s tickers", len(tickers))
            return pd.DataFrame(columns=COLUMNS)
        return pd.concat(frames, ignore_index=True)[COLUMNS]

    @staticmethod
    def get_fund_data_csv(file_path: str) -> pd.DataFrame:
        logger.info("Fetching fundamental data from CSV file: %s", file_path)
        return pd.read_csv(file_path, index_col=0, parse_dates=True)

    @staticmethod
    def _determine_source(data_source: dict,
                          tickers: List[str],
                          start_date: pd.Timestamp,
                          end_date: pd.Timestamp) -> pd.DataFrame:
        "Determine the appropriate data source and fetch the data accordingly."
        for source, content in data_source.items():
            if source == "edgar":
                return FundamentalDataGateway.get_fund_data_edgar(tickers, start_date, end_date)
            elif source == "csv":
                return FundamentalDataGateway.get_fund_data_csv(content)
            else:
                raise ValueError(f"Unknown source type: {data_source}")
        raise ValueError("No fundamental data source configured")

    @staticmethod
    def _ticker_fundamentals(ticker: str) -> Optional[pd.DataFrame]:
        """All metrics for one ticker over its whole filing history, or None when EDGAR has
        nothing. Served from <market cache>/fundamentals/<TICKER>.parquet when that file is
        younger than CACHE_MAX_AGE_DAYS; a ticker that failed or was not found is not cached,
        so it is retried next run."""
        path = None
        if cache_enabled():
            folder = MarketDataCache().root / "fundamentals"
            folder.mkdir(parents=True, exist_ok=True)
            path = folder / f"{quote(ticker, safe='')}.parquet"
            if path.exists() and time.time() - path.stat().st_mtime <= CACHE_MAX_AGE_DAYS * 86400:
                return pd.read_parquet(path)

        facts_df = FundamentalDataGateway._company_facts(ticker)
        if facts_df is None:
            return None
        frames = [FundamentalDataGateway._extract_metric_data(facts_df, tags, name)
                  for name, tags in FundamentalDataGateway.tag_map.items()]
        frames = [f for f in frames if not f.empty]
        if not frames:
            return pd.DataFrame(columns=COLUMNS)
        ticker_df = pd.concat(frames, ignore_index=True).assign(ticker=ticker)[COLUMNS]
        if path is not None:
            _atomic_write(path, lambda tmp: ticker_df.to_parquet(tmp))
        return ticker_df

    @staticmethod
    def _company_facts(ticker: str) -> Optional[pd.DataFrame]:
        """Every XBRL fact the company has filed, with filing dates, or None when EDGAR has
        nothing for the ticker. Company() raises for a ticker it cannot resolve (most delisted
        names), so the failure is caught here: one ticker must not stop the rest."""
        try:
            company = Company(ticker)
            if not company:
                logger.warning("Fundamentals: %s not found on EDGAR; skipped", ticker)
                return None
            facts = company.get_facts()
        except Exception as exc:
            logger.warning("Fundamentals: %s failed (%s: %s); skipped", ticker, type(exc).__name__, exc)
            return None

        if facts is None:
            logger.warning("Fundamentals: %s has no XBRL facts; skipped", ticker)
            return None
        return facts.to_dataframe(pit_mode=True)

    @staticmethod
    def _extract_metric_data(facts_df: pd.DataFrame, tags: List[str], name: str) -> pd.DataFrame:
        """Rows for one metric from a company's point-in-time facts frame."""
        columns = [c for c in COLUMNS if c != "ticker"]
        rows = facts_df[facts_df["concept"].isin(tags) & facts_df["numeric_value"].notna()].copy()
        if rows.empty:
            return pd.DataFrame(columns=columns)

        for col in ("period_start", "period_end", "filing_date"):
            rows[col] = pd.to_datetime(rows[col], errors="coerce")
        rows = rows.dropna(subset=["period_end", "filing_date"])

        rows["metric"] = name
        rows["value"] = rows["numeric_value"]
        rows["_tag_rank"] = rows["concept"].map({tag: i for i, tag in enumerate(tags)})
        rows = (rows.sort_values(["filing_date", "_tag_rank"], kind="stable")
                    .drop_duplicates(subset=["period_start", "period_end"], keep="first")
                    .sort_values(["period_end", "period_start", "filing_date"], kind="stable"))
        return rows[columns].reset_index(drop=True)
