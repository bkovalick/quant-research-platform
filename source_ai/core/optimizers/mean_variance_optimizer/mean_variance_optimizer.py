import numpy as np
from scipy.optimize import minimize
from core.optimizers.ioptimizer import IOptimizer
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
        risk_aversion = getattr(rebalance_problem, 'risk_aversion', 1.0)

        def objective(weights):
            return risk_aversion * weights.T @ cov_matrix @ weights - mean_vector.T @ weights

        constraints = [{'type': 'eq', 'fun': lambda x: np.sum(x) - 1}]
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
            decision_variables=type('DV', (), {
                'portfolio_weights': type('W', (), {'level': lambda self=optimal_weights: optimal_weights})(),
                'total_trades': type('T', (), {'level': lambda self=total_trades: total_trades})()
            })(),
            rebalance_problem=rebalance_problem
        )

    def output_efficient_frontier(self, rebalance_problem: RebalanceProblem):
        pass
