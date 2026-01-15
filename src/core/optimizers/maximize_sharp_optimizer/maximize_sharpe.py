
from mosek.fusion import *
import numpy as np

from core.optimizers.ioptimizer import IOptimizer
from core.optimizers.maximize_sharp_optimizer.decision_variables_max_sharpe import MaximizeSharpeDecisionVariables
from portfolio.rebalance_problem import RebalanceProblem

class MaximizeSharpeOptimizer(IOptimizer):
    def __init__(self):
        super().__init__()

    def optimize(self, rebalance_problem: RebalanceProblem):
        with Model("maximize_sharpe") as M:
            n = rebalance_problem.n_constituents
            mu = rebalance_problem.get_return_series
            rf = rebalance_problem.get_risk_free_rate
            covMatrix = rebalance_problem.get_covariance_matrix

            # # Decision variables
            # y = M.variable("y", n, Domain.greaterThan(0.0))

            # # Constraints
            # adjusted_mu = [mu[i] - rf for i in range(len(mu))]
            # M.constraint("return_constraint", Expr.dot(adjusted_mu, y), Domain.equalsTo(1.0))

            # # Objective: Minimize y^T * Cov * y
            # quad_expr = Expr.mul(Expr.transpose(y), Expr.mul(Matrix.dense(covMatrix), y))
            # M.objective("MinimizeVariance", ObjectiveSense.Minimize, quad_expr)

            # # Solve the problem
            # M.solve()

            # # Retrieve optimal weights
            # y_optimal = y.level()
            # x_optimal = y_optimal / np.sum(y_optimal)
            # print("Optimal weights (x):")
            # print(x_optimal)
            # sharpe_ratio = (np.dot(mu, x_optimal) - rf) / np.sqrt(x_optimal @ covMatrix @ x_optimal)
            # print(f"Max Sharpe Ratio: {sharpe_ratio}")


""" 
    Method 2: Manual Convex Reformulation using gurobipy If you need more control over the model 
    (e.g., adding specific custom constraints like L1 norm constraints), you can manually implement 
    the convex reformulation using the core gurobipy API. The original Sharpe ratio objective function 
    is non-convex:\(\max _{x}\frac{\mu ^{T}x-r_{f}}{\sqrt{x^{T}\Sigma x}}\quad \text{s.t.}\quad \sum x_{i}=1,x\ge 0\) 
    It can be reformulated as a convex quadratic program (QP) by introducing a variable change \(y=\frac{x}{\mu ^{T}x-r_{f}}\) 
    (assuming \(\mu ^{T}x>r_{f}\)):\(\min _{y}y^{T}\Sigma y\quad \text{s.t.}\quad (\mu -r_{f})^{T}y=1,y\ge 0\)
    After solving for \(y\), the optimal weights \(x\) are recovered by \(x_{i}=\frac{y_{i}}{\sum _{j}y_{j}}\). 
    Here is a general outline of the manual implementation using gurobipy: 
"""