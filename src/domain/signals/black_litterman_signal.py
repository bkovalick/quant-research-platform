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
        self.ml_signals_config = self.signals_cfg.ml_signals_config
        self.current_weights = current_weights

    def mean_returns(self) -> np.ndarray:
        """
        Returns the Black-Litterman posterior mean return vector. If no
        black_litterman config is present, falls back to the parent class
        historical mean returns.
        """
        black_litterman = getattr(self.signals_cfg, "black_litterman", None)
        if black_litterman is None:
            return super().mean_returns()

        sigma = self.covariance_matrix()
        pi = self._compute_equilibrium_returns(sigma)
        P, Q, omega = self._build_views(sigma)
        return self._compute_posterior(pi, sigma, P, Q, omega)
    
    def _compute_equilibrium_returns(self, sigma):
        """
        Computes the CAPM-implied equilibrium excess returns (pi) using reverse
        optimization: pi = delta * Sigma * w, where delta is the risk aversion
        coefficient and w is the current portfolio weight vector.
        """
        delta = getattr(self.signals_cfg, "risk_aversion", 2.5)
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
        if self.ml_signals_config is not None and self.ml_signals_config.enabled \
            and self.ml_state is not None and self.ml_state.scores is not None:
            ml_scores = self.ml_state.scores
            tickers = self.market_state.lookback_prices().columns
            ranked = pd.Series(ml_scores, index=tickers).rank()
            expected_spread = self.signals_cfg.black_litterman.get("ml_view_spread", 0.03)
        else:
            mean_reversion_window = getattr(self.signals_cfg, "mean_reversion_window", 4)
            lookback_prices = self.market_state.lookback_prices()
            short_returns = lookback_prices.pct_change(mean_reversion_window).iloc[-1]        
            ranked = short_returns.rank()
            expected_spread = self.signals_cfg.black_litterman.get("reversion_view", 0.03)
        
        n = len(ranked)
        quintile = n // 5

        losers  = ranked <= quintile        # bottom 20%
        winners = ranked >= n - quintile    # top 20%
        
        # build P — one relative view
        P = np.zeros((1, n))

        view_direction = self.signals_cfg.black_litterman.get("view_direction", "momentum")
        if view_direction == "momentum":
            P[0, winners] = 1 / winners.sum() # long winners equally
            P[0, losers]  = -1 / losers.sum()   # short losers equally
        elif view_direction == "mean_reversion":
            P[0, losers]  = 1 / losers.sum()   # long losers equally
            P[0, winners] = -1 / winners.sum() # short winners equally
        
        Q = np.array([expected_spread])
        
        tau = self.signals_cfg.black_litterman.get("tau", 0.05)
        omega = np.diag(np.diag(tau * P @ sigma @ P.T))
        
        return P, Q, omega

    def _compute_posterior(self, pi, sigma, P, Q, omega) -> np.ndarray:
        """
        Combines the equilibrium returns (pi) with the investor views (P, Q, Omega)
        using the Black-Litterman formula to produce a blended posterior mean vector:
          mu_BL = M @ (inv(tau*Sigma) @ pi + P' @ inv(Omega) @ Q)
        where M = inv(inv(tau*Sigma) + P' @ inv(Omega) @ P).
        """
        tau = self.signals_cfg.black_litterman.get("tau", 0.05)
        M = np.linalg.inv(
            np.linalg.inv(tau * sigma) + P.T @ np.linalg.inv(omega) @ P
        )
        return M @ (np.linalg.inv(tau * sigma) @ pi + P.T @ np.linalg.inv(omega) @ Q)
