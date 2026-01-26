import numpy as np
from scipy.optimize import minimize

from core.optimizers.ioptimizer import IOptimizer
from portfolio.rebalance_problem import RebalanceProblem
from models.rebalance_solution import RebalanceSolution
from signals.signals import Signals

class Optimizer(IOptimizer):
	"""Optimizer using SciPy's minimize function with SLSQP method."""
	def __init__(self):
		super().__init__()

	def optimize(self, 
			  rebalance_problem: RebalanceProblem, 
			  signals: Signals = None,
			  current_weights: np.ndarray = None) -> RebalanceSolution:
		"""Optimize portfolio weights for the given rebalance problem."""
		if current_weights is None:
			current_weights = np.array(rebalance_problem.initial_weights)
		constraints, bounds = self._setup_constraints(rebalance_problem, current_weights)
		objective = self._set_objective(rebalance_problem, signals)
	
		result = minimize(
			objective,
			x0=current_weights,
			method='SLSQP',
			bounds=bounds,
			constraints=constraints
		)

		if not result.success:
			raise RuntimeError(f"Optimization failed: {result.message}")

		optimal_weights = result.x
		total_trades = optimal_weights - current_weights
        
		return RebalanceSolution(
			model="Scipy",
			decision_variables={
				'portfolio_weights': optimal_weights,
				'total_trades': total_trades
			},
			rebalance_problem=rebalance_problem
		)

	def _setup_constraints(self, rebalance_problem: RebalanceProblem, current_weights: np.ndarray = None) -> list:
		"""Setup constraints for the optimization problem."""
		portfolio_constraints, bounds = self._setup_portfolio_constraints(rebalance_problem)
		turnover_constraints = self._setup_turnover_constraints(rebalance_problem, current_weights)
		return portfolio_constraints + turnover_constraints, bounds
	
	def _setup_portfolio_constraints(self, rebalance_problem: RebalanceProblem) -> list: 
		"""Setup basic portfolio constraints (weights sum to 1, bounds)."""
		n_assets = len(rebalance_problem.tickers)
		constraints = [{'type': 'eq', 'fun': lambda x: np.sum(x) - 1}]
		bounds = [(0, 1) for _ in range(n_assets)]
		return constraints, bounds
	
	def _setup_turnover_constraints(self, rebalance_problem: RebalanceProblem, current_weights: np.ndarray = None) -> list: 
		"""Setup turnover constraints based on trading buffer."""
		constraints = []
		if getattr(rebalance_problem, 'turnover_limit') is not None:
			constraints.append({
				'type': 'ineq',
				'fun': lambda x: rebalance_problem.turnover_limit - np.sum(np.abs(x - current_weights))
			})
		return constraints

	def _set_objective(self, rebalance_problem: RebalanceProblem, signals: Signals = None) -> callable:
		"""Set the objective function based on rebalance problem settings."""
		if getattr(rebalance_problem, 'apply_max_return_objective'):
			return self._set_maximize_return_objective(rebalance_problem, signals)
		elif getattr(rebalance_problem, 'apply_sharpe_objective'):
			return self._set_maximum_sharpe_objective(rebalance_problem, signals)
	
	def _set_maximize_return_objective(self, rebalance_problem: RebalanceProblem, signals: Signals) -> callable:
		"""Set objective to maximize returns minus risk penalty."""
		mean_vector = signals.mean_returns
		cov_matrix = signals.covariance_matrix
		risk_tolerance = getattr(rebalance_problem, 'risk_tolerance', 1.0)
		def objective(weights):
			return - (mean_vector @ weights - risk_tolerance * (weights @ cov_matrix @ weights))
		return objective		

	def _set_maximum_sharpe_objective(self, rebalance_problem: RebalanceProblem, signals: Signals) -> callable:
		"""Set objective to maximize Sharpe ratio."""
		mean_vector = signals.mean_returns
		cov_matrix = signals.covariance_matrix
		risk_free_rate = getattr(rebalance_problem, 'risk_free_rate', 0.0)
		def objective(weights):
			port_return = mean_vector @ weights
			port_vol = np.sqrt(weights.T @ cov_matrix @ weights)
			if port_vol == 0:
				return 1e6
			return - (port_return - risk_free_rate) / port_vol
		return objective

	def output_efficient_frontier(self, rebalance_problem: RebalanceProblem):
		"""Generate efficient frontier by varying risk tolerance."""
		for risk_tolerance in np.linspace(0.1, 10, 50):
			rebalance_problem._data['risk_tolerance'] = risk_tolerance
			solution = self.optimize(rebalance_problem)
			yield risk_tolerance, solution.decision_variables['portfolio_weights']
