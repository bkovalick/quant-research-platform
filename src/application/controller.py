from application.experiment_runner import ExperimentRunner
from reporting.report_generation import ExcelGenerator
from models.experiment import Experiment
from models.backtest_result import BacktestResult
from models.strategy_run import StrategyRun
from models.experiment_model import ExperimentModel
from infrastructure.strategy_results_data_gateway import ExperimentMetaDataDataGateway

from application.progress import ProgressTracker

import threading
import uuid
from collections import OrderedDict
from dataclasses import dataclass
from typing import Optional
from datetime import datetime
from fastapi import FastAPI, Body, HTTPException
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
    experiment_results = runner.run()
    return experiment_results.to_dict()

@app.post("/run-experiment-parallel")
def run_experiment_parallel(config: dict = Body(...)):
    logger.info(f"Received experiment configuration: {config}")
    runner = ExperimentRunner(config)
    experiment_results = runner.run_parallel()
    return experiment_results.to_dict()

# ---- Background runs with progress -------------------------------------------
# POST /experiments starts a run and returns a job id; GET /experiments/{id}
# returns progress (cheap, poll it); GET /experiments/{id}/result returns the
# experiment once status == "done". Jobs live in memory for this process only.

@dataclass
class _Job:
    tracker: ProgressTracker
    result: Optional[dict] = None

_JOBS: "OrderedDict[str, _Job]" = OrderedDict()
_JOBS_LOCK = threading.Lock()
_MAX_JOBS = 20


def _run_job(job: _Job, config: dict, parallel: bool) -> None:
    try:
        runner = ExperimentRunner(config)
        experiment = runner.run_parallel(job.tracker) if parallel else runner.run(job.tracker)
        job.tracker.set_status("finalizing")
        job.result = experiment.to_dict()
        job.tracker.set_status("done")
    except Exception as exc:
        logger.exception("Experiment job failed")
        job.tracker.set_status("failed", error=f"{type(exc).__name__}: {exc}")


def _get_job(job_id: str) -> _Job:
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Unknown job {job_id}")
    return job


@app.post("/experiments")
def start_experiment(config: dict = Body(...), parallel: bool = False):
    names = [s.get("name", f"strategy_{i}") for i, s in enumerate(config.get("strategies", []))]
    job_id = str(uuid.uuid4())
    job = _Job(tracker=ProgressTracker(names))
    with _JOBS_LOCK:
        _JOBS[job_id] = job
        finished = [k for k, j in _JOBS.items() if j.tracker.status in ("done", "failed")]
        for k in finished[: max(0, len(_JOBS) - _MAX_JOBS)]:
            del _JOBS[k]
    threading.Thread(target=_run_job, args=(job, config, parallel), daemon=True).start()
    logger.info("Started experiment job %s with %s strategies (parallel=%s)", job_id, len(names), parallel)
    return {"job_id": job_id}


@app.get("/experiments/{job_id}")
def experiment_progress(job_id: str):
    return {"job_id": job_id, **_get_job(job_id).tracker.snapshot()}


@app.get("/experiments/{job_id}/result")
def experiment_result(job_id: str):
    job = _get_job(job_id)
    if job.tracker.status != "done" or job.result is None:
        raise HTTPException(status_code=409, detail=f"Job {job_id} is {job.tracker.status}")
    return job.result


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