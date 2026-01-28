from dataclasses import dataclass
import numpy as np
from scipy.optimize import minimize
from collections import defaultdict

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

		bounds = self._setup_position_bounds(rebalance_problem)
		constraints = self._setup_constraints(rebalance_problem, current_weights)
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

	def _setup_position_bounds(self, 
							   rebalance_problem: RebalanceProblem) -> list:
		"""Setup position size bounds."""
		n_assets = len(rebalance_problem.tickers)
		max_bound = getattr(rebalance_problem, "max_position_size")
		if max_bound is None or max_bound == 0:
			max_bound = 1.0
		return [(0, max_bound) for _ in range(n_assets)]

	def _setup_constraints(self, rebalance_problem: RebalanceProblem, 
						   current_weights: np.ndarray = None) -> list:
		"""Setup constraints for the optimization problem."""
		constraints = []
		self._setup_portfolio_constraints(constraints, rebalance_problem)
		self._setup_turnover_constraints(constraints, rebalance_problem, current_weights)
		self._setup_asset_class_size_constraints(constraints, rebalance_problem)
		self._setup_sector_size_constraints(constraints, rebalance_problem)
		self._setup_max_num_positions_constraints(constraints, rebalance_problem)
		return constraints
	
	def _setup_portfolio_constraints(self, 
								  	 constraints: list,
								     rebalance_problem: RebalanceProblem) -> list: 
		"""Setup basic portfolio constraints (weights sum to 1, bounds)."""
		constraints += [{'type': 'eq', 'fun': lambda x: np.sum(x) - 1}]
	
	def _setup_turnover_constraints(self, 
								 	constraints: list, 
								 	rebalance_problem: RebalanceProblem, 
								    current_weights: np.ndarray = None) -> list: 
		"""Setup turnover constraints based on trading buffer."""
		if getattr(rebalance_problem, 'turnover_limit') is None or current_weights is None:
			return
		
		constraints += [{
			'type': 'ineq',
			'fun': lambda x: rebalance_problem.turnover_limit - np.sum(np.abs(x - current_weights))
		}]

	def _setup_asset_class_size_constraints(self, 
										    constraints: list, 
											rebalance_problem: RebalanceProblem) -> list:
		"""Setup asset class size constraints (max position size, max number of positions)."""
		return []

	def _setup_sector_size_constraints(self, 
									   constraints: list, 
									   rebalance_problem: RebalanceProblem) -> list:
		"""Setup sector size constraints (max position size, max number of positions)."""
		return []
		
	def _setup_max_num_positions_constraints(self, 
									     constraints: list, 
										 rebalance_problem: RebalanceProblem) -> list:
		"""Setup max number of positions constraints."""
		if getattr(rebalance_problem, "max_number_of_positions") is None:
			return
		
		constraints += [{
			'type': 'ineq',
			'fun': lambda x: rebalance_problem.max_number_of_positions - np.sum(x > 1e-4)
		}]

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

@dataclass
class AssetInfo:
	"""Data class to hold asset information."""
	asset_class: str
	sector: str
	ticker: str

	def __post_init__(self):
		if not all([self.asset_class, self.sector, self.ticker]):
			raise ValueError("AssetInfo fields cannot be empty.")
		
		# hierarch_ex = {
		# 	"Equity": { "Financials": ["JPM"] },
		# 	"fixed_income": { "Government": [""], "Corporate": [""] },
		# 	"Commodity": { "Energy": [], "Metals": [] },
		# 	"Real Estate": { "REITs": [] },
		# 	"Cash": { "Cash": [] }
		# }
	
class AssetSpecificConstraints:
	"""Handles asset-specific constraints for the optimizer."""

	def __init__(self, rebalance_problem: RebalanceProblem):
		self.rebalance_problem = rebalance_problem
		self.tickers = rebalance_problem.tickers

	def get_hierarchy(self):
		"""Get asset class and sector hierarchy for the tickers."""	
		hierarchy = defaultdict(lambda: defaultdict(list))
		for ticker in self.tickers:
			asset_info = self.rebalance_problem.get_asset_info(ticker)
			hierarchy[asset_info.asset_class][asset_info.sector].append(ticker)
		return dict(hierarchy)
