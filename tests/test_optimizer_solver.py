from types import SimpleNamespace

import cvxpy as cp
import numpy as np
import pandas as pd
import pytest

from domain.optimizers.target_weight_optimizer import TargetWeightOptimizer


class FakeProblem:
    def __init__(self, results, violation=0.0):
        self.results = iter(results)
        self.status = None
        self.calls = []
        self.constraints = [SimpleNamespace(violation=lambda: np.array([violation]))]

    def solve(self, **kwargs):
        self.calls.append(kwargs)
        result = next(self.results)
        if isinstance(result, Exception):
            raise result
        self.status = result


def run_solver(problem):
    weights = pd.Series({"B": 0.3, "A": 0.7})
    config = SimpleNamespace(investment_universe=["A", "B"])
    return TargetWeightOptimizer()._run_solver(problem, weights, config)


def test_optimal_solution_stops_solver_chain():
    problem = FakeProblem([cp.OPTIMAL])
    assert run_solver(problem) is None
    assert [call["solver"] for call in problem.calls] == [cp.CLARABEL]
    assert problem.calls[0]["warm_start"] is True
    assert problem.calls[0]["canon_backend"] == cp.SCIPY_CANON_BACKEND


@pytest.mark.parametrize("violation", [0.0, 1e-4])
def test_inaccurate_solution_within_tolerance_is_accepted(violation):
    problem = FakeProblem([cp.OPTIMAL_INACCURATE], violation)
    assert run_solver(problem) is None
    assert len(problem.calls) == 1


@pytest.mark.parametrize("violation", [1.01e-4, float("nan"), float("inf")])
def test_inaccurate_solution_outside_tolerance_tries_next_solver(violation):
    problem = FakeProblem([cp.OPTIMAL_INACCURATE, cp.OPTIMAL], violation)
    assert run_solver(problem) is None
    assert [call["solver"] for call in problem.calls] == [cp.CLARABEL, cp.SCS]
    assert problem.calls[1]["max_iters"] == 5000


def test_solver_failures_return_original_weights_in_universe_order():
    problem = FakeProblem([cp.SolverError("failed"), ValueError("failed"), cp.INFEASIBLE])
    solution = run_solver(problem)
    assert [call["solver"] for call in problem.calls] == [cp.CLARABEL, cp.SCS, cp.OSQP]
    pd.testing.assert_series_equal(solution.target_weights, pd.Series({"A": 0.7, "B": 0.3}))
    assert solution.sell_allocations == {}
    assert solution.realized_tax_cost == 0.0
    assert solution.tracking_error == 0.0
