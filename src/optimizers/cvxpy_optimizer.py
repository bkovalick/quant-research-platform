import numpy as np
from collections import defaultdict
import cvxpy as cp

from core.optimizers.ioptimizer import IOptimizer
from portfolio.rebalance_problem import RebalanceProblem
from models.rebalance_solution import RebalanceSolution
from signals.signals import Signals

class CvxpyOptimizer(IOptimizer):
	"""Optimizer using Cvxpy's minimize function."""
	def optimize(self, 
			  rebalance_problem: RebalanceProblem, 
			  signals: Signals = None,
			  current_weights: np.ndarray = None) -> RebalanceSolution:
		"""Optimize portfolio weights for the given rebalance problem."""
		if current_weights is None:
			current_weights = np.array(rebalance_problem.initial_weights)				

		decision_variables = self._setup_decision_variables(rebalance_problem)
		constraints = self._setup_constraints(decision_variables, rebalance_problem, signals, current_weights)
		objective = self._set_objective(decision_variables, rebalance_problem, signals)
		prob = cp.Problem(objective, constraints)

		try:
			prob.solve(solver=cp.ECOS, verbose=False)
		except cp.SolverError as e:
			try:
				prob.solve(solver=cp.OSQP, verbose=False)
			except cp.SolverError as e:
				raise RuntimeError(f"Optimization failed: {str(e)}")
			
		if prob.status not in [cp.OPTIMAL, cp.OPTIMAL_INACCURATE]:
			raise RuntimeError(f"Optimization failed: Problem status {prob.status}")
		
		optimal_weights = decision_variables['portfolio_weights'].value
		total_trades = optimal_weights - current_weights
		return RebalanceSolution(
			model="Cvxpy",
			decision_variables={
				'portfolio_weights': optimal_weights,
				'total_trades': total_trades
			},
			rebalance_problem=rebalance_problem
		)		

	def _setup_decision_variables(self, rebalance_problem: RebalanceProblem) -> dict:
		"""Setup decision variables for the optimization problem."""
		n_assets = len(rebalance_problem.tickers)
		portfolio_weights = cp.Variable(n_assets)
		return {'portfolio_weights': portfolio_weights}

	def _setup_constraints(self, 
						   decision_variables: dict,
						   rebalance_problem: RebalanceProblem, 
						   signals: Signals = None,
						   current_weights: np.ndarray = None) -> list:
		"""Setup constraints for the optimization problem."""
		constraints = []
		constraints.extend(
			self._setup_portfolio_constraints(decision_variables, rebalance_problem, signals)
		)
		constraints.extend(
			self._setup_turnover_constraints(decision_variables, rebalance_problem, current_weights)
		)
		constraints.extend(
			self._setup_asset_class_constraints(decision_variables, rebalance_problem, current_weights)
		)
		constraints.extend(
			self._setup_sector_constraints(decision_variables, rebalance_problem, current_weights)
		)
		return constraints

	def _setup_portfolio_constraints(self, 
								     decision_variables: dict,
								     rebalance_problem: RebalanceProblem,
									 signals: Signals = None) -> list: 
		"""Setup basic portfolio constraints (weights sum to 1, bounds)."""
		portfolio_weights = decision_variables.get('portfolio_weights')
		min_position_size = getattr(rebalance_problem, 'min_position_size', 0.0)
		max_position_size = getattr(rebalance_problem, 'max_position_size', 1.0)
		return [
				cp.sum(portfolio_weights) == 1,
				portfolio_weights >= min_position_size,
				portfolio_weights <= max_position_size
			]

	def _setup_turnover_constraints(self, 
								    decision_variables: dict,
								    rebalance_problem: RebalanceProblem,
									current_weights: np.ndarray = None) -> list: 
		"""Setup turnover constraints based on turnover limit."""
		if getattr(rebalance_problem, 'turnover_limit') is None or current_weights is None:
			return []
		
		portfolio_weights = decision_variables.get('portfolio_weights')
		return [
				cp.norm1(portfolio_weights - current_weights) <= rebalance_problem.turnover_limit * 2
		]

	def _setup_asset_class_constraints(self, 
								       decision_variables: dict,
								       rebalance_problem: RebalanceProblem,
									   current_weights: np.ndarray = None) -> list:
		"""Setup asset class size constraints: Equity < 90%, Fixed < 20%, etc..."""
		return []
	
	def _setup_sector_constraints(self, 
								  decision_variables: dict,
								  rebalance_problem: RebalanceProblem,
								  current_weights: np.ndarray = None) -> list:
		"""Setup asset class size constraints: Financials < 15%, Tech: 20%, etc..."""
		return []

	def _set_objective(self, 
					   decision_variables: dict, 
					   rebalance_problem: RebalanceProblem, 
					   signals: Signals = None) -> callable:
		"""Set the objective function based on rebalance problem settings."""
		if getattr(rebalance_problem, 'apply_max_return_objective'):
			return self._set_maximize_return_objective(decision_variables, rebalance_problem, signals)
		
	def _set_maximize_return_objective(self, 
									   decision_variables: dict,
									   rebalance_problem: RebalanceProblem, 
									   signals: Signals) -> callable:
		"""Set objective to maximize returns minus risk penalty."""
		portfolio_weights = decision_variables.get('portfolio_weights')
		mean_vector = signals.mean_returns
		cov_matrix = signals.covariance_matrix
		risk_tolerance = getattr(rebalance_problem, 'risk_tolerance', 1.0)
		portfolio_risk = cp.quad_form(portfolio_weights, cov_matrix)
		concentration_penalty = cp.sum_squares(portfolio_weights)  # penalize large weights
		concentration_strength = 1
		objective = cp.Maximize(mean_vector @ portfolio_weights - risk_tolerance * \
						  portfolio_risk - concentration_strength * concentration_penalty)
		return objective