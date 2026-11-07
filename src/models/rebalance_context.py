import pandas as pd
from dataclasses import dataclass

from domain.portfolio.portfolio import Portfolio
from domain.portfolio.tax_lot_ledger import TaxLotLedger
from models.rebalance_problem import RebalanceProblem

@dataclass(frozen=True)
class RebalanceContext:
    cursor: int
    signals: dict
    initial_weights: dict
    current_weights: pd.Series
    investment_universe: list
    rebalance_problem: RebalanceProblem
    portfolio: Portfolio
    tax_lot_ledger: TaxLotLedger = None
    tradable: pd.Series = None


def tradable_mask(rebalance_context) -> pd.Series:
    """Tradable flags aligned to the context's investment_universe; all True when the context
    carries none (works for any context-like object, e.g. test stubs)."""
    universe = list(rebalance_context.investment_universe)
    tradable = getattr(rebalance_context, "tradable", None)
    if tradable is None:
        return pd.Series(True, index=universe)
    return tradable.reindex(universe).fillna(False).astype(bool)