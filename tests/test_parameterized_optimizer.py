"""ParameterizedOptimizer must match TargetWeightOptimizer while compiling the problem only once."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from domain.optimizers.parameterized_optimizer import ParameterizedOptimizer
from domain.optimizers.target_weight_optimizer import TargetWeightOptimizer
from models.rebalance_context import RebalanceContext
from models.rebalance_problem import RebalanceProblem

TICKERS = ["A", "B", "C", "D", "BOND", "CASH"]


class Signal:
    def __init__(self, seed):
        rng = np.random.default_rng(seed)
        self._mu = rng.normal(0.05, 0.05, len(TICKERS))
        a = rng.normal(0, 0.1, (len(TICKERS), len(TICKERS)))
        self._cov = a @ a.T + np.eye(len(TICKERS)) * 0.01
        self.beta_vector = rng.normal(1.0, 0.3, len(TICKERS))

    def mean_returns(self):
        return self._mu

    def covariance_matrix(self):
        return self._cov


def _problem():
    return RebalanceProblem({
        "investment_universe": TICKERS, "n_assets": len(TICKERS), "initial_weights": {},
        "risk_aversion": 2.0, "transaction_cost": 0.003, "concentration_strength": 1,
        "turnover_limit": 1.0, "min_position_size": 0.0, "max_position_size": 0.4,
        "max_beta_exposure": 1.2, "max_long": 1.0, "max_short": 0.0,   # long-only, net 1.0
        "asset_class_map": {"Equity": [(0, "A"), (1, "B"), (2, "C"), (3, "D")],
                            "Fixed Income": [(4, "BOND")], "Cash": (5, "CASH")},
        "asset_class_constraints": {"Equity": [0.6, 0.95], "Fixed Income": [0.05, 0.3]},
        "sector_map": None, "sector_constraints": None,
    })


def _context(problem, current, tradable):
    return RebalanceContext(cursor=0, signals={}, initial_weights={}, investment_universe=TICKERS,
                            current_weights=pd.Series(current, index=TICKERS), rebalance_problem=problem,
                            portfolio=None, tax_lot_ledger=None,
                            tradable=pd.Series(tradable, index=TICKERS))


def test_matches_target_weight_optimizer_and_compiles_once():
    problem = _problem()
    param = ParameterizedOptimizer(problem)
    assert param._prob.is_dpp()

    current = np.full(len(TICKERS), 1 / len(TICKERS))
    for seed, tradable in [(0, [True] * 6),
                           (1, [True, False, True, True, True, True]),       # B not tradable
                           (2, [True, True, True, True, False, True])]:      # bond sleeve not listed yet
        signal = Signal(seed)
        context = _context(problem, current, tradable)
        expected = TargetWeightOptimizer().optimize(context, signal).target_weights.to_numpy(dtype=float)
        got = param.optimize(context, signal).target_weights.to_numpy(dtype=float)
        np.testing.assert_allclose(got, expected, atol=1e-4)
        assert np.allclose(got[~np.array(tradable)], 0, atol=1e-7)
        current = got

    # One compiled problem object, reused for every date.
    assert param._prob._cache.param_prog is not None
