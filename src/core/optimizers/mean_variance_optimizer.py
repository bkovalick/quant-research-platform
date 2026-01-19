import sys
from mosek.fusion import *
import numpy as np
from scipy.optimize import minimize

from .ioptimizer import IOptimizer
from portfolio.rebalance_problem import RebalanceProblem
from models.rebalance_solution import RebalanceSolution

class MeanVarianceOptimizer(IOptimizer):
    def __init__(self):
        super().__init__()

    def optimize(self, rebalance_problem: RebalanceProblem):
        mean_vector = rebalance_problem.mean_vector
        cov_matrix = rebalance_problem.covariance_matrix
        n_assets = len(mean_vector)
        initial_weights = getattr(rebalance_problem, 'initial_weights', np.ones(n_assets) / n_assets)
        risk_tolerance = getattr(rebalance_problem, 'risk_tolerance', 1.0)

        # Objective: Minimize risk_tolerance * variance - expected return
        # def objective(weights):
        #     return risk_tolerance * weights.T @ cov_matrix @ weights - mean_vector.T @ weights
        
        # # Objective: Maximize expected return
        # def objective(weights):
        #     return mean_vector.T @ weights   
        objective = self._set_objective(rebalance_problem)
        
        # Constraints: weights sum to 1, weights >= 0
        constraints = [{'type': 'eq', 'fun': lambda x: np.sum(x) - 1}]
        constraints += [{'type': 'ineq', 'fun': lambda x: risk_tolerance - (x @ cov_matrix @ x)}]
        bounds = [(0, 1) for _ in range(n_assets)]

        result = minimize(
            objective,
            x0=initial_weights,
            method='SLSQP',
            bounds=bounds,
            constraints=constraints
        )

        if not result.success:
            raise RuntimeError(f"Optimization failed: {result.message}")

        optimal_weights = result.x
        total_trades = optimal_weights - initial_weights
        
        return RebalanceSolution(
            model="Scipy",
            decision_variables={
                'portfolio_weights': type('W', (), {'level': lambda self=optimal_weights: optimal_weights})().level(),
                'total_trades': type('T', (), {'level': lambda self=total_trades: total_trades})().level()
            },
            rebalance_problem=rebalance_problem
        )
    
    # def _setup_constraints(self, weights, rebalance_problem: RebalanceProblem):
    #     pass

    def _set_objective(self, rebalance_problem: RebalanceProblem):
        mean_vector = rebalance_problem.mean_vector
        def objective(weights):
            return mean_vector.T @ weights
        return objective

    def output_efficient_frontier(self, rebalance_problem: RebalanceProblem):
        pass