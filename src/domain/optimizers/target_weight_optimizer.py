import logging
import warnings
import numpy as np
import cvxpy as cp
import pandas as pd
from scipy import sparse

from domain.optimizers.base_optimizer import BaseOptimizer
from domain.signals.signals import Signals
from domain.portfolio.tax_lot_ledger import TaxLotLedger
from models.rebalance_problem import RebalanceProblem
from models.rebalance_solution import RebalanceSolution
from models.rebalance_context import RebalanceContext, tradable_mask

SOLVER_OPTIONS = {cp.SCS: {"max_iters": 5000}}
MAX_INACCURATE_VIOLATION = 1e-4

class TargetWeightOptimizer(BaseOptimizer):
	"""Optimizer using Cvxpy's minimize function."""
	def __init__(self):
		super().__init__()
		self.logger = logging.getLogger(__name__)
		self._risky_indices = []
		self._risky_tickers = []
		self._tradable = None

	def optimize(self, 
			     rebalance_context: RebalanceContext, 
				 active_signal: Signals = None) -> RebalanceSolution:
		"""Optimize portfolio weights for the given rebalance problem."""
		current_weights = self._current_weights(rebalance_context)
		self._set_risky_universe(rebalance_context.rebalance_problem)
		self._tradable = tradable_mask(rebalance_context).to_numpy()
		decision_variables = self._setup_decision_variables(
			rebalance_context.rebalance_problem, 
			rebalance_context.tax_lot_ledger
		)
	
		constraints = self._setup_constraints(
			decision_variables,
			rebalance_context,
			active_signal,
			current_weights
		)
		objective = self._setup_objective(
			decision_variables, 
			rebalance_context.rebalance_problem, 
			active_signal, 
			rebalance_context.tax_lot_ledger
		)
		prob = cp.Problem(objective, constraints)
		solver_fallback = self._run_solver(prob, current_weights, rebalance_context.rebalance_problem)
		if solver_fallback is not None:
			return solver_fallback

		return self._prepare_optimizer_output(
			decision_variables, 
			rebalance_context.rebalance_problem, 
			rebalance_context.tax_lot_ledger
		)

	def _run_solver(self, 
	                prob: cp.Problem, 
					current_weights: pd.Series, 
					rebalance_problem: RebalanceProblem) -> RebalanceSolution | None:
		"""Run solvers and return fallback solution on failure, else None."""
		for solver in [cp.CLARABEL, cp.SCS, cp.OSQP]:
			try:
				with warnings.catch_warnings():
					warnings.filterwarnings(
						"ignore",
						message="Solution may be inaccurate.*",
						category=UserWarning,
					)
					prob.solve(
						solver=solver, 
						verbose=False, 
						**SOLVER_OPTIONS.get(solver, {}), 
						warm_start=True)

				if prob.status == cp.OPTIMAL:
					self.logger.info("reason_code=solver_success solver=%s status=%s", solver, prob.status)
					return None

				if prob.status == cp.OPTIMAL_INACCURATE:
					violation = max((float(np.max(c.violation())) for c in prob.constraints), default=0.0)
					if np.isfinite(violation) and violation <= MAX_INACCURATE_VIOLATION:
						self.logger.warning(
							"reason_code=solver_inaccurate solver=%s status=%s violation=%.2e",
							solver, prob.status, violation,
						)
						return None
					self.logger.warning(
						"reason_code=solver_inaccurate_rejected solver=%s violation=%.2e", solver, violation,
					)
					continue

				self.logger.warning("reason_code=solver_nonoptimal solver=%s status=%s", solver, prob.status)
			except cp.SolverError as e:
				self.logger.warning("reason_code=solver_error solver=%s error=%s", solver, e)
			except Exception as e:
				self.logger.warning("reason_code=solver_exception solver=%s error=%s", solver, e)

		self.logger.warning("reason_code=solver_failure_fallback status=%s", prob.status)

		return RebalanceSolution(
			target_weights=current_weights.reindex(rebalance_problem.investment_universe),
			sell_allocations={},
			realized_tax_cost=0.0,
			tracking_error=0.0,
		)

	def _prepare_optimizer_output(self, 
							   	  decision_variables: dict, 
								  rebalance_problem: RebalanceProblem, 
								  tax_lot_ledger: TaxLotLedger) -> RebalanceSolution:
		"""Prepare the output of the optimizer for reporting and ledger updates."""
		tickers = rebalance_problem.investment_universe
		target_weights = decision_variables['portfolio_weights'].value
		
		tax_enabled = (
			tax_lot_ledger is not None
			and getattr(rebalance_problem, "apply_tax_objective", False)
		)

		if not tax_enabled:
			return RebalanceSolution(
				target_weights=pd.Series(target_weights, index=tickers),
				sell_allocations={},
				realized_tax_cost=0.0,
				tracking_error=None,
			)

		tax_solution = self._build_tax_solution(
			decision_variables=decision_variables,
			target_weights=target_weights,
			tickers=tickers,
			sell_fractions=np.asarray(decision_variables["portfolio_sell_fractions"].value, dtype=float),
			tax_lot_ledger=tax_lot_ledger,
		)
		return tax_solution

	def _build_tax_solution(self,
	                        decision_variables: dict, 
	                        target_weights: np.ndarray, 
							tickers: list, sell_fractions: np.ndarray, 
							tax_lot_ledger: TaxLotLedger) -> RebalanceSolution:
		"""Build a tax-aware rebalance solution based on the decision variables, target weights, and tax lot ledger."""
		tax_lots = tax_lot_ledger.tax_lots if tax_lot_ledger is not None else pd.DataFrame()
		if tax_lots.empty:
			return RebalanceSolution(
				target_weights=pd.Series(target_weights, index=tickers),
				sell_allocations={},
				realized_tax_cost=0.0,
				tracking_error=None,
			)

		sell_fractions = np.asarray(decision_variables["portfolio_sell_fractions"].value, dtype=float)
		TOL = 1e-4
		bad = (sell_fractions < -TOL) | (sell_fractions > 1 + TOL)
		if bad.any():
			raise ValueError(f"Solver returned sell fractions outside [0,1] beyond tolerance: "
							f"{sell_fractions[bad][:5]} (status may be inaccurate)")
		sell_fractions = np.clip(sell_fractions, 0.0, 1.0)
		sell_fractions[sell_fractions < 1e-8] = 0.0
		sell_allocations = {
			lot_id: float(sell_fraction)
			for lot_id, sell_fraction in zip(tax_lots.index, sell_fractions)
		}

		realized_tax_cost = float(
			np.dot(
				tax_lots["TaxCost"].to_numpy(),
				np.asarray(sell_fractions),
			)
		)
		
		return RebalanceSolution(
			target_weights=pd.Series(target_weights, index=tickers),
			sell_allocations=sell_allocations,
			realized_tax_cost=realized_tax_cost,
			tracking_error=None
		)		

	def _set_risky_universe(self, rebalance_problem: RebalanceProblem) -> None:
		"""Cache the non-cash universe for the current optimization request."""
		investment_universe = getattr(rebalance_problem, "investment_universe")
		if rebalance_problem.has_cash:
			cash_idx = rebalance_problem.cash_index
			self._risky_indices = [
				i for i, _ in enumerate(investment_universe) if i != cash_idx
			]
		else:
			self._risky_indices = list(range(len(investment_universe)))
		self._risky_tickers = [
			investment_universe[index] for index in self._risky_indices
		]
	
	def _setup_decision_variables(self, 
							      rebalance_problem: RebalanceProblem,
								  tax_lot_ledger: TaxLotLedger) -> dict:
		"""Setup decision variables for the optimization problem."""
		n_assets = rebalance_problem.n_assets
		n_risky_assets = len(self._risky_indices)
		n_tax_lots = len(tax_lot_ledger.tax_lots) if tax_lot_ledger is not None else 0
		portfolio_weights = cp.Variable(n_assets)
		portfolio_buys = cp.Variable(n_risky_assets, nonneg=True)
		portfolio_sells = cp.Variable(n_risky_assets, nonneg=True)
		portfolio_abs_weights = cp.Variable(n_assets, nonneg=True)
		portfolio_long_weights = cp.Variable(n_assets, nonneg=True)
		portfolio_short_weights = cp.Variable(n_assets, nonneg=True)
		portfolio_sell_fractions = cp.Variable(n_tax_lots, nonneg=True) if n_tax_lots > 0 else None
		decision_variables = {
			'portfolio_weights': portfolio_weights,
			'portfolio_buys': portfolio_buys,
			'portfolio_sells': portfolio_sells,
			'portfolio_abs_weights': portfolio_abs_weights,
			'portfolio_long_weights': portfolio_long_weights,
			'portfolio_short_weights': portfolio_short_weights
		}
		if portfolio_sell_fractions is not None:
			decision_variables['portfolio_sell_fractions'] = portfolio_sell_fractions
		return decision_variables

	def _setup_constraints(self, 
						   decision_variables: dict,
						   rebalance_context: RebalanceContext,
						   active_signal: Signals,
					   	   current_weights: pd.Series = None) -> list:
		"""Setup constraints for the optimization problem."""
		constraints = []
		constraints.extend(
			self._setup_portfolio_constraints(decision_variables, rebalance_context.rebalance_problem, current_weights)
		)
		constraints.extend(
			self._setup_gross_exposure_constraints(decision_variables, rebalance_context.rebalance_problem)
		)
		constraints.extend(
			self._setup_long_short_decomposition_constraints(decision_variables, rebalance_context.rebalance_problem)
		)
		constraints.extend(
			self._setup_turnover_constraints(decision_variables, rebalance_context.rebalance_problem, current_weights)
		)
		constraints.extend(
			self._setup_beta_exposure_constraints(
				decision_variables, rebalance_context.rebalance_problem, getattr(active_signal, "beta_vector", None)
			)
		)
		constraints.extend(
			self._setup_asset_class_constraints(decision_variables, rebalance_context.rebalance_problem)
		)
		constraints.extend(
			self._setup_sector_constraints(decision_variables, rebalance_context.rebalance_problem)
		)
		constraints.extend(
			self._setup_tax_constraints(decision_variables, rebalance_context.rebalance_problem, rebalance_context.tax_lot_ledger)
		)
		return constraints
	
	def _setup_portfolio_constraints(self, 
								     decision_variables: dict,
								     rebalance_problem: RebalanceProblem,
								 	 current_weights: pd.Series = None) -> list: 
		"""Setup basic portfolio constraints (weights sum to 1, bounds)."""
		min_position_size = getattr(rebalance_problem, 'min_position_size', 0.0)
		max_position_size = getattr(rebalance_problem, 'max_position_size', 1.0)
		net_exposure = getattr(rebalance_problem, 'net_exposure', 1.0)
		portfolio_weights = decision_variables.get('portfolio_weights')
		portfolio_buys = decision_variables.get('portfolio_buys')
		portfolio_sells = decision_variables.get('portfolio_sells')
		risky_current = current_weights.iloc[self._risky_indices]
		risky_weights = portfolio_weights[self._risky_indices]

		constraints = [
			cp.sum(portfolio_weights) == net_exposure,
			risky_weights - risky_current == portfolio_buys - portfolio_sells,
		]
		if self._tradable is None or self._tradable.all():
			return constraints + [
				portfolio_weights >= min_position_size,
				portfolio_weights <= max_position_size,
			]

		tradable_idx = np.flatnonzero(self._tradable)
		untradable_idx = np.flatnonzero(~self._tradable)
		constraints.append(portfolio_weights[untradable_idx] == 0)
		if len(tradable_idx):
			constraints += [
				portfolio_weights[tradable_idx] >= min_position_size,
				portfolio_weights[tradable_idx] <= max_position_size,
			]
		return constraints

	def _allows_shorts(self, rebalance_problem) -> bool:
		return (getattr(rebalance_problem, "max_short", 0.0) or 0.0) > 0 \
			or (getattr(rebalance_problem, "min_position_size", 0.0) or 0.0) < 0
	
	def _setup_gross_exposure_constraints(self,
										  decision_variables: dict,
										  rebalance_problem: RebalanceProblem) -> list:
		"""Setup gross exposure constraints based on the gross exposure limit."""
		if not self._allows_shorts(rebalance_problem):
			return []		
		gross_exposure = getattr(rebalance_problem, 'gross_exposure', 1.0)
		portfolio_long_weights = decision_variables.get('portfolio_long_weights')
		portfolio_short_weights = decision_variables.get('portfolio_short_weights')
		return [
			cp.sum(portfolio_long_weights + portfolio_short_weights) <= gross_exposure
		]

	def _setup_long_short_decomposition_constraints(self, decision_variables, rebalance_problem):
		"""Setup long/short decomposition constraints."""	
		if not self._allows_shorts(rebalance_problem):
			return []
		max_long  = getattr(rebalance_problem, 'max_long', 1.0)
		max_short = getattr(rebalance_problem, 'max_short', 0.0)
		w     = decision_variables.get('portfolio_weights')
		long  = decision_variables.get('portfolio_long_weights')
		short = decision_variables.get('portfolio_short_weights')
		absw  = decision_variables.get('portfolio_abs_weights')

		return [
			w == long - short,
			absw == long + short,
			cp.sum(long)  <= max_long,
			cp.sum(short) <= max_short,
		]
	
	def _setup_volatility_constraints(self, 
								   	  decision_variables: dict,
								   	  rebalance_problem: RebalanceProblem,
								   	  signals: Signals) -> list:
		"""Setup volatility constraints based on optimizer volatility constraint."""
		optimizer_vol_constraint = getattr(rebalance_problem, 'optimizer_vol_constraint', None)
		if optimizer_vol_constraint is None or signals is None:
			return []
		
		portfolio_weights = decision_variables.get('portfolio_weights')
		risky_weights = portfolio_weights[self._risky_indices]
		cov_matrix = signals.covariance_matrix()[np.ix_(self._risky_indices, self._risky_indices)]
		portfolio_risk = cp.quad_form(risky_weights, cp.psd_wrap(cov_matrix))
		return [
			portfolio_risk <= optimizer_vol_constraint ** 2
		]

	def _setup_turnover_constraints(self, 
								    decision_variables: dict,
								    rebalance_problem: RebalanceProblem,
									current_weights: pd.Series = None) -> list: 
		"""Setup turnover constraints based on turnover limit."""
		if getattr(rebalance_problem, 'turnover_limit') is None or current_weights is None:
			return []
		
		portfolio_weights = decision_variables.get('portfolio_weights')	
		risky_current = current_weights.iloc[self._risky_indices]
		risky_weights = portfolio_weights[self._risky_indices]

		return [
			cp.norm1(risky_weights - risky_current) <= rebalance_problem.turnover_limit
		]

	def _setup_beta_exposure_constraints(self,
									  	decision_variables: dict,
									  	rebalance_problem: RebalanceProblem,
									  	beta_vector: np.ndarray = None) -> list:
		"""Setup a beta-neutral exposure cap when configured."""
		max_beta_exposure = getattr(rebalance_problem, 'max_beta_exposure', None)
		if max_beta_exposure is None or beta_vector is None:
			return []
		
		portfolio_weights = decision_variables.get('portfolio_weights')
		beta_vector = np.asarray(beta_vector, dtype=float)
		if beta_vector.shape[0] != portfolio_weights.shape[0]:
			return []

		beta_vector = np.nan_to_num(beta_vector, nan=0.0, posinf=0.0, neginf=0.0)
		return [
			cp.abs(beta_vector @ portfolio_weights) <= max_beta_exposure
		]

	def _setup_asset_class_constraints(self,
								       decision_variables: dict,
								       rebalance_problem: RebalanceProblem) -> list:
		"""Setup asset class size constraints: Equity < 90%, Fixed < 20%, etc..."""
		if getattr(rebalance_problem, "asset_class_constraints") is None:
			return []

		portfolio_weights = decision_variables.get('portfolio_weights')
		asset_class_map = rebalance_problem.asset_class_map
		asset_class_constraints = rebalance_problem.asset_class_constraints
		constraints = []
		if asset_class_constraints is None:
			return constraints
		
		for asset_class, min_max in asset_class_constraints.items():
			if asset_class not in asset_class_map:
				continue
	
			min_weight, max_weight = min_max[0], min_max[1]
			indices = [idx[0] for idx in asset_class_map[asset_class]] \
				if asset_class != "Cash" else [asset_class_map[asset_class][0]]
			indices = self._tradable_indices(indices)
			if not indices:
				continue
			class_weight = cp.sum(portfolio_weights[indices])
			
			if min_weight > 0:
				constraints.append(class_weight >= min_weight)
			
			if max_weight < 1:
				constraints.append(class_weight <= max_weight)
		return constraints

	def _setup_sector_constraints(self, 
								  decision_variables: dict,
								  rebalance_problem: RebalanceProblem) -> list:
		"""Setup asset class size constraints: Financials < 15%, Tech: 20%, etc..."""
		if getattr(rebalance_problem, "sector_constraints") is None:
			return []

		portfolio_weights = decision_variables.get('portfolio_weights')
		sector_constraints = rebalance_problem.sector_constraints
		sector_map = rebalance_problem.sector_map
		constraints = []
		if sector_constraints is None or sector_map is None:
			return constraints
				
		for sector, min_max in sector_constraints.items():
			if sector not in sector_map:
				continue

			min_weight, max_weight = min_max[0], min_max[1]
			indices = [idx[0] for idx in sector_map[sector]] \
				if sector != "Cash" else [sector_map[sector][0]]
			indices = self._tradable_indices(indices)
			if not indices:
				continue
			sector_weight = cp.sum(portfolio_weights[indices])

			if min_weight > 0:
				constraints.append(sector_weight >= min_weight)

			if max_weight < 1:
				constraints.append(sector_weight <= max_weight)
		return constraints

	def _setup_tax_constraints(self,
							   decision_variables: dict,
							   rebalance_problem: RebalanceProblem,
							   tax_lot_ledger: TaxLotLedger) -> list:
		"""Setup tax constraints based on tax lot ledger and sell fractions."""
		if tax_lot_ledger is None or getattr(rebalance_problem, "apply_tax_objective", False) is False:
			return []
		
		tax_lots = tax_lot_ledger.tax_lots
		if tax_lots.empty or tax_lot_ledger.nav <= 0.0:
			return []

		sell_trades = decision_variables.get('portfolio_sells')
		sell_fractions = decision_variables.get('portfolio_sell_fractions')

		# Lots are worth weight * NAV per ticker, so dividing by NAV turns lot sales into weight sold.
		lot_weights = tax_lots["CurrentValue"].to_numpy(dtype=float) / tax_lot_ledger.nav
		lot_to_ticker = self._map_lot_to_ticker(tax_lots)
		weight_reduction_per_ticker = lot_to_ticker.T @ cp.multiply(lot_weights, sell_fractions)

		return [
			sell_fractions <= 1,
			sell_trades == weight_reduction_per_ticker
		]

	def _setup_objective(self, 
					   	 decision_variables: dict, 
					   	 rebalance_problem: RebalanceProblem, 
					   	 signals: Signals = None,
						 tax_lot_ledger: TaxLotLedger = None) -> callable:
		"""Set objective function for the optimization problem"""
		risk_aversion = getattr(rebalance_problem, 'risk_aversion', 1.0)
		transaction_cost = getattr(rebalance_problem, 'transaction_cost', 0.003)
		portfolio_weights = decision_variables.get('portfolio_weights')
		mean_vector = np.array(signals.mean_returns(), dtype=float)
		finite = np.isfinite(mean_vector)
		expected_median_vector = float(np.median(mean_vector[finite])) if finite.any() else 0.0
		mean_vector = np.where(finite, mean_vector, expected_median_vector)

		# Get indices of risky assets and their corresponding weights
		risky_weights = portfolio_weights[self._risky_indices]
		cov_matrix = signals.covariance_matrix()[np.ix_(self._risky_indices, self._risky_indices)]
		mean_vector = mean_vector[self._risky_indices]

		# Calculate portfolio risk, concentration objective, and transaction cost penalty
		portfolio_risk = cp.quad_form(risky_weights, cp.psd_wrap(cov_matrix))
		concentration_objective = self._get_concentration_objective(risky_weights, rebalance_problem)
		transaction_cost_penalty = self._get_transaction_cost_penalty(transaction_cost, decision_variables)
		tax_cost_objective = self._get_tax_cost_objective(decision_variables, rebalance_problem, tax_lot_ledger)

		# Define the objective function to maximize returns minus risk, concentration, and transaction costs
		objective = cp.Maximize(mean_vector @ risky_weights - risk_aversion * \
						  portfolio_risk - concentration_objective - transaction_cost_penalty - tax_cost_objective)
		return objective

	def _get_concentration_objective(self, 
									 risky_weights,
								 	 rebalance_problem: RebalanceProblem):
		"""Set concentration objective that will penalize large weights."""
		concentration_penalty = cp.sum_squares(risky_weights)
		concentration_strength = getattr(rebalance_problem, "concentration_strength", 0.0)
		if concentration_strength == 0:
			return 0
		return concentration_penalty * concentration_strength
	
	def _get_transaction_cost_penalty(self,
								   	  transaction_cost: float,
									  decision_variables: dict): 
		"""Set transaction cost penalty based on turnover from current weights to new weights."""
		portfolio_buys = decision_variables.get('portfolio_buys')
		portfolio_sells = decision_variables.get('portfolio_sells')
		return transaction_cost * (cp.sum(portfolio_buys) + cp.sum(portfolio_sells))

	def _get_tax_cost_objective(self,
					  decision_variables: dict,
					  rebalance_problem: RebalanceProblem,
					  tax_lot_ledger: TaxLotLedger):
		"""Set tax cost penalty based on realized gains from selling tax lots."""
		if tax_lot_ledger is None or rebalance_problem.apply_tax_objective is False:
			return 0

		tax_lots = tax_lot_ledger.tax_lots
		sell_fractions = decision_variables.get('portfolio_sell_fractions')
		if tax_lots.empty or sell_fractions is None:
			return 0
		tax_costs = tax_lots["TaxCost"].to_numpy(dtype=float)
		return cp.sum(cp.multiply(tax_costs / tax_lot_ledger.nav, sell_fractions))

	def _tradable_indices(self, indices: list) -> list:
		"""Group members that can trade today."""
		if self._tradable is None:
			return list(indices)
		return [i for i in indices if self._tradable[i]]
	
	def _map_lot_to_ticker(self, tax_lots: pd.DataFrame) -> sparse.csr_matrix:
		"""Sparse (n_lots x n_risky) indicator matrix: lot i belongs to risky ticker j."""
		ticker_positions = {ticker: index for index, ticker in enumerate(self._risky_tickers)}
		columns = tax_lots["Ticker"].map(ticker_positions)
		rows = np.flatnonzero(columns.notna().to_numpy())
		return sparse.csr_matrix(
			(np.ones(len(rows)), (rows, columns.iloc[rows].astype(int).to_numpy())),
			shape=(len(tax_lots), len(self._risky_tickers)),
		)

	@staticmethod
	def _current_weights(rebalance_context: RebalanceContext) -> pd.Series:
		"""Retrieve the current weights for the given rebalance context, falling back to initial weights if necessary."""
		rp = rebalance_context.rebalance_problem
		tickers = rp.investment_universe
		current = rebalance_context.current_weights
		if current is None:
			return pd.Series([rp.initial_weights.get(t, 0.0) for t in tickers], index=tickers, dtype=float)
		if not isinstance(current, pd.Series):
			return pd.Series(current, index=tickers, dtype=float)
		return current.reindex(tickers).astype(float).fillna(0.0)