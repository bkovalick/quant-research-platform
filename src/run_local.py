from application.experiment_runner import ExperimentRunner
from application.result_export import save_experiment_files, load_experiment_pickle
from reporting.report_generation import ExcelGenerator
from simulation.parameter_sweeps import ParameterSweeps
from utils.logging_config import setup_logging

import logging
import json
from io import BytesIO
from pathlib import Path
from datetime import datetime

setup_logging()
logger = logging.getLogger(__name__)

def create_folder_path(folder_name: str):
    path = Path(folder_name)
    path.mkdir(parents=True, exist_ok=True)

def local_run(config, excel: bool = True, max_workers: int | None = None):
    """Run an experiment, save the results to backtest_results/<date>/ straight away
    (experiment_<ts>.json opens in the UI's Lab; experiment_<ts>.pkl keeps everything),
    then optionally build the Excel report. A failing report can no longer lose the run."""
    logger.info("local_run:: Starting local run of experiment")
    config = config.copy()
    runner = ExperimentRunner(config, max_workers=max_workers)
    experiment_results = runner.run_parallel()
    # experiment_results = runner.run()

    folder_path = "backtest_results" + "/" + datetime.now().strftime('%Y-%m-%d')
    stamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
    json_path, pkl_path = save_experiment_files(experiment_results, folder_path, stamp)
    print("Results saved:")
    print(f"  UI file : {json_path.resolve()}  (open it from the Lab: Saved Results > open results file)")
    print(f"  full    : {pkl_path.resolve()}")

    if excel:
        try:
            write_excel_report(experiment_results, folder_path, stamp)
        except Exception:
            logger.exception("local_run:: Excel report failed; results are still in %s", pkl_path)

def write_excel_report(experiment, folder_path: str, stamp: str):
    buffer = BytesIO()
    ExcelGenerator(experiment, buffer).generate_report()
    create_folder_path(folder_path)
    with open(f"{folder_path}/backtest_report_{stamp}.xlsx", "wb") as f:
        f.write(buffer.getvalue())

def excel_report_from_pickle(pkl_path: str):
    """Rebuild the Excel report for a saved run without re-running the backtests."""
    path = Path(pkl_path)
    write_excel_report(load_experiment_pickle(path), str(path.parent), path.stem.replace("experiment_", ""))

def run_pairs_strategy():
    logger.info("run_pairs_strategy:: Starting local run of pairs trading strategy")
    with open(f"src/config/experiment_pairs_strategy_condensed.json", 'r') as f:
        config = json.load(f)
    local_run(config)

def run_ml_momentum_strategy():
    logger.info("run_momentum_strategy:: Starting local run of machine learning black-litterman/momentum view strategy")
    with open(f"src/config/experiment_securities_ml_bl_momentum_100.json", 'r') as f:
        config = json.load(f)
    local_run(config)

def run_ml_mean_reversion_strategy():
    logger.info("run_ml_mean_reversion_strategy:: Starting local run of machine learning black-litterman/mean reversion view strategy")
    with open(f"src/config/experiment_securities_ml_bl_mean_reversion.json", 'r') as f:
        config = json.load(f)
    local_run(config)

def run_standard_mean_variance_strategy():
    logger.info("run_standard_mean_variance_strategy:: Starting local run of standard mean-variance strategy")
    with open(f"src/config/experiment_securities_mean_variance_only.json", 'r') as f:
        config = json.load(f)
    local_run(config)

def run_full_suite():
    logger.info("run_full_suite:: Starting local run of full suite of strategies")
    with open(f"src/config/experiment_full_suite.json", 'r') as f:
        config = json.load(f)
    # 44 strategies: the Excel time-series sheet alone is ~135M cells, too much for this machine.
    # Skip it here; rebuild later with excel_report_from_pickle(<the .pkl path printed>) if needed.
    local_run(config, excel=False, max_workers=3)

def run_equal_weight_strategy():
    logger.info("run_equal_weight_strategy:: Starting local run of equal weight strategy")
    with open(f"src/config/experiment_equal_weight.json", 'r') as f:
        config = json.load(f)
    local_run(config)

def run_fixed_weight_strategy():
    logger.info("run_fixed_weight_strategy:: Starting local run of fixed weight strategy")
    with open(f"src/config/experiment_fwp.json", 'r') as f:
        config = json.load(f)
    local_run(config)

def run_securities_equal_weight_strategy():
    logger.info("run_securities_equal_weight_strategy:: Starting local run of equal/fixed weight securities baselines")
    with open(f"src/config/experiment_securities_equal_weight.json", 'r') as f:
        config = json.load(f)
    local_run(config)

def run_long_short_strategy():
    logger.info("run_long_short_strategy:: Starting local run of long/short decomposition strategy")
    with open(f"src/config/experiment_long_short.json", 'r') as f:
        config = json.load(f)
    local_run(config)

def run_ls_market_neutral_ml():
    logger.info("run_ls_market_neutral_ml:: Starting local run of long/short market neutral machine learning strategy")
    with open(f"src/config/experiment_ls_market_neutral_ml.json", 'r') as f:
        config = json.load(f)
    local_run(config)

def run_mean_reversion_strategy():
    logger.info("run_mean_reversion_strategy:: Starting local run of mean reversion strategy")
    with open(f"src/config/experiment_mean_reversion_moving_average.json", 'r') as f:
        config = json.load(f)
    local_run(config)

def run_inverse_volatility_strategy():
    logger.info("run_inverse_volatility_strategy:: Starting local run of inverse volatility strategy")
    with open(f"src/config/experiment_inverse_vol.json", 'r') as f:
        config = json.load(f)
    local_run(config)

def run_black_litterman_strategy():
    logger.info("run_black_litterman_strategy:: Starting local run of Black-Litterman strategy")
    with open(f"src/config/experiment_securities_bl_only_momentum.json", 'r') as f:
        config = json.load(f)
    local_run(config)

def run_parameter_sweep():
    with open(f"src/config/experiment_securities_ml_bl_momentum.json", 'r') as f:
        config = json.load(f)

    sweep = ParameterSweeps(config)
    sweep.run()

if __name__ == '__main__':
    # run_full_suite()
    # run_pairs_strategy()
    # run_ml_momentum_strategy()
    # run_ml_mean_reversion_strategy()
    # run_parameter_sweep()
    # run_standard_mean_variance_strategy()
    run_equal_weight_strategy()
    # run_fixed_weight_strategy()
    # run_long_short_strategy()
    # run_ls_market_neutral_ml()
    # run_mean_reversion_strategy()
    # run_inverse_volatility_strategy()
    # run_black_litterman_strategy()