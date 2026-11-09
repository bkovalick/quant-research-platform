import sys
from pathlib import Path

import pandas as pd
import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from infrastructure.market_data_store import MarketDataStore


@pytest.fixture
def store():
    return MarketDataStore.__new__(MarketDataStore)


def test_historical_tickers_from_csv_are_distinct(tmp_path, store):
    path = tmp_path / "historical.csv"
    path.write_text(
        'date,tickers\n2020-01-01,"AAPL, MSFT,AAPL"\n'
        '2020-01-02,"MSFT,NVDA"\n',
        encoding="utf-8",
    )
    universe = store._get_historical_sp500_universe(str(path))

    assert store._get_historical_sp500_tickers(universe) == ["AAPL", "MSFT", "NVDA"]


def test_historical_tickers_accept_lists_and_empty_dataframe(store):
    universe = pd.DataFrame({"tickers": [["AAPL", "MSFT"], ["MSFT", "NVDA"]]})
    assert store._get_historical_sp500_tickers(universe) == ["AAPL", "MSFT", "NVDA"]
    assert store._get_historical_sp500_tickers(universe.iloc[:0]) == []


@pytest.mark.parametrize("row", [None, float("nan"), ["AAPL", None], "AAPL,,MSFT"])
def test_historical_tickers_reject_invalid_entries(store, row):
    with pytest.raises(ValueError, match="Invalid ticker"):
        store._get_historical_sp500_tickers(pd.DataFrame({"tickers": [row]}))
