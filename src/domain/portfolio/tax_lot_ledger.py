import pandas as pd
import numpy as np

from domain.portfolio.portfolio import Portfolio
from simulation.market_state import MarketState
from models.rebalance_solution import RebalanceSolution

LOT_COLUMNS = [
    "AcquisitionDate",
    "Ticker",
    "DaysHeld",
    "Term",
    "TaxRate",
    "CurrentPrice",
    "AcquisitionPrice",
    "Shares",
    "CurrentValue",
    "GainPerShare",
    "TotalCostBasis",
    "TotalGain",
    "TaxCost",
]


class TaxLotLedger:
    """Open tax lots for a long-only portfolio, kept in step with the portfolio's weights.

    The ledger tracks the portfolio's NAV (starting at ``base_nav`` and compounding with the
    portfolio's returns), so each ticker's open lots are always worth ``weight * NAV``:

    * the optimizer's per-lot ``sell_allocations`` are applied first, then
    * every ticker is reconciled to its post-trade target weight: shortfalls become a buy lot,
      excess (solver slack, or a strategy that doesn't choose lots) is sold lowest-tax-first.

    Buys of a ticker within the same calendar month are merged into one lot (weighted-average
    cost, acquisition date = latest buy, so the long-term clock is never started early), and lots
    worth less than ``dust_fraction * NAV`` are dropped. Short positions are not modelled.
    """

    def __init__(self,
                 short_term_tax_rate: float = 0.37,
                 long_term_tax_rate: float = 0.20,
                 base_nav: float = 1_000_000_000,
                 sync_tolerance: float = 1e-7,
                 dust_fraction: float = 1e-9):
        self._short_term_tax_rate = short_term_tax_rate
        self._long_term_tax_rate = long_term_tax_rate
        self._base_nav = base_nav
        self._sync_tolerance = sync_tolerance
        self._dust_fraction = dust_fraction
        self._nav = base_nav
        self._nav_cursor = 0
        self._last_rebalance_date = None
        self._next_lot_id = 0
        self._realized_gain = 0.0
        self._realized_tax = 0.0
        self._tax_lots = pd.DataFrame(columns=LOT_COLUMNS).rename_axis("LotId")

    def initialize(self, market_state: MarketState, portfolio: Portfolio, cursor: int) -> None:
        """Seed open lots from the initial portfolio holdings."""
        self._nav, self._nav_cursor = self._base_nav, cursor
        date = portfolio.weights.index[cursor]
        prices = market_state.investment_prices.iloc[cursor]
        self._reconcile(portfolio.weights.iloc[cursor], date, prices)
        self._last_rebalance_date = date

    def mark_to_market(self, market_state: MarketState, portfolio: Portfolio, cursor: int) -> None:
        """Roll NAV forward and reprice lots, so the optimizer sees current values and gains."""
        self._advance_nav(portfolio, cursor)
        self._refresh(market_state.investment_prices.index[cursor], market_state.investment_prices.iloc[cursor])

    def apply_rebalance(self,
                        market_state: MarketState,
                        portfolio: Portfolio,
                        rebalance_solution: RebalanceSolution,
                        cursor: int) -> None:
        """Apply the rebalance's lot sales, then reconcile every ticker to its new target weight."""
        date = portfolio.weights.index[cursor]
        if self._last_rebalance_date is not None and date <= self._last_rebalance_date:
            raise ValueError(f"Rebalance date {date} must be after the last applied rebalance date "
                             f"{self._last_rebalance_date}.")

        prices = market_state.investment_prices.iloc[cursor]
        self._advance_nav(portfolio, cursor)
        self._refresh(date, prices)
        self._sell_lot_fractions(rebalance_solution.sell_allocations)
        self._reconcile(portfolio.weights.iloc[cursor], date, prices)
        self._last_rebalance_date = date

    @property
    def nav(self) -> float:
        """Portfolio NAV in ledger dollars; open lots per ticker are worth weight * nav."""
        return self._nav

    @property
    def realized_gain(self) -> float:
        return self._realized_gain

    @property
    def realized_tax(self) -> float:
        return self._realized_tax

    @property
    def tax_lots(self) -> pd.DataFrame:
        """Returns the tax lot ledger as a DataFrame."""
        return self._tax_lots.copy()

    def _advance_nav(self, portfolio: Portfolio, cursor: int) -> None:
        if cursor > self._nav_cursor:
            growth = (1.0 + portfolio.returns.iloc[self._nav_cursor + 1:cursor + 1]).prod()
            self._nav *= float(growth)
            self._nav_cursor = cursor

    def _refresh(self, date: pd.Timestamp, prices: pd.Series) -> None:
        """Recompute price-dependent columns for every open lot."""
        lots = self._tax_lots
        if lots.empty:
            return
        lots["CurrentPrice"] = lots["Ticker"].map(prices).astype(float)
        lots["DaysHeld"] = (date - lots["AcquisitionDate"]).dt.days
        long_term = lots["DaysHeld"] >= 365
        lots["Term"] = np.where(long_term, "long", "short")
        lots["TaxRate"] = np.where(long_term, self._long_term_tax_rate, self._short_term_tax_rate)
        lots["CurrentValue"] = lots["CurrentPrice"] * lots["Shares"]
        lots["GainPerShare"] = lots["CurrentPrice"] - lots["AcquisitionPrice"]
        lots["TotalCostBasis"] = lots["AcquisitionPrice"] * lots["Shares"]
        lots["TotalGain"] = lots["GainPerShare"] * lots["Shares"]
        lots["TaxCost"] = lots["TotalGain"].clip(lower=0) * lots["TaxRate"]

    def _sell_lot_fractions(self, lot_sell_allocations: dict[int, float]) -> None:
        """Sell the given fraction of each named lot (the optimizer's lot choices)."""
        if not lot_sell_allocations:
            return
        for lot_id, fraction in lot_sell_allocations.items():
            if lot_id not in self._tax_lots.index:
                raise ValueError(f"Unknown tax lot id: {lot_id}")
            if not 0 <= fraction <= 1:
                raise ValueError(f"Sell fraction for lot {lot_id} must be between 0 and 1.")
        ids = [lot_id for lot_id, fraction in lot_sell_allocations.items() if fraction > 0]
        fractions = pd.Series({lot_id: lot_sell_allocations[lot_id] for lot_id in ids}, dtype=float)
        self._realize(fractions)

    def _realize(self, fractions: pd.Series) -> None:
        """Sell `fractions` (indexed by LotId) of each lot, booking realized gain and tax."""
        if fractions.empty:
            return
        lots = self._tax_lots
        sold = lots.loc[fractions.index]
        self._realized_gain += float((sold["TotalGain"] * fractions).sum())
        self._realized_tax += float((sold["TaxCost"] * fractions).sum())
        lots.loc[fractions.index, "Shares"] = sold["Shares"] * (1.0 - fractions)
        for column in ("CurrentValue", "TotalCostBasis", "TotalGain", "TaxCost"):
            lots.loc[fractions.index, column] = sold[column] * (1.0 - fractions)

    def _reconcile(self, target_weights: pd.Series, date: pd.Timestamp, prices: pd.Series) -> None:
        """Buy or sell so each ticker's open lots are worth max(target weight, 0) * NAV."""
        targets = target_weights.drop(labels=[t for t in target_weights.index if str(t).upper() == "CASH"])
        trade_prices = prices.reindex(targets.index)
        tradable = trade_prices.notna() & (trade_prices > 0)
        targets, trade_prices = targets[tradable].clip(lower=0.0), trade_prices[tradable]

        held = (self._tax_lots.groupby("Ticker")["CurrentValue"].sum()
                if not self._tax_lots.empty else pd.Series(dtype=float))
        gap = targets * self._nav - held.reindex(targets.index).fillna(0.0)
        threshold = self._sync_tolerance * self._nav

        for ticker, amount in gap[gap < -threshold].items():
            self._sell_value(ticker, -amount)
        buys = gap[gap > threshold]
        if not buys.empty:
            self._buy(buys / trade_prices[buys.index], trade_prices[buys.index], date)

        self._refresh(date, prices)
        self._drop_dust()

    def _sell_value(self, ticker: str, value: float) -> None:
        """Sell `value` dollars of `ticker`, lowest tax cost per dollar first."""
        lots = self._tax_lots[self._tax_lots["Ticker"] == ticker]
        lots = lots[lots["CurrentValue"] > 0]
        if lots.empty:
            return
        order = (lots["TaxCost"] / lots["CurrentValue"]).sort_values(kind="stable").index
        remaining, fractions = value, {}
        for lot_id in order:
            lot_value = lots.at[lot_id, "CurrentValue"]
            take = min(lot_value, remaining)
            fractions[lot_id] = take / lot_value
            remaining -= take
            if remaining <= 0:
                break
        self._realize(pd.Series(fractions, dtype=float))

    def _buy(self, shares: pd.Series, prices: pd.Series, date: pd.Timestamp) -> None:
        """Add shares, merging into an open lot of the same ticker bought in the same month."""
        lots = self._tax_lots
        same_month = pd.Series(False, index=lots.index)
        if not lots.empty:
            acquired = lots["AcquisitionDate"]
            same_month = (acquired.dt.year == date.year) & (acquired.dt.month == date.month)

        new_rows = {}
        for ticker, qty in shares.items():
            match = lots.index[same_month & (lots["Ticker"] == ticker)] if not lots.empty else []
            if len(match):
                lot_id = match[0]
                old_qty = lots.at[lot_id, "Shares"]
                cost = old_qty * lots.at[lot_id, "AcquisitionPrice"] + qty * prices[ticker]
                lots.at[lot_id, "Shares"] = old_qty + qty
                lots.at[lot_id, "AcquisitionPrice"] = cost / (old_qty + qty)
                lots.at[lot_id, "AcquisitionDate"] = date
            else:
                new_rows[self._next_lot_id] = {"AcquisitionDate": date, "Ticker": ticker,
                                               "AcquisitionPrice": float(prices[ticker]), "Shares": float(qty)}
                self._next_lot_id += 1

        if new_rows:
            new_lots = pd.DataFrame.from_dict(new_rows, orient="index").reindex(columns=LOT_COLUMNS)
            new_lots.index.name = "LotId"
            self._tax_lots = new_lots if lots.empty else pd.concat([lots, new_lots])

    def _drop_dust(self) -> None:
        """Remove lots that are fully sold or too small to matter."""
        if self._tax_lots.empty:
            return
        value = self._tax_lots["CurrentValue"]
        keep = value.isna() | (value > self._dust_fraction * self._nav)
        self._tax_lots = self._tax_lots.loc[keep].copy()
