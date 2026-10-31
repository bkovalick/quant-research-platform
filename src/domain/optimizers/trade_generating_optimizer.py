import logging
import numpy as np
import cvxpy as cp
import pandas as pd

from domain.optimizers.base_optimizer import BaseOptimizer
from models.rebalance_solution import RebalanceSolution
    
class TargetWeightTradeGenerator(BaseOptimizer):
	def __init__(self,
				 target_weights: np.ndarray,
				 available_cash: float,
				 prices: np.ndarray):
		super().__init__()
		self.logger = logging.getLogger(__name__)
		self.target_weights = target_weights
		self.available_cash = available_cash
		self.prices = prices

	def optimize(self) -> RebalanceSolution:
		"""Optimize the portfolio to match target weights while respecting available cash."""
		self.logger.debug(
			"Generating trades for %d assets with %.2f available cash",
			len(self.target_weights), self.available_cash
		)
		decision_variables = self._setup_decision_variables()
		constraints = self._setup_constraints(decision_variables)
		objective = self._setup_objective(decision_variables)
		prob = cp.Problem(objective, constraints)

		for solver in ["HIGHS"]:
			try:
				prob.solve(solver=solver, verbose=False)
				if prob.status in [cp.OPTIMAL, cp.OPTIMAL_INACCURATE]:
					break
				self.logger.warning("Solver %s returned status %s", solver, prob.status)
			except (cp.SolverError, Exception) as e:
				self.logger.warning("Solver %s failed: %s", solver, e)
				continue
		else:
			self.logger.warning("No solver produced a usable solution; returning target weights unchanged")
			return RebalanceSolution(
				target_weights=pd.Series(self.target_weights, index=range(len(self.target_weights))),
				sell_allocations={},
				realized_tax_cost=0.0,
				tracking_error=None
			)
				
		optimal_weights = decision_variables.get("optimal_weights").value
		self.logger.debug(
			"Trade generation finished with status %s, remaining cash %.2f",
			prob.status, decision_variables["remaining_cash"].value
		)
		return RebalanceSolution(
			target_weights=pd.Series(optimal_weights, index=range(len(optimal_weights))),
			sell_allocations={},
			realized_tax_cost=0.0,
			tracking_error=None
		)
	
	def _setup_decision_variables(self) -> dict:
		n_assets = len(self.target_weights)
		optimal_weights = cp.Variable(n_assets, integer = True)
		remaining_cash = cp.Variable()
		return {
			"optimal_weights": optimal_weights,
			"remaining_cash": remaining_cash
		}
	
	def _setup_constraints(self, 
	                       decision_variables: dict) -> list:
		constraints = []
		constraints.extend(
			self._setup_unallocated_constraint(decision_variables)
		)
		return constraints

	def _setup_unallocated_constraint(self, 
	                                  decision_variables: dict) -> list:
		optimal_weights = decision_variables.get("optimal_weights")
		remaining_cash = decision_variables.get("remaining_cash")
		actual_dollars = cp.multiply(self.prices, optimal_weights)
		return [
			remaining_cash + cp.sum(actual_dollars) == self.available_cash,
			remaining_cash >= 0,
			optimal_weights >= 0
		]
		
	def _setup_objective(self, 
	                     decision_variables: dict):
		optimal_weights = decision_variables.get("optimal_weights")
		remaining_cash = decision_variables.get("remaining_cash")
		target_dollars = self.target_weights * self.available_cash
		actual_dollars = cp.multiply(self.prices, optimal_weights)
		tracking_error = cp.norm1(target_dollars - actual_dollars)
		objective = cp.Minimize(remaining_cash + tracking_error)
		return objective