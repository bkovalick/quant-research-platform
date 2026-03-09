from domain.signals.risk_return_signals import RiskReturnSignals
from models.signals_config import SignalsConfig
from simulation.market_state import MarketState
import numpy as np

class BlackLittermanSignal(RiskReturnSignals):
    def __init__(self, 
                 market_state: MarketState, 
                 signals_cfg: SignalsConfig, 
                 current_weights: np.ndarray):
        super().__init__(market_state, signals_cfg)
        self.current_weights = current_weights

    def mean_returns(self):
        black_litterman = getattr(self.signals_cfg, "black_litterman", None)
        if black_litterman is None:
            return super().mean_returns()

        sigma = self.covariance_matrix()
        pi = self._compute_equilibrium_returns(sigma)
        P, Q, omega = self._build_views(sigma)
        return self._compute_posterior(pi, sigma, P, Q, omega)
    
    def _compute_equilibrium_returns(self, sigma):
        delta = getattr(self.signals_cfg, "risk_aversion", 2.5)
        return delta * sigma @ self.current_weights

    def _build_views(self, sigma):
        # get your reversion signal
        mean_reversion_window = getattr(self.signals_cfg, "mean_reversion_window", 4)
        lookback_prices = self.market_state.lookback_prices()
        short_returns = lookback_prices.pct_change(mean_reversion_window).iloc[-1]
        
        # rank assets — bottom quintile are losers, top quintile are winners
        n = len(short_returns)
        quintile = n // 5
        ranked = short_returns.rank()
        
        losers  = ranked <= quintile        # bottom 20%
        winners = ranked >= n - quintile    # top 20%
        
        # build P — one relative view
        P = np.zeros((1, n))
        P[0, losers]  = 1 / losers.sum()   # long losers equally
        P[0, winners] = -1 / winners.sum() # short winners equally
        
        # Q — expected spread between losers and winners
        expected_spread = getattr(self.signals_cfg, "reversion_view", 0.03)
        Q = np.array([expected_spread])
        
        # omega — confidence tied to asset variance (Black-Litterman standard)
        tau = getattr(self.signals_cfg, "tau", 0.05)
        omega = np.diag(np.diag(tau * P @ sigma @ P.T))
        
        return P, Q, omega

    def _compute_posterior(self, pi, sigma, P, Q, omega):
        tau = getattr(self.signals_cfg, "tau", 0.05)
        M = np.linalg.inv(
            np.linalg.inv(tau * sigma) + P.T @ np.linalg.inv(omega) @ P
        )
        return M @ (np.linalg.inv(tau * sigma) @ pi + P.T @ np.linalg.inv(omega) @ Q)
