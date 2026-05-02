from application.experiment_runner import ExperimentRunner
from reporting.report_generation import ExcelGenerator
from models.experiment import Experiment
from models.backtest_result import BacktestResult
from models.strategy_run import StrategyRun
from models.experiment_model import ExperimentModel

from datetime import datetime
from fastapi import FastAPI, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi import Response
from io import BytesIO
import logging

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
    filename="optimizer.log"
)

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
    logging.info(f"Received experiment configuration: {config}")
    runner = ExperimentRunner(config)
    experiment_results = runner.run_parallel()
    return experiment_results.to_dict()

@app.post("/download")
def download(body: ExperimentModel = Body(...)):
    logging.info(f"Downloading backtest report for experiment ID: {body.experiment_id}")
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
        headers={"Content-Disposition": "attachment; filename=backtest_report.xlsx"}
    )

# Both of these are future installments that rely on data storage and retrieval, which is not yet implemented. They will be used to load existing experiments and list all available experiments respectively.
@app.post("/load-experiment")
def load_experiment(config: dict):
    return {"message": "This endpoint will load an experiment based on the provided configuration, but it is not yet implemented."}

@app.post("/list-experiments")
def list_experiments(config: dict) -> list:
    load_experiments = []
    return load_experiments

if __name__ == '__main__':
    pass