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
        self._pairs_cache = pd.DataFrame(run.pairs_cache) if run.pairs_cache else pd.DataFrame()
        if not self._pairs_cache.empty:
            self._pairs_cache["FwdReturn"] = self._pairs_cache.groupby("Pair")["RealizedReturn"].shift(-1)

    def analyze(self) -> MonitoringStats:
        if self._pairs_cache.empty:
            return MonitoringStats()
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
    OLS regression of portfolio excess returns on Fama-French five factors plus momentum (FF5 + MOM).

    The Ken French factors are daily. Portfolio returns may be daily, weekly or
    monthly, so the daily factors are compounded over each portfolio period
    (previous return date, this return date] before regressing. Regressing a
    weekly return on a single day's factor return understates R^2 and the betas
    and misstates alpha.
    """
    FACTORS = ["Mkt-RF", "SMB", "HML", "RMW", "CMA", "Mom"]

    def __init__(self,
                 run: BacktestRun,
                 risk_free_rate: float = 0.03,
                 periods_per_year: int | None = None):
        self._run = run
        # Fallback only: the regression uses the Ken French RF series when it is available.
        self._risk_free_rate = risk_free_rate
        self._portfolio_returns = pd.Series(run.portfolio.returns) if run.portfolio is not None else None

        if self._portfolio_returns is None or self._portfolio_returns.empty:
            self._portfolio_returns = None
        self._periods_per_year = periods_per_year or self._infer_periods_per_year()

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
        """Runs FF5 + MOM on portfolio returns and factors compounded to the same periods."""
        returns = self._portfolio_returns.copy().replace([np.inf, -np.inf], np.nan).dropna()
        if isinstance(returns.index, pd.PeriodIndex):
            returns.index = returns.index.to_timestamp()
        returns.index = pd.to_datetime(returns.index)
        returns = returns.sort_index()

        daily_factors = self.add_momentum_factors(self._get_fama_french_five_factors)
        daily_factors = daily_factors.replace([np.inf, -np.inf], np.nan).dropna()
        factors = self.aggregate_factors_to_periods(daily_factors, returns.index)

        returns = returns.loc[factors.index]
        excess_returns = returns - factors["RF"]

        X = sm.add_constant(factors[self.FACTORS])
        self._n_obs = len(excess_returns)
        self._hac_lags = self._newey_west_lags(self._n_obs)
        return sm.OLS(excess_returns, X, missing="drop").fit(
            cov_type="HAC", cov_kwds={"maxlags": self._hac_lags}
        )

    def aggregate_factors_to_periods(self,
                                     daily_factors: pd.DataFrame,
                                     period_ends: pd.DatetimeIndex) -> pd.DataFrame:
        """
        Compound daily factor returns (Ken French percent units) over each portfolio
        period (previous period end, this period end]. Returns decimal returns indexed
        by period end. The first period (no known start) and any period not fully
        covered by the factor data are dropped.

        Mkt-RF is rebuilt as compounded market minus compounded RF, rather than
        compounding the daily excess return. For daily portfolios each period holds
        one factor day, so this reduces to the plain daily regression.
        """
        daily = daily_factors.sort_index() / 100.0
        rf_daily = daily["RF"] if "RF" in daily else pd.Series(
            self._risk_free_rate / 252, index=daily.index)
        daily = daily.assign(Mkt=daily["Mkt-RF"] + rf_daily, RF=rf_daily)

        period_ends = pd.DatetimeIndex(period_ends).sort_values()
        period_ends = period_ends[period_ends <= daily.index.max()]
        if len(period_ends) < 2:
            raise ValueError("Not enough overlap between portfolio returns and Fama-French factor data")

        # Label each factor day with the first period end on or after it. Position 0
        # means the day falls in the first period, whose start is unknown, so drop it.
        position = period_ends.searchsorted(daily.index, side="left")
        in_range = (position > 0) & (position < len(period_ends))
        daily = daily[in_range]
        labels = period_ends[position[in_range]]

        cols = ["Mkt", "RF", "SMB", "HML", "RMW", "CMA", "Mom"]
        compounded = (1.0 + daily[cols]).groupby(labels).prod() - 1.0
        compounded["Mkt-RF"] = compounded["Mkt"] - compounded["RF"]
        return compounded.drop(columns="Mkt")

    def add_momentum_factors(self, ff_factors: pd.DataFrame) -> pd.DataFrame:
        mom_factor = self._get_momentum_factor.copy().replace([np.inf, -np.inf], np.nan).dropna()
        if isinstance(mom_factor.index, pd.PeriodIndex):
            mom_factor.index = mom_factor.index.to_timestamp()
        mom_factor.columns = [str(c).strip() for c in mom_factor.columns]
        ff_factors = ff_factors.copy()
        ff_factors.index = pd.to_datetime(ff_factors.index)
        return ff_factors.join(mom_factor, how='inner')

    @property
    def _get_fama_french_five_factors(self) -> pd.DataFrame:
        # Start a month early so the first portfolio periods have factor days behind them.
        start_date = pd.Timestamp(self._portfolio_returns.index[0]) - pd.DateOffset(months=1)
        end_date = self._portfolio_returns.index[-1]
        ff_dataset = FamaFrenchReader('F-F_Research_Data_5_Factors_2x3_daily', start=start_date, end=end_date)
        if ff_dataset is None:
            raise ValueError("Fama-French dataset could not be retrieved. "
                             "Please check your internet connection or the availability of the dataset.")

        ff_factors = ff_dataset.read()[0]
        if isinstance(ff_factors.index, pd.PeriodIndex):
            ff_factors.index = ff_factors.index.to_timestamp()
        return ff_factors

    @property
    def _get_momentum_factor(self) -> pd.DataFrame:
        start_date = pd.Timestamp(self._portfolio_returns.index[0]) - pd.DateOffset(months=1)
        end_date = self._portfolio_returns.index[-1]
        df_daily = web.DataReader('F-F_Momentum_Factor_daily', 'famafrench', start=start_date, end=end_date)
        return df_daily[0]

    def _infer_periods_per_year(self) -> int:
        """Fallback when the caller doesn't pass periods_per_year: median spacing of the return dates."""
        if self._portfolio_returns is None or len(self._portfolio_returns) < 3:
            return 252
        spacing_days = pd.Series(pd.to_datetime(self._portfolio_returns.index)).diff().dt.days.median()
        if spacing_days <= 3:
            return 252
        if spacing_days <= 10:
            return 52
        if spacing_days <= 45:
            return 12
        return 4

    @staticmethod
    def _newey_west_lags(n_obs: int) -> int:
        """Newey-West (1994) rule of thumb: floor(4 * (n/100)^(2/9))."""
        return max(1, int(np.floor(4 * (n_obs / 100.0) ** (2.0 / 9.0))))

    def _format_factor_regression(self, result) -> dict:
        parameter_names = result.model.exog_names
        parameters = dict(zip(parameter_names, result.params))
        t_statistics = dict(zip(parameter_names, result.tvalues))
        p_values = dict(zip(parameter_names, result.pvalues))
        alpha = float(parameters["const"])

        return {
            "model": "FF5 + MOM",
            "cov_type": f"HAC (Newey-West, {self._hac_lags} lags)",
            "periods_per_year": self._periods_per_year,
            "n_obs": self._n_obs,
            "r_squared": float(result.rsquared),
            "alpha": {
                "coef": alpha,                                   # per portfolio period, decimal
                "annualized": alpha * self._periods_per_year,
                "t_stat": float(t_statistics["const"]),
                "p_value": float(p_values["const"]),
            },
            "factors": [
                {
                    "name": factor_name,
                    "beta": float(parameters[factor_name]),
                    "t_stat": float(t_statistics[factor_name]),
                    "p_value": float(p_values[factor_name]),
                }
                for factor_name in parameter_names
                if factor_name != "const"
            ],
        }
