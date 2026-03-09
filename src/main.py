from application.experiment_runner import ExperimentRunner
from reporting.reporting_module import ExcelGenerator
from models.experiment import Experiment
from models.backtest_result import BacktestResult
from models.strategy_run import StrategyRun
from models.experiment_model import ExperimentModel

import json
from datetime import datetime

from fastapi import FastAPI, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from io import BytesIO
from pathlib import Path

def create_folder_path(folder_name: str):
    path = Path(folder_name)
    path.mkdir(parents=True, exist_ok=True)

def local_run():
    with open(f"src/config/experiment_fwp.json", 'r') as f:
        config = json.load(f)

    config = config.copy()
    runner = ExperimentRunner(config)
    experiment_results = runner.run_parallel()
    buffer = BytesIO()
    reporting_module = ExcelGenerator(experiment_results, buffer)
    reporting_module.generate_report()
    folder_path = "backtest_results" + "/" + datetime.now().strftime('%Y-%m-%d')
    create_folder_path(folder_path)
    with open(folder_path + "/backtest_report.xlsx", "wb") as f:
        f.write(buffer.getvalue())

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
    runner = ExperimentRunner(config)
    experiment_results = runner.run_parallel()
    return experiment_results.to_dict()

from fastapi import Response

@app.post("/download")
def download(body: ExperimentModel = Body(...)):
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

@app.post("/load-experiment")
def load_experiment(config: dict):
    pass

@app.post("/list-experiments")
def list_experiments(config: dict):
    pass

if __name__ == '__main__':
    import os
    run_mode = os.environ.get("RUN_MODE", "api").lower()
    run_mode = "local"
    if run_mode == "local":
        local_run()
    else:
        import uvicorn
        uvicorn.run("main:app", reload=True)