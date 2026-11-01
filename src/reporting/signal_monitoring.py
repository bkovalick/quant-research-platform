import abc
import pandas as pd
import numpy as np
from scipy.stats import spearmanr
from scipy import stats
import statsmodels.api as sm
from pandas_datareader.famafrench import FamaFrenchReader
from pandas_datareader import data as web

from models.monitoring_stats import MonitoringStats
from models.backtest_run import BacktestRun

class BaseDiagnostic(abc.ABC):
    @abc.abstractmethod
    def analyze(self) -> MonitoringStats: ...

class PairsSpreadDiagnostics(BaseDiagnostic):
    """Monitors signal decay by computing rolling Information Coefficient and half-life of those signals."""
    def __init__(self, 
                 run: BacktestRun):
        self._run = run
        self._pairs_cache = pd.DataFrame(run.pairs_cache) if run.pairs_cache is not None else None
        if self._pairs_cache is None or self._pairs_cache.empty:
            raise ValueError("Pairs cache is empty or None. Cannot compute diagnostics.")
        self._pairs_cache["FwdReturn"] = self._pairs_cache.groupby("Pair")["RealizedReturn"].shift(-1)

    def analyze(self) -> MonitoringStats:
        ic_sp_series = self._compute_ic_statistics()
        return MonitoringStats(
            ic_statistics={"spearman": ic_sp_series.to_dict()},
            ic_summary= {"mean_ic": float(ic_sp_series.mean())}
        )

    def _compute_ic_statistics(self) -> pd.Series:
        """
        Computes the Spearman rank correlation (IC) between the signal and 
        forward returns for each date, then applies a rolling mean to smooth the series.
        """
        clean = (
            self._pairs_cache[["Zscore", "FwdReturn"]]
            .replace([np.inf, -np.inf], np.nan)
            .dropna()
        )
        ic_sp, pval = spearmanr(-clean["Zscore"], clean["FwdReturn"])
        return pd.Series([ic_sp], dtype=float)
    
class LongOnlyICDiagnostics(BaseDiagnostic):
    """Monitors signal decay by computing rolling Information Coefficient and half-life of those signals."""
    def __init__(self, 
                 run: BacktestRun):
        self._run = run
        self._scores = pd.DataFrame(run.scores_history).T if run.scores_history is not None else None
        self._forward_data = pd.DataFrame(run.fwd_history).T if run.fwd_history is not None else None

        if self._scores is None or self._scores.empty:
            self._scores = None
        
        if self._forward_data is None or self._forward_data.empty:
            self._forward_data = None
        
    def analyze(self) -> MonitoringStats:
        has_ic_data = self._scores is not None and self._forward_data is not None
        ic_sp_series = self._compute_ic_statistics() if has_ic_data else None
        return MonitoringStats(
            ic_statistics={"spearman": ic_sp_series.to_dict()} if ic_sp_series is not None else None,
            ic_summary=self._compute_ic_summary(ic_sp_series) if ic_sp_series is not None else None
        )

    def _compute_ic_statistics(self) -> pd.Series:
        """
        Computes the Spearman rank correlation (IC) between the signal and 
        forward returns for each date, then applies a rolling mean to smooth the series.
        """
        ic_sp_values = []
        for date in self._scores.index:
            if date not in self._forward_data.index:
                continue
            
            scores = self._scores.loc[date].dropna()
            fwd_data = self._forward_data.loc[date].dropna()
            common = scores.index.intersection(fwd_data.index)
            if len(common) < 5:
                continue

            ic_sp, _ = spearmanr(scores.loc[common], fwd_data.loc[common])
            ic_sp_values.append((date, float(ic_sp)))

        if not ic_sp_values:
            return pd.Series(dtype=float)

        dates, ics_spear = zip(*ic_sp_values)
        return pd.Series(ics_spear, index=dates)
    
    def _compute_ic_summary(self, ic_series: pd.Series) -> dict:
        """
        Perform a one-sample t-test to determine if the mean IC is significantly different from zero.
        Returns the t-statistic and p-value.
        """
        if len(ic_series.dropna()) < 2:
            return {"t_statistic": np.nan, "p_value": np.nan}
        t_stat, p_value = stats.ttest_1samp(ic_series.dropna(), 0)
        ic_std = ic_series.std()
        ic_ir = ic_series.mean() / ic_std if ic_std > 0 else np.nan
        return {
            "mean_ic": ic_series.mean(),
            "ic_ir": ic_ir,
            "hit_rate": float((ic_series > 0).mean()),
            "t_statistic": t_stat, 
            "p_value": p_value,
            "half_life": self._compute_half_life(ic_series),
            "n_observations": len(ic_series.dropna()),
        }
    
    def _compute_half_life(self, ic_series: pd.Series) -> float:
        """
        Estimate the signal decay half-life from signals using AR(1) autocorrelation.
        """
        phi = ic_series.autocorr(lag=1)

        if phi <= 0 or phi >= 1:
            return np.nan

        half_life = np.log(0.5) / np.log(phi)
        return half_life

