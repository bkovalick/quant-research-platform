import numpy as np
import cvxpy as cp

from domain.optimizers.ioptimizer import IOptimizer
from models.rebalance_problem import RebalanceProblem
from models.rebalance_solution import RebalanceSolution
from domain.signals.signals import Signals

class PortfolioOptimizer(IOptimizer):
	"""Optimizer using Cvxpy's minimize function."""
	def __init__(self):
		super().__init__()
			
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
			print(f"Optimization failed: Problem status {prob.status} {rebalance_problem.max_return}")
			return current_weights

		optimal_weights = decision_variables['portfolio_weights'].value
		return optimal_weights	

	def _setup_decision_variables(self, rebalance_problem: RebalanceProblem) -> dict:
		"""Setup decision variables for the optimization problem."""
		n_assets = rebalance_problem.n_constituents
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
			self._setup_portfolio_constraints(decision_variables, rebalance_problem)
		)
		constraints.extend(
			self._setup_turnover_constraints(decision_variables, rebalance_problem, current_weights)
		)
		constraints.extend(
			self._setup_asset_class_constraints(decision_variables, rebalance_problem, current_weights)
		)
		# constraints.extend(
		# 	self._setup_sector_constraints(decision_variables, rebalance_problem, current_weights)
		# )
		return constraints

	def _setup_portfolio_constraints(self, 
								     decision_variables: dict,
								     rebalance_problem: RebalanceProblem) -> list: 
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
				cp.norm1(portfolio_weights - current_weights) <= rebalance_problem.turnover_limit
		]

	def _setup_asset_class_constraints(self, 
								       decision_variables: dict,
								       rebalance_problem: RebalanceProblem,
									   current_weights: np.ndarray = None) -> list:
		"""Setup asset class size constraints: Equity < 90%, Fixed < 20%, etc..."""
		if getattr(rebalance_problem, "asset_class_constraints") is None:
			return []

		portfolio_weights = decision_variables.get('portfolio_weights')
		asset_class_map = rebalance_problem.asset_class_map
		asset_class_constraints = rebalance_problem.asset_class_constraints
		constraints = []
		for asset_class, min_max in asset_class_constraints.items():
			if asset_class not in asset_class_map:
				continue
	
			min_weight, max_weight = min_max[0], min_max[1]
			indices = [idx[0] for idx in asset_class_map[asset_class]] \
				if asset_class != "Cash" else [asset_class_map[asset_class][0]] 
			class_weight = cp.sum(portfolio_weights[indices])
			
			if min_weight > 0:
				constraints.append(class_weight >= min_weight)
			
			if max_weight < 1:
				constraints.append(class_weight <= max_weight)
		return constraints

	def _setup_sector_constraints(self, 
								  decision_variables: dict,
								  rebalance_problem: RebalanceProblem,
								  current_weights: np.ndarray = None) -> list:
		"""Setup asset class size constraints: Financials < 15%, Tech: 20%, etc..."""
		if getattr(rebalance_problem, "sector_constraints") is None:
			return []

		portfolio_weights = decision_variables.get('portfolio_weights')
		sector_constraints = rebalance_problem.sector_constraints
		sector_map = rebalance_problem.sector_map
		constraints = []
		for sector, min_max in sector_constraints.items():
			if sector not in sector_map:
				continue

			min_weight, max_weight = min_max[0], min_max[1]
			indices = [idx[0] for idx in sector_map[sector]] \
				if sector != "Cash" else [sector_map[sector][0]] 
			
			sector_weight = cp.sum(portfolio_weights[indices])

			if min_weight > 0:
				constraints.append(sector_weight >= min_weight)

			if max_weight < 1:
				constraints.append(sector_weight <= max_weight)
		return constraints
		

	def _set_objective(self, 
					   decision_variables: dict, 
					   rebalance_problem: RebalanceProblem, 
					   signals: Signals = None) -> callable:
		"""Set the objective function based on rebalance problem settings."""
		if getattr(rebalance_problem, 'apply_max_return_objective'):
			return self._set_maximize_return_objective(decision_variables, rebalance_problem, signals)
		else:
			return
		
	def _set_maximize_return_objective(self, 
									   decision_variables: dict,
									   rebalance_problem: RebalanceProblem, 
									   signals: Signals) -> callable:
		"""Set objective to maximize returns minus risk penalty."""
		risk_tolerance = getattr(rebalance_problem, 'risk_tolerance', 1.0)
		portfolio_weights = decision_variables.get('portfolio_weights')
		mean_vector = signals.mean_returns()
		cov_matrix = signals.covariance_matrix()
		portfolio_risk = cp.quad_form(portfolio_weights, cov_matrix)
		concentration_objective = self._get_concentration_objective(decision_variables, rebalance_problem)
		objective = cp.Maximize(mean_vector @ portfolio_weights - risk_tolerance * \
						  portfolio_risk - concentration_objective)
		return objective
	
	def _get_concentration_objective(self, 
								  	 decision_variables: dict,
									 rebalance_problem: RebalanceProblem):
		"""Set concentration objective that will penalize large weights."""
		portfolio_weights = decision_variables.get('portfolio_weights')
		concentration_penalty = cp.sum_squares(portfolio_weights)
		concentration_strength = getattr(rebalance_problem, "concentration_strength")
		concentration_objective = concentration_penalty * concentration_strength
		return concentration_objective