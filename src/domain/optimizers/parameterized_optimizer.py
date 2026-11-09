import numpy as np
import pandas as pd
import cvxpy as cp

from domain.signals.signals import Signals
from models.rebalance_problem import RebalanceProblem
from models.rebalance_solution import RebalanceSolution
from models.rebalance_context import RebalanceContext, tradable_mask
from domain.optimizers.target_weight_optimizer import TargetWeightOptimizer

RISK_FACTORS = 50   # covariance factors kept; a dense n x n Parameter exhausts memory under DPP


class ParameterizedOptimizer(TargetWeightOptimizer):
	"""Same mean-variance problem as TargetWeightOptimizer, compiled once and re-solved each date.
	"""

	def __init__(self, rebalance_problem: RebalanceProblem):
		super().__init__()
		self._n = len(rebalance_problem.investment_universe)
		self._build(rebalance_problem)

	def optimize(self,
				 rebalance_context: RebalanceContext,
				 active_signal: Signals = None) -> RebalanceSolution:
		"""Optimize the portfolio for the given rebalance context and active signal."""
		rebalance_problem = rebalance_context.rebalance_problem
		if getattr(rebalance_problem, "apply_tax_objective", False) and rebalance_context.tax_lot_ledger is not None:
			return super().optimize(rebalance_context, active_signal)
		if len(rebalance_problem.investment_universe) != self._n:
			raise ValueError("ParameterizedOptimizer was built for a different universe size")

		current_weights = self._current_weights(rebalance_context)
		self._update(rebalance_context, active_signal, current_weights)
		fallback = self._run_solver(self._prob, current_weights, rebalance_problem)
		if fallback is not None:
			return fallback
		return RebalanceSolution(
			target_weights=pd.Series(self._w.value, index=rebalance_problem.investment_universe),
			sell_allocations={},
			realized_tax_cost=0.0,
			tracking_error=None,
		)

	def _build(self, rp: RebalanceProblem) -> None:
		"""Variables, Parameters, constraints and objective: structure only, no per-date data."""
		self._set_risky_universe(rp)
		self._build_variables()
		self._build_parameters()
		constraints = (
			self._budget_constraint(rp)
			+ self._trade_constraints()
			+ self._position_bound_constraints()
			+ self._long_short_constraints(rp)
			+ self._turnover_constraint(rp)
			+ self._beta_constraint(rp)
			+ self._group_constraints(rp)
		)
		self._prob = cp.Problem(self._objective(rp), constraints)
		if not self._prob.is_dpp():
			raise RuntimeError("ParameterizedOptimizer problem is not DPP; it would recompile every solve")

	def _build_variables(self) -> None:
		"""Create cvxpy Variables for the optimization problem."""
		n_risky = len(self._risky_indices)
		self._w = cp.Variable(self._n)
		self._buys = cp.Variable(n_risky, nonneg=True)
		self._sells = cp.Variable(n_risky, nonneg=True)
		self._w_risky = self._w[self._risky_indices]

	def _build_parameters(self) -> None:
		"""Create cvxpy Parameters for the optimization problem."""
		n_risky = len(self._risky_indices)
		self._k = min(n_risky, RISK_FACTORS)
		self._mu = cp.Parameter(n_risky)
		self._F = cp.Parameter((n_risky, self._k))
		self._d = cp.Parameter(n_risky, nonneg=True)
		self._w0 = cp.Parameter(n_risky)
		self._lb = cp.Parameter(self._n)
		self._ub = cp.Parameter(self._n)
		self._beta = None
		self._gmin = None

	def _budget_constraint(self, rp: RebalanceProblem) -> list:
		"""Weights sum to the net exposure (1.0 long-only)."""
		return [cp.sum(self._w) == getattr(rp, "net_exposure", 1.0)]

	def _trade_constraints(self) -> list:
		"""Buys and sells are the change from current weights (priced by transaction cost)."""
		return [self._w_risky - self._w0 == self._buys - self._sells]

	def _position_bound_constraints(self) -> list:
		"""Per-asset bounds; untradable assets get lb = ub = 0 on that date."""
		return [self._w >= self._lb, self._w <= self._ub]

	def _long_short_constraints(self, rp: RebalanceProblem) -> list:
		"""Long/short books: caps on total long, total short and gross exposure."""
		if not self._allows_shorts(rp):
			return []
		long, short = cp.Variable(self._n, nonneg=True), cp.Variable(self._n, nonneg=True)
		return [
			self._w == long - short,
			cp.sum(long) <= getattr(rp, "max_long", 1.0),
			cp.sum(short) <= getattr(rp, "max_short", 0.0),
			cp.sum(long + short) <= getattr(rp, "gross_exposure", 1.0),
		]

	def _turnover_constraint(self, rp: RebalanceProblem) -> list:
		"""One-way trading per rebalance is capped at turnover_limit."""
		if getattr(rp, "turnover_limit", None) is None:
			return []
		return [cp.norm1(self._w_risky - self._w0) <= rp.turnover_limit]

	def _beta_constraint(self, rp: RebalanceProblem) -> list:
		"""|portfolio beta| <= max_beta_exposure; beta is a Parameter refreshed each date."""
		if getattr(rp, "max_beta_exposure", None) is None:
			return []
		self._beta = cp.Parameter(self._n)
		return [cp.abs(self._beta @ self._w) <= rp.max_beta_exposure]

	def _group_constraints(self, rp: RebalanceProblem) -> list:
		"""Asset-class and sector limits as one membership matrix G. Minimums are Parameters so a
		group with no tradable members (e.g. bonds before AGG lists) is relaxed to 0 that date."""
		self._groups, maxima = [], []
		for group_map, limits in ((rp.asset_class_map, rp.asset_class_constraints),
								  (rp.sector_map, rp.sector_constraints)):
			for name, (minimum, maximum) in (limits or {}).items():
				if not group_map or name not in group_map:
					continue
				members = group_map[name]
				indices = [members[0]] if name == "Cash" else [m[0] for m in members]
				self._groups.append((indices, minimum))
				maxima.append(maximum)
		if not self._groups:
			return []

		G = np.zeros((len(self._groups), self._n))
		for row, (indices, _) in enumerate(self._groups):
			G[row, indices] = 1.0
		self._gmin = cp.Parameter(len(self._groups))
		return [G @ self._w >= self._gmin, G @ self._w <= np.asarray(maxima, dtype=float)]

	def _objective(self, rp: RebalanceProblem):
		"""Expected return - risk aversion * risk - concentration - transaction costs."""
		risk = cp.sum_squares(self._F.T @ self._w_risky) + cp.sum_squares(cp.multiply(self._d, self._w_risky))
		concentration = (getattr(rp, "concentration_strength", 0.0) or 0.0) * cp.sum_squares(self._w_risky)
		trading_cost = getattr(rp, "transaction_cost", 0.003) * cp.sum(self._buys + self._sells)
		return cp.Maximize(self._mu @ self._w_risky
						   - getattr(rp, "risk_aversion", 1.0) * risk
						   - concentration
						   - trading_cost)

	def _update(self, rebalance_context: RebalanceContext, signal: Signals, current_weights: pd.Series) -> None:
		"""Update per-date Parameter values for the optimization problem."""
		rp = rebalance_context.rebalance_problem
		self._tradable = tradable_mask(rebalance_context).to_numpy()
		self._update_expected_returns(signal)
		self._update_risk_model(signal)
		self._w0.value = current_weights.to_numpy(dtype=float)[self._risky_indices]
		self._update_position_bounds(rp)
		self._update_beta(signal)
		self._update_group_minimums()

	def _update_expected_returns(self, signal: Signals) -> None:
		"""Missing views (untradable / short history) get the cross-sectional median."""
		mu = np.asarray(signal.mean_returns(), dtype=float)
		finite = np.isfinite(mu)
		mu = np.where(finite, mu, float(np.median(mu[finite])) if finite.any() else 0.0)
		self._mu.value = mu[self._risky_indices]

	def _update_risk_model(self, signal: Signals) -> None:
		"""Update the risk model parameters (F and d) based on the signal's covariance matrix."""
		risky = self._risky_indices
		self._F.value, self._d.value = self._risk_model(signal.covariance_matrix()[np.ix_(risky, risky)], self._k)

	def _update_position_bounds(self, rp: RebalanceProblem) -> None:
		"""Update the position bounds (lower and upper) based on the rebalance problem and tradable mask."""
		lo, hi = getattr(rp, "min_position_size", None), getattr(rp, "max_position_size", None)
		self._lb.value = np.where(self._tradable, 0.0 if lo is None else lo, 0.0)
		self._ub.value = np.where(self._tradable, 1.0 if hi is None else hi, 0.0)

	def _update_beta(self, signal: Signals) -> None:
		"""Update the beta exposure parameter based on the signal's beta vector."""
		if self._beta is None:
			return
		beta = getattr(signal, "beta_vector", None)
		beta = np.zeros(self._n) if beta is None else np.asarray(beta, dtype=float)
		self._beta.value = np.nan_to_num(beta, nan=0.0, posinf=0.0, neginf=0.0)

	def _update_group_minimums(self) -> None:
		"""Update the group minimum constraints based on the tradable mask."""
		if self._gmin is None:
			return
		self._gmin.value = np.array([minimum if self._tradable[indices].any() else 0.0
									 for indices, minimum in self._groups], dtype=float)

	@staticmethod
	def _risk_model(cov: np.ndarray, k: int) -> tuple[np.ndarray, np.ndarray]:
		"""(F, d) with F F' + diag(d^2) ~= cov. Exact when k covers every asset; otherwise the top-k
		eigen-factors carry the correlations and d keeps each asset's variance exact."""
		cov = 0.5 * (cov + cov.T)
		n = cov.shape[0]
		if k >= n:
			try:
				return np.linalg.cholesky(cov), np.zeros(n)
			except np.linalg.LinAlgError:
				vals, vecs = np.linalg.eigh(cov)
				return vecs * np.sqrt(np.clip(vals, 0.0, None)), np.zeros(n)
		vals, vecs = np.linalg.eigh(cov)                      # ascending
		F = vecs[:, -k:] * np.sqrt(np.clip(vals[-k:], 0.0, None))
		residual = np.clip(np.diag(cov) - np.sum(F ** 2, axis=1), 0.0, None)
		return F, np.sqrt(residual)

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
