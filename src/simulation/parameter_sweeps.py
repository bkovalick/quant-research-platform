"""
We need to define what parameters we want to do sweeps on.
    1. Rebalance Frequency (rebalance_frequency): daily/weekly/quarterly/yearly
    2. Black Litterman Config
        a. tau
        b. delta
        c. reversion_view
        d. ml_view_spread
        e. view_direction: [momentum/mean_reversion]
    3. strategy_rules -> Right now this is only volatility based, not sure what happens with this.
    4. Optimizer Constraints
        a. Max Position (35%)
        b. Concentration Strength
        c. Max Return -> This might be turned off
        d. Risk Aversion
        e. Turnover (turnover_limit) 
        f. Volatility (optimizer_vol_constraint)
    5. signal_source -> black_litterman/risk_return/machine_learning/vol_forecasting/momentum
    6. Lookback Window (1y) -> How much time do we allow to pass before we start rebalancing (Similar to a warm up for all of our signals).


Build a class that's entire purpose is to build custom configuration files or one massive config file that gets fed to the experiment runner.

"""

from application.experiment_runner import ExperimentRunner
from reporting.report_generation import ExcelGenerator

import json
from io import BytesIO
from pathlib import Path
from datetime import datetime
from itertools import product
import copy

def create_folder_path(folder_name: str):
    path = Path(folder_name)
    path.mkdir(parents=True, exist_ok=True)

"""
Perhaps we have a json parameter sweep file

"""
class ParameterSweeps:
    
    def __init__(self, base_config):
        self.base_config = base_config 
        self.fwp_config_file = "src/config/experiment_fwp.json"
        self.equal_config = "src/config/experiment_equal_weight.json"
        self.unique_market_tickers = []

    def run(self):
        """
        Builds a master configuration dict that includes all parameter sweeps, 
        then feeds it to the experiment runner.
        """
        param_sweep_config = self._build_parameter_sweeps()
        runner = ExperimentRunner(param_sweep_config)
        experiment_results = runner.run_parallel()
        buffer = BytesIO()
        reporting_module = ExcelGenerator(experiment_results, buffer)
        reporting_module.generate_report()
        folder_path = "backtest_results" + "/" + datetime.now().strftime('%Y-%m-%d')
        create_folder_path(folder_path)
        with open(folder_path + "/backtest_report_" + datetime.now().strftime("%Y%m%d%H%M%S%f") + ".xlsx", "wb") as f:
            f.write(buffer.getvalue())        

    def _build_parameter_sweeps(self) -> dict:
        """
        Builds a master config with one market_store_config and a flat list
        of strategy variants (baselines + frequency sweep).
        """
        # Baselines
        strategies = []
        strategies.extend(self._load_baseline_strategies())

        # Frequency sweep over base config strategies
        for strategy in self.base_config.get("strategies", []):
            self._ml_features_sweep(strategies, copy.deepcopy(strategy))
            # for freq in self._rebalance_frequency_sweep():
            #     variant = copy.deepcopy(strategy)
            #     variant["name"] = f"{strategy['name']}_{freq}"
            #     variant["rebalance_problem"]["rebalance_frequency"] = freq
            #     strategies.append(variant)

        # Merge all unique tickers into one market_store_config
        base_tickers = self.base_config["market_store_config"]["tickers"]
        all_tickers = list(set(base_tickers) | set(self.unique_market_tickers))

        return {
            "market_store_config": {
                **self.base_config["market_store_config"],
                "tickers": all_tickers
            },
            "strategies": strategies
        }

    def _load_baseline_strategies(self) -> list:
        """Load FWP and EWP baseline strategies, collecting their tickers."""
        strategies = []
        for config_file in [self.fwp_config_file, self.equal_config]:
            with open(config_file, 'r') as f:
                config = json.load(f)
            tickers = config.get("market_store_config", {}).get("tickers", [])
            self.unique_market_tickers = list(set(tickers) | set(self.unique_market_tickers))
            strategies.extend(config.get("strategies", []))
        return strategies

    def _rebalance_frequency_sweep(self):
        """Sweep over different rebalance frequencies for the same strategy configuration."""
        return ["daily", "weekly", "quarterly", "yearly"]

    def _black_litterman_sweeps(self, variant):
        if "black_litterman" not in variant:
            return
        
        risk_aversion_view_sweeps = [0.03]
        tau_sweeps = [0.01, 0.05, 0.10]
        ml_view_spread_sweeps = [0.01, 0.03, 0.05, 0.10]
        variant["black_litterman"]["tau"] = 0.01

    def _ml_features_sweep(self, strategy: dict) -> list:
        """Generates leave-one-out feature variants for the ML predictor signal."""
        features = (strategy
                     .get("signals_config", {})
                     .get("ml_signals_config", {})
                     .get("features"))
        if not features:
            return []

        variants = []
        for feat in features:
            variant = copy.deepcopy(strategy)
            remaining = [f for f in features if f != feat]
            variant["name"] = f"{strategy['name']}_remove_{feat}"
            variant["signals_config"]["ml_signals_config"]["features"] = remaining
            variants.append(variant)
        return variants

if __name__ == '__main__':
    with open(f"src/config/src/config/experiment_securities_ml_bl_momentum_full_universe.json", 'r') as f:
        config = json.load(f)

    config = config.copy()    
    param_sweeps = ParameterSweeps(config)
    param_sweeps.run()