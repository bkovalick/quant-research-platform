import numpy as np
from models.signals_config import SignalsConfig
from simulation.market_state import MarketState
from sklearn.covariance import LedoitWolf
from domain.signals.signals import Signals

class RiskReturnSignals(Signals):
    def __init__(self, 
                 market_state: MarketState, 
                 signals_config: SignalsConfig):
        super().__init__(market_state, signals_config)

    def mean_returns(self) -> np.ndarray:
        """Annualized mean return; NaN for assets without a complete lookback window (they
        are untradable, and the optimizer fills them before use)."""
        lookback_returns = self.lookback_returns()
        complete = lookback_returns.notna().all()
        mu = lookback_returns.mean() * self.ann_factor
        return mu.where(complete).to_numpy(dtype=float)

    def covariance_matrix(self) -> np.ndarray:
        """Ledoit-Wolf covariance over assets with a complete lookback window, embedded in the
        full universe matrix. Incomplete assets get no covariance and a median variance on the
        diagonal: it keeps the matrix PSD and invertible (Black-Litterman inverts it), and those
        assets are held at zero weight anyway.

        Dropping incomplete *columns* rather than rows matters: one late listing would otherwise
        throw away most of the window for every asset."""
        lookback_returns = self.lookback_returns()
        n = lookback_returns.shape[1]
        complete = lookback_returns.notna().all().to_numpy()
        cov = np.zeros((n, n))
        idx = np.flatnonzero(complete)

        if len(idx) >= 2 and len(lookback_returns) >= 2:
            lw = LedoitWolf()
            lw.fit(lookback_returns.iloc[:, idx].to_numpy(dtype=float))
            cov[np.ix_(idx, idx)] = lw.covariance_ * self.ann_factor
        elif len(idx) == 1 and len(lookback_returns) >= 2:
            cov[idx[0], idx[0]] = lookback_returns.iloc[:, idx[0]].var() * self.ann_factor

        known_var = np.diag(cov)[idx]
        known_var = known_var[known_var > 0]
        fill_var = float(np.median(known_var)) if len(known_var) else 1e-4
        missing = np.flatnonzero(~complete)
        cov[missing, missing] = fill_var
        return 0.5 * (cov + cov.T)
    
    def portfolio_vol(self, curr_weights: np.ndarray) -> float:
        cov = self.covariance_matrix()
        return np.sqrt(curr_weights.T @ cov @ curr_weights)

    @property
    def sector_dict(self) -> dict:
        """Returns {ticker: sector_name} for the investment universe."""
        result = {}
        for sector, members in self.market_state.sector_map.items():
            if isinstance(members, list):
                for _, ticker in members:
                    result[ticker] = sector
            else:
                _, ticker = members
                result[ticker] = sector
        return result