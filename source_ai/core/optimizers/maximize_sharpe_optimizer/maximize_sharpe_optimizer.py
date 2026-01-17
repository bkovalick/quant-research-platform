import numpy as np
from scipy.optimize import minimize
from core.optimizers.ioptimizer import IOptimizer
from portfolio.rebalance_problem import RebalanceProblem
from models.rebalance_solution import RebalanceSolution

class MaximizeSharpeOptimizer(IOptimizer):
    def __init__(self):
        super().__init__()

    def optimize(self, rebalance_problem: RebalanceProblem):
        mean_vector = rebalance_problem.mean_vector
        cov_matrix = rebalance_problem.covariance_matrix
        risk_free_rate = getattr(rebalance_problem, 'risk_free_rate', 0.0)
        n_assets = len(mean_vector)
        initial_weights = getattr(rebalance_problem, 'initial_weights', np.ones(n_assets) / n_assets)

        def neg_sharpe(weights):
            port_return = mean_vector @ weights
            port_vol = np.sqrt(weights.T @ cov_matrix @ weights)
            if port_vol == 0:
                return 1e6  # Penalize zero volatility
            return -(port_return - risk_free_rate) / port_vol

        constraints = [{'type': 'eq', 'fun': lambda x: np.sum(x) - 1}]
        bounds = [(0, 1) for _ in range(n_assets)]

        result = minimize(
            neg_sharpe,
            x0=initial_weights,
            method='SLSQP',
            bounds=bounds,
            constraints=constraints
        )

        if not result.success:
            raise RuntimeError(f"Sharpe optimization failed: {result.message}")

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
