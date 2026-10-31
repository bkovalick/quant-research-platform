from application.experiment_runner import ExperimentRunner
from reporting.report_generation import ExcelGenerator
from models.experiment import Experiment
from models.backtest_result import BacktestResult
from models.strategy_run import StrategyRun
from models.experiment_model import ExperimentModel
from infrastructure.strategy_results_data_gateway import ExperimentMetaDataDataGateway

from datetime import datetime
from fastapi import FastAPI, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi import Response
from io import BytesIO
import logging
from utils.logging_config import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

@app.post("/run-experiment")
def run_experiment(config: dict = Body(...)):
    logger.info(f"Received experiment configuration: {config}")
    runner = ExperimentRunner(config)
    # experiment_results = runner.run_parallel()
    experiment_results = runner.run()
    return experiment_results.to_dict()

@app.post("/download")
def download(body: ExperimentModel = Body(...)):
    logger.info(f"Downloading backtest report for experiment ID: {body.experiment_id}")
    experiment = Experiment(
        experiment_id=body.experiment_id,
        created_at=datetime.now(),
        market_config=body.market_config,
    )
    for run in body.strategy_runs:
        experiment.add_run(StrategyRun(
            run_id=run.run_id,
            strategy_name=run.strategy_name,
            strategy_config=run.strategy_config,
            metadata=run.metadata,
            monitoring_stats=run.monitoring_stats,
            result=BacktestResult(
                summary=run.result.summary,
                series=run.result.series
            )
        ))

    buffer = BytesIO()
    ExcelGenerator(experiment, buffer).generate_report()
    return Response(
        content=buffer.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=backtest_report_{body.experiment_id}.xlsx"}
    )

@app.post("/load-experiment")
def load_experiment(config: dict) -> Experiment | None:
    logger.info(f"Loading experiment with configuration: {config}")
    gateway = ExperimentMetaDataDataGateway("research.db")
    experiment = gateway.get_experiment_instance(config["experiment_id"])
    return experiment

@app.post("/list-experiments")
def list_experiments() -> list[Experiment]:
    """List all available experiments."""
    logger.info(f"Listing available experiments")
    gateway = ExperimentMetaDataDataGateway("research.db")
    load_experiments = gateway.list_of_experiments()
    if load_experiments is None:
        load_experiments = []
    return load_experiments
    
if __name__ == '__main__':
    pass