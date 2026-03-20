from domain.signals.risk_return_signals import RiskReturnSignals
from domain.signals.ml_signals import MLSignalsState
from models.signals_config import SignalsConfig
from simulation.market_state import MarketState

import numpy as np
import pandas as pd

class BlackLittermanSignal(RiskReturnSignals):
    def __init__(self, 
                 market_state: MarketState, 
                 signals_config: SignalsConfig,
                 ml_state: MLSignalsState,
                 current_weights: np.ndarray):
        super().__init__(market_state, signals_config)

        self.ml_state = ml_state
        self.ml_signals_config = self.signals_config.ml_signals_config
        self.black_litterman = getattr(self.signals_config, "black_litterman", None)
        self.current_weights = current_weights

    def mean_returns(self) -> np.ndarray:
        """
        Returns the Black-Litterman posterior mean return vector. If no
        black_litterman config is present, falls back to the parent class
        historical mean returns.
        """
        if self.black_litterman is None:
            return super().mean_returns()

        sigma = self.covariance_matrix()
        pi = self._compute_equilibrium_returns(sigma)
        P, Q, omega = self._build_views(sigma)
        if not np.any(P):
            return pi  # no valid view (too few assets); fall back to equilibrium returns
        return self._compute_posterior(pi, sigma, P, Q, omega)
    
    def _compute_equilibrium_returns(self, sigma):
        """
        Computes the CAPM-implied equilibrium excess returns (pi) using reverse
        optimization: pi = delta * Sigma * w, where delta is the risk aversion
        coefficient and w is the current portfolio weight vector.
        """
        delta = self.black_litterman.get("delta", 2.5)
        return delta * sigma @ self.current_weights

    def _build_views(self, sigma):
        """
        Constructs the investor view matrices (P, Q, Omega) using a mean-reversion
        signal. Assets in the bottom quintile by recent returns are expected to
        outperform assets in the top quintile (losers beat winners). Returns:
          P     — (1 x N) pick matrix encoding the relative view.
          Q     — (1,) array of the expected return spread.
          Omega — (1 x 1) diagonal uncertainty matrix scaled by tau * P @ Sigma @ P'.
        """        
        ranked, expected_spread = self._get_ranked_scores()

        n = len(ranked)
        quintile = n // 5

        losers  = ranked <= quintile        # bottom 20%
        winners = ranked >= n - quintile    # top 20%

        P = self._determine_view_direction(n, winners, losers)

        Q = np.array([expected_spread])
        
        tau = self.black_litterman.get("tau", 0.05)
        omega = np.diag(np.diag(tau * P @ sigma @ P.T))
        
        return P, Q, omega

    def _compute_posterior(self, pi, sigma, P, Q, omega) -> np.ndarray:
        """
        Combines the equilibrium returns (pi) with the investor views (P, Q, Omega)
        using the Black-Litterman formula to produce a blended posterior mean vector:
          mu_BL = M @ (inv(tau*Sigma) @ pi + P' @ inv(Omega) @ Q)
        where M = inv(inv(tau*Sigma) + P' @ inv(Omega) @ P).
        """
        tau = self.black_litterman.get("tau", 0.05)
        M = np.linalg.inv(
            np.linalg.inv(tau * sigma) + P.T @ np.linalg.inv(omega) @ P
        )
        return M @ (np.linalg.inv(tau * sigma) @ pi + P.T @ np.linalg.inv(omega) @ Q)
    
    def _get_ranked_scores(self):
        """
        Returns (ranked, expected_spread) used to construct the view matrix P.
        If ML scores are available and enabled, assets are ranked by model score
        and the ml_view_spread config value is used as the expected return spread.
        Otherwise falls back to ranking by short-term price returns over
        mean_reversion_window periods, using reversion_view as the spread.
        """
        bl = self.black_litterman
        use_ml = (
            self.ml_signals_config is not None
            and self.ml_signals_config.enabled
            and self.ml_state is not None
            and self.ml_state.scores is not None
        )
        if use_ml:
            return self.ml_state.scores.rank(), bl.get("ml_view_spread", 0.03)

        window = getattr(self.signals_config, "mean_reversion_window", 4)
        short_returns = self.market_state.lookback_prices().pct_change(window).iloc[-1]
        return short_returns.rank(), bl.get("reversion_view", 0.03)
    
    def _determine_view_direction(self, n: int, winners, losers):
        """
        Builds the (1 x N) pick matrix P encoding a single long/short relative
        view based on the configured view_direction:
          "momentum"       — long winners, short losers (trend-following).
          "mean_reversion" — long losers, short winners (contrarian).
        Each leg is equally weighted and normalised so the row sums to zero.
        Defaults to mean_reversion if view_direction is unrecognised.
        """
        P = np.zeros((1, n))

        if winners.sum() == 0 or losers.sum() == 0:
            return P  # too few assets to form a valid view; express no view

        view_direction = self.black_litterman.get("view_direction", "momentum")
        if view_direction == "momentum":
            P[0, winners] =  1 / winners.sum()  # long winners equally
            P[0, losers]  = -1 / losers.sum()   # short losers equally
        else:  # "mean_reversion" or unrecognised
            P[0, losers]  =  1 / losers.sum()   # long losers equally
            P[0, winners] = -1 / winners.sum()  # short winners equally

        return P
