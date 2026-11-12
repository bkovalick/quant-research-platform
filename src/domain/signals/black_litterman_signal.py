from typing import Optional
import numpy as np
import pandas as pd

from domain.signals.risk_return_signals import RiskReturnSignals
from domain.signals.machine_learning_signals import MLPredictorSignalsState
from models.signals_config import SignalsConfig
from simulation.market_state import MarketState

class BlackLittermanSignal(RiskReturnSignals):
    def __init__(self, 
                 market_state: MarketState, 
                 signals_config: SignalsConfig,
                 ml_state: Optional[MLPredictorSignalsState]):
        super().__init__(market_state, signals_config)
        self.ml_state = ml_state
        self.ml_signals_config = self.signals_config.ml_signals_config
        self.investment_universe = self.market_state.investment_universe
        self.equilibrium_weights = self._build_equilibrium_weights()       
        bl = self.signals_config.black_litterman or {}
        self.black_litterman = bl if bl else None
        self.view_uncertainty = bl.get("view_uncertainty", 1.0)
        if self.black_litterman is not None and not self.view_uncertainty > 0:
            raise ValueError(f"black_litterman.view_uncertainty must be > 0, got {self.view_uncertainty!r}")
        self.delta = bl.get("delta", 2.5)
        self.view_direction = bl.get("view_direction", "momentum")

    def mean_returns(self) -> np.ndarray:
        """ Returns the Black-Litterman posterior mean return vector. """
        if self.black_litterman is None:
            return super().mean_returns()
        
        sigma = self.covariance_matrix()
        pi = self._compute_equilibrium_returns(sigma)
        P, Q, omega = self._build_views(sigma)
        if not np.any(P):
            return pi
        return self._compute_posterior(pi, sigma, P, Q, omega)
    
    def _build_equilibrium_weights(self) -> np.ndarray:
        """ Constructs the equilibrium weights vector """
        n = len(self.investment_universe)
        return np.ones(n) / n
    
    def _compute_equilibrium_returns(self, sigma: np.ndarray) -> np.ndarray:
        """ Computes the CAPM-implied equilibrium excess returns (pi) using reverse optimization: pi = delta * Sigma * w """
        return self.delta * sigma @ self.equilibrium_weights

    def _build_views(self, sigma: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """ Constructs the investor view matrices (P, Q, Omega) using the ranked scores. """
        ranked, expected_spread = self._get_ranked_scores()
        n = int(ranked.notna().sum())
        quintile = n // 5
        losers  = ranked <= quintile
        losers.reindex(self.investment_universe, fill_value=False).to_numpy()
        winners = ranked > n - quintile
        winners.reindex(self.investment_universe, fill_value=False).to_numpy()

        if winners.sum() == 0 or losers.sum() == 0:
            n_investment = len(self.investment_universe)
            return np.zeros((1, n_investment)), np.array([0.0]), np.eye(1)
        
        P = self._determine_view_direction(winners, losers)
        Q = np.array([expected_spread])
        prior_view_variance = np.diag(P @ sigma @ P.T)
        view_variance = self.view_uncertainty * prior_view_variance
        omega = np.diag(np.maximum(view_variance, 1e-8))
        return P, Q, omega

    def _compute_posterior(self, 
                           equilibrium_ret: np.ndarray, 
                           sigma: np.ndarray, 
                           P: np.ndarray, 
                           Q: np.ndarray, 
                           omega: np.ndarray) -> np.ndarray:
        """ Computes the Black-Litterman posterior mean given equilibrium returns and views. 
            Q = the vector of expected view returns
            P = the pick matrix encoding the views (which assets are involved in each view)
            sigma = the prior covariance of asset returns
            omega = the covariance matrix of the views (uncertainty in the views)
            asset_view_cov = the covariance between assets and views
            view_total_cov = the total covariance of the views (prior + view uncertainty)
            view_surprise = the difference between the expected view returns and the prior-implied returns
        """                            
        asset_view_cov = sigma @ P.T                  # N x k: each asset vs each view, covariance between assets and views
        view_total_cov = P @ asset_view_cov + omega   # k x k: prior + view uncertainty, total covariance of the views
        view_surprise = Q - P @ equilibrium_ret       # k: view minus what the prior implies
        return equilibrium_ret + asset_view_cov @ np.linalg.solve(view_total_cov, view_surprise) # posterior mean of asset returns given the views

    def _get_ranked_scores(self):
        """ Returns ranked scores used to construct the view matrix P. """
        if self.use_ml:
            scores = self.ml_state.scores.reindex(self.investment_universe)
            return scores.rank(), self.black_litterman.get("ml_view_spread", 0.03)

        window = self.signals_config.mean_reversion_window
        short_returns = self.market_state.lookback_prices().pct_change(window, fill_method=None).iloc[-1]
        return short_returns.rank(), self.black_litterman.get("reversion_view", 0.03)
    
    def _determine_view_direction(self, 
                                  winners: np.ndarray, 
                                  losers: np.ndarray) -> np.ndarray:
        """ Builds the (1 x N) pick matrix P encoding a single long/short relative view based on the configured view_direction. """
        sign = 1 if self.view_direction == "momentum" else -1
        P = np.zeros((1, len(self.investment_universe)))
        if winners.sum() == 0 or losers.sum() == 0:
            return P

        P[0, winners] = sign / winners.sum()
        P[0, losers] = -sign / losers.sum()
        return P

    @property
    def use_ml(self) -> bool:
        return (self.ml_signals_config is not None
                and self.ml_signals_config.enabled
                and self.ml_state is not None
                and self.ml_state.scores is not None)