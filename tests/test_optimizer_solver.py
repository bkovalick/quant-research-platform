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


def test_optimal_solution_is_accepted():
    problem = FakeProblem([cp.OPTIMAL])
    assert run_solver(problem) is None
    assert len(problem.calls) == 1
    assert problem.calls[0]["solver"] == cp.OSQP
    # Each solve is compiled from scratch, so OSQP must not reuse the previous solve's matrices.
    assert problem.calls[0]["ignore_dpp"] is True
    assert problem.calls[0]["warm_start"] is False


@pytest.mark.parametrize("violation", [0.0, 1e-2])
def test_optimal_solution_within_tolerance_is_accepted(violation):
    assert run_solver(FakeProblem([cp.OPTIMAL], violation)) is None


@pytest.mark.parametrize("violation", [1.01e-2, float("nan"), float("inf")])
def test_optimal_solution_breaking_constraints_keeps_current_weights(violation):
    assert_kept_current_weights(run_solver(FakeProblem([cp.OPTIMAL], violation)))


@pytest.mark.parametrize("violation", [0.0, 1e-4])
def test_inaccurate_solution_within_tolerance_is_accepted(violation):
    problem = FakeProblem([cp.OPTIMAL_INACCURATE], violation)
    assert run_solver(problem) is None
    assert len(problem.calls) == 1


@pytest.mark.parametrize("violation", [1.01e-4, float("nan"), float("inf")])
def test_inaccurate_solution_outside_tolerance_keeps_current_weights(violation):
    assert_kept_current_weights(run_solver(FakeProblem([cp.OPTIMAL_INACCURATE], violation)))


@pytest.mark.parametrize("result", [cp.SolverError("failed"), ValueError("failed"), cp.INFEASIBLE])
def test_solver_failure_keeps_current_weights(result):
    assert_kept_current_weights(run_solver(FakeProblem([result])))


def assert_kept_current_weights(solution):
    """The fallback: current weights, in universe order, with nothing sold."""
    pd.testing.assert_series_equal(solution.target_weights, pd.Series({"A": 0.7, "B": 0.3}))
    assert solution.sell_allocations == {}
    assert solution.realized_tax_cost == 0.0
    assert solution.tracking_error == 0.0
