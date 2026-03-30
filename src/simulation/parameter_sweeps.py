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

def create_folder_path(folder_name: str):
    path = Path(folder_name)
    path.mkdir(parents=True, exist_ok=True)

class ParameterSweeps:
    def __init__(self, base_config):
        self.master_config = {}
        self.base_config = base_config 
        self.fwp_config_file = "src/config/experiment_fwp.json"
        self.equal_config = "src/config/experiment_equal_weight.json"
        self.unique_market_tickers = [] # need to store all possible tickers in market store.

    def run(self):
        config = self._build_parameter_sweeps()
        runner = ExperimentRunner(config)
        experiment_results = runner.run_parallel()
        buffer = BytesIO()
        reporting_module = ExcelGenerator(experiment_results, buffer)
        reporting_module.generate_report()
        folder_path = "backtest_results" + "/" + datetime.now().strftime('%Y-%m-%d')
        create_folder_path(folder_path)
        with open(folder_path + "/backtest_report_" + datetime.now().strftime("%Y%m%d%H%M%S%f") + ".xlsx", "wb") as f:
            f.write(buffer.getvalue())        

    def _build_parameter_sweeps(self) -> dict:
        self._add_fwp_config()
        self._add_ewp_config()
        return self.master_config.copy()

    def _add_fwp_config(self):
        with open(self.fwp_config_file, 'r') as f:
            config = json.load(f)
        self.master_config["fixed_weight_portfolio"] = config.copy()

    def _add_ewp_config(self):
        with open(self.equal_config, 'r') as f:
            config = json.load(f)
        self.master_config["equal_weight_portfolio"] = config.copy()