class FactorRegressionDiagnostics(BaseDiagnostic):
    """
    Performs OLS regression of portfolio excess returns against Fama-French five factors plus momentum (FF5 + MOM).
    """
    def __init__(self, 
                 run: BacktestRun,
                 risk_free_rate: float = 0.03):
        self._run = run
        self._risk_free_rate = risk_free_rate
        self._portfolio_returns = pd.Series(run.portfolio.returns) if run.portfolio is not None else None

        if self._portfolio_returns is None or self._portfolio_returns.empty:
            self._portfolio_returns = None
        
    def analyze(self) -> MonitoringStats:
        has_port_data = self._portfolio_returns is not None
        if not has_port_data:
            return MonitoringStats(
                regression_summary=None
            )
        result = self._ols_fama_french_factor_regression()
        return MonitoringStats(
            regression_summary=self._format_factor_regression(result)
        )

    def _ols_fama_french_factor_regression(self):
        """Runs a simple FF5 + MOM regression on aligned, frequency-safe data."""
        returns = self._portfolio_returns.copy().replace([np.inf, -np.inf], np.nan).dropna()
        ff_factors = self._get_fama_french_five_factors.copy().replace([np.inf, -np.inf], np.nan).dropna()

        if isinstance(returns.index, pd.PeriodIndex):
            returns.index = returns.index.to_timestamp()
        if isinstance(ff_factors.index, pd.PeriodIndex):
            ff_factors.index = ff_factors.index.to_timestamp()

        ff_factors = self.add_momentum_factors(ff_factors)

        returns = returns[returns.index.isin(ff_factors.index)]
        ff_factors = ff_factors.loc[returns.index]

        rf_per_period = self._risk_free_rate / self._periods_per_year
        regression_data = pd.concat({
            "Returns": returns,
            "RiskFree": pd.Series(rf_per_period, index=returns.index),
            **{col: ff_factors[col] for col in ff_factors.columns},
        }, axis=1)
        regression_data["Asset_Excess_Return"] = regression_data["Returns"] - regression_data["RiskFree"]

        X = regression_data[["Mkt-RF", "SMB", "HML", "RMW", "CMA", "Mom"]]
        X = sm.add_constant(X)
        y = regression_data["Asset_Excess_Return"]

        model = sm.OLS(y, X, missing="drop").fit(cov_type="HAC", cov_kwds={"maxlags": 7})
        return model

    def add_momentum_factors(self, ff_factors: pd.DataFrame) -> pd.DataFrame:
        mom_factor = self._get_momentum_factor.copy().replace([np.inf, -np.inf], np.nan).dropna()
        if isinstance(mom_factor.index, pd.PeriodIndex):
            mom_factor.index = mom_factor.index.to_timestamp()
        ff_factors = ff_factors.copy()
        ff_factors.index = pd.to_datetime(ff_factors.index)
        factors = ff_factors.join(mom_factor, how='inner')
        return factors

    @property
    def _get_fama_french_five_factors(self) -> pd.DataFrame:
        start_date = self._portfolio_returns.index[0]
        end_date = self._portfolio_returns.index[-1]
        ff_dataset = FamaFrenchReader('F-F_Research_Data_5_Factors_2x3_daily', start=start_date, end=end_date)
        if ff_dataset is None:
            raise ValueError("Fama-French dataset could not be retrieved. \
                             Please check your internet connection or the availability of the dataset.")

        ff_factors = ff_dataset.read()[0]
        ff_factors.index = ff_factors.index.to_timestamp()
        return ff_factors
    
    @property
    def _get_momentum_factor(self) -> pd.DataFrame:
        start_date = self._portfolio_returns.index[0]
        end_date = self._portfolio_returns.index[-1]
        df_daily = web.DataReader('F-F_Momentum_Factor_daily', 'famafrench', start=start_date, end=end_date)
        return df_daily[0]

    @property
    def _periods_per_year(self) -> int:
        freq = getattr(self._portfolio_returns.index, "inferred_freq", None)
        if freq is None:
            return 252
        if freq.startswith("M") or freq.startswith("Q"):
            return 12
        if freq.startswith("W"):
            return 52
        return 252

    def _format_factor_regression(self, result) -> dict:
        parameter_names = result.model.exog_names
        parameters = dict(zip(parameter_names, result.params))
        t_statistics = dict(zip(parameter_names, result.tvalues))
        p_values = dict(zip(parameter_names, result.pvalues))

        return {
            "model": "FF5 + MOM",
            "cov_type": "HAC (Newey-West, 7 lags)",
            "r_squared": float(result.rsquared),
            "alpha": {
                "coef": float(parameters["const"]) * 100,
                "t_stat": float(t_statistics["const"]),
                "p_value": float(p_values["const"]),
            },
            "factors": [
                {
                    "name": factor_name,
                    "beta": float(parameters[factor_name]) * 100,
                    "t_stat": float(t_statistics[factor_name]),
                    "p_value": float(p_values[factor_name]),
                }
                for factor_name in parameter_names
                if factor_name != "const"
            ],
        }