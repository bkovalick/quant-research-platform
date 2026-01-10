
import gurobipy as gp
import numpy as np

from .ioptimizer import IOptimizer
from .decision_variables_max_sharpe import MaximizeSharpeDecisionVariables
from data.rebalance_problem import RebalanceProblem

class MaximizeSharpeOptimizer(IOptimizer):
    def optimize(self, rebalance_problem: RebalanceProblem):
        self.model = gp.Model("MaximizeSharpe")
        decision_variables = self.get_decision_variables(rebalance_problem)
        self.build_constraints(rebalance_problem, decision_variables)
        self.set_objective(rebalance_problem, decision_variables)
        self.model.update()
        self.model.optimize()

        if self.model.status == gp.GRB.OPTIMAL:
            self.print_model_results(rebalance_problem, decision_variables)
            self.model.dispose()
        else:
            print("No optimal solution found.")

    def print_model_results(self, rebalance_problem, decision_variables):
        objVal = self.model.objVal
        mu = rebalance_problem.get_return_series
        rf = rebalance_problem.get_risk_free_rate
        covMatrix = rebalance_problem.get_covariance_matrix
        y_optimal = decision_variables.weights.X
        x_optimal = y_optimal / np.sum(y_optimal)
        print("Optimal weights (x):")
        print(x_optimal)
        sharpe_ratio = (np.dot(mu, x_optimal) - rf) / np.sqrt(x_optimal @ covMatrix @ x_optimal)
        print(f"Max Sharpe Ratio: {sharpe_ratio}") 

    def get_decision_variables(self, rebalance_problem)-> MaximizeSharpeDecisionVariables:
        n_constituents = rebalance_problem.n_constituents
        decision_variables = MaximizeSharpeDecisionVariables(n_constituents)
        return decision_variables

    def build_constraints(self, rebalance_problem, decision_variables)-> None:
        mu = rebalance_problem.get_return_series
        adjusted_mu = [mu[i] - rebalance_problem.get_risk_free_rate for i in range(len(mu))]
        self.model.addConstr(gp.quicksum(decision_variables.weights[i] \
                                         for i in range(len(decision_variables.weights))) == 1, name="weight_sum")
        self.model.addConstr(decision_variables.weights @ adjusted_mu == 1, name="return_constraint")

    def set_objective(self, rebalance_problem, decision_variables)-> None:
        weights = decision_variables.weights
        covMatrix = rebalance_problem.get_covariance_matrix
        self.model.setObjective(weights @ covMatrix @ weights, gp.GRB.MINIMIZE)

# Method 2: Manual Convex Reformulation using gurobipy If you need more control over the model (e.g., adding specific custom constraints like L1 norm constraints), you can manually implement the convex reformulation using the core gurobipy API. The original Sharpe ratio objective function is non-convex:\(\max _{x}\frac{\mu ^{T}x-r_{f}}{\sqrt{x^{T}\Sigma x}}\quad \text{s.t.}\quad \sum x_{i}=1,x\ge 0\)It can be reformulated as a convex quadratic program (QP) by introducing a variable change \(y=\frac{x}{\mu ^{T}x-r_{f}}\) (assuming \(\mu ^{T}x>r_{f}\)):\(\min _{y}y^{T}\Sigma y\quad \text{s.t.}\quad (\mu -r_{f})^{T}y=1,y\ge 0\)After solving for \(y\), the optimal weights \(x\) are recovered by \(x_{i}=\frac{y_{i}}{\sum _{j}y_{j}}\). Here is a general outline of the manual implementation using gurobipy: 
