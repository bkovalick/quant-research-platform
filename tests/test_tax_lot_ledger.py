from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from domain.portfolio.portfolio import Portfolio
from domain.portfolio.tax_lot_ledger import TaxLotLedger
from models.rebalance_solution import RebalanceSolution

TICKERS = ["AAA", "BBB", "CCC", "DDD", "EEE"]


def _ledger_weights(ledger: TaxLotLedger) -> pd.Series:
    lots = ledger.tax_lots
    held = lots.groupby("Ticker")["CurrentValue"].sum() if not lots.empty else pd.Series(dtype=float)
    return (held / ledger.nav).reindex(TICKERS).fillna(0.0)


def _simulate(seed: int, n_days: int = 400, rebalance_every: int = 5, optimizer_sells: bool = True):
    """Drift a portfolio through random prices, rebalancing to random targets, and yield the
    ledger and portfolio after every rebalance."""
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2020-01-01", periods=n_days)
    returns = pd.DataFrame(rng.normal(0.0004, 0.02, (n_days, len(TICKERS))), index=dates, columns=TICKERS)
    returns.iloc[0] = 0.0
    prices = 100 * (1 + returns).cumprod()
    market_state = SimpleNamespace(investment_prices=prices)

    weights = np.full(len(TICKERS), 1 / len(TICKERS))
    portfolio = Portfolio()
    portfolio.initialize(dates, np.array(TICKERS), weights)
    ledger = TaxLotLedger()
    ledger.initialize(market_state, portfolio, cursor=0)

    for cursor in range(1, n_days):
        weights = portfolio.drift(weights, returns.iloc[cursor].to_numpy(), cursor)
        if cursor % rebalance_every:
            continue
        ledger.mark_to_market(market_state, portfolio, cursor)
        drifted = pd.Series(weights, index=TICKERS)

        # Ledger must already agree with the drifted portfolio before anything trades.
        assert np.allclose(_ledger_weights(ledger), drifted, atol=1e-9)

        target = rng.dirichlet(np.ones(len(TICKERS)))
        sells = {}
        if optimizer_sells:  # emulate the optimizer picking lots for (part of) each reduction
            lots = ledger.tax_lots
            for ticker in drifted.index[target < drifted.values]:
                ticker_lots = lots[lots["Ticker"] == ticker]
                share = rng.uniform(0.0, 1.0)
                to_sell = (drifted[ticker] - target[TICKERS.index(ticker)]) * share * ledger.nav
                for lot_id, value in ticker_lots["CurrentValue"].items():
                    take = min(value, to_sell)
                    if take <= 0:
                        break
                    sells[lot_id] = take / value
                    to_sell -= take

        portfolio.apply(target, weights, cursor)
        ledger.apply_rebalance(market_state, portfolio, RebalanceSolution(
            target_weights=pd.Series(target, index=TICKERS), sell_allocations=sells,
            realized_tax_cost=0.0, tracking_error=None), cursor)
        weights = target
        yield ledger, portfolio, cursor


@pytest.mark.parametrize("optimizer_sells", [True, False])
def test_ledger_tracks_portfolio_weights_and_nav(optimizer_sells):
    for ledger, portfolio, cursor in _simulate(seed=7, optimizer_sells=optimizer_sells):
        assert np.allclose(_ledger_weights(ledger), portfolio.weights[cursor], atol=1e-9)
        nav = 1_000_000_000 * (1 + portfolio.returns[1:cursor + 1]).prod()
        assert ledger.nav == pytest.approx(nav, rel=1e-12)


def test_same_month_buys_share_one_lot_per_ticker():
    for ledger, _, _ in _simulate(seed=3, rebalance_every=5):
        lots = ledger.tax_lots
        month = lots["AcquisitionDate"].dt.to_period("M")
        assert not lots.assign(month=month).duplicated(["Ticker", "month"]).any()
    # ~19 months of weekly rebalances: at most one lot per ticker per month survives.
    assert len(ledger.tax_lots) <= len(TICKERS) * 20


def test_realized_tax_is_booked_and_lowest_tax_lots_are_sold_first():
    # Jan buy, then a Feb top-up: different months, so they stay separate lots.
    dates = pd.DatetimeIndex(["2020-01-31", "2020-02-03", "2020-02-04"])
    prices = pd.DataFrame({"AAA": [100.0, 150.0, 150.0]}, index=dates)
    market_state = SimpleNamespace(investment_prices=prices)
    portfolio = Portfolio()
    portfolio.initialize(dates, np.array(["AAA"]), np.array([0.5]))
    ledger = TaxLotLedger()
    ledger.initialize(market_state, portfolio, cursor=0)          # lot 0: bought at 100

    weights = portfolio.drift(np.array([0.5]), np.array([0.5]), 1)  # AAA +50%
    portfolio.apply(np.array([1.0]), weights, 1)                     # top up -> lot 1 at 150
    ledger.apply_rebalance(market_state, portfolio, RebalanceSolution(
        pd.Series([1.0], index=["AAA"]), {}, 0.0, None), 1)
    assert ledger.realized_tax == 0.0

    portfolio.apply(np.array([0.65]), np.array([1.0]), 2)            # trim with no lot choice
    ledger.apply_rebalance(market_state, portfolio, RebalanceSolution(
        pd.Series([0.65], index=["AAA"]), {}, 0.0, None), 2)
    lots = ledger.tax_lots
    # The zero-gain lot bought at 150 is sold first, so nothing is realized yet.
    assert ledger.realized_tax == pytest.approx(0.0, abs=1e-6)
    assert sorted(lots["AcquisitionPrice"].round(6)) == [100.0, 150.0]
    assert len(lots) == 2
