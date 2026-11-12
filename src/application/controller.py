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
import os
from utils.logging_config import setup_logging

from application.experiment_runner import ExperimentRunner
from application.progress import ProgressTracker
from application.result_export import experiment_ui_payload
from reporting.report_generation import ExcelGenerator
from models.experiment import Experiment
from models.backtest_result import BacktestResult
from models.strategy_run import StrategyRun
from models.experiment_model import ExperimentModel
from infrastructure.strategy_results_data_gateway import ExperimentMetaDataDataGateway, save_experiment

DEFAULT_RESULTS_DB = "research.duckdb"

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

def _resolve_db(config: Optional[dict] = None) -> str:
    """One place that decides which DuckDB file results go to (and are read from)."""
    config = config or {}
    db = config.get("results_database") or config.get("database_name") or DEFAULT_RESULTS_DB
    return os.path.abspath(db)

@app.post("/save-experiment")
def save_experiment_endpoint(experiment: Experiment, config: dict = Body(...)):
    resolved_db = _resolve_db(config)
    save_experiment(experiment, resolved_db)
    return {"experiment_id": experiment.experiment_id, "database": resolved_db}

@dataclass
class _Job:
    tracker: ProgressTracker
    result: Optional[dict] = None

_JOBS: "OrderedDict[str, _Job]" = OrderedDict()
_JOBS_LOCK = threading.Lock()
_MAX_JOBS = 20

def _run_job(job: _Job, config: dict, parallel: bool, persist: bool) -> None:
    try:
        runner = ExperimentRunner(config)
        experiment = runner.run_parallel(job.tracker) if parallel else runner.run(job.tracker)
        job.tracker.set_status("finalizing")
        job.result = experiment_ui_payload(experiment)   # weight matrices left out: ~95% of the size, unused by the UI
    except Exception as exc:
        logger.exception("Experiment job failed")
        job.tracker.set_status("failed", error=f"{type(exc).__name__}: {exc}")
        return

    if persist:
        # A failed save must not cost the user their results: the run still
        # completes and the save error is reported alongside it.
        database = _resolve_db(config)
        job.tracker.set_save(database)
        job.tracker.set_status("saving")
        try:
            save_experiment(experiment, database)
            job.tracker.set_save(database, saved=True)
        except Exception as exc:
            logger.exception("Saving experiment %s failed", experiment.experiment_id)
            job.tracker.set_save(database, error=f"{type(exc).__name__}: {exc}")
    job.tracker.set_status("done")

def _get_job(job_id: str) -> _Job:
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Unknown job {job_id}")
    return job

@app.post("/experiments")
def start_experiment(config: dict = Body(...), parallel: bool = False, persist: bool = False):
    names = [s.get("name", f"strategy_{i}") for i, s in enumerate(config.get("strategies", []))]
    job_id = str(uuid.uuid4())
    job = _Job(tracker=ProgressTracker(names))
    with _JOBS_LOCK:
        _JOBS[job_id] = job
        finished = [k for k, j in _JOBS.items() if j.tracker.status in ("done", "failed")]
        for k in finished[: max(0, len(_JOBS) - _MAX_JOBS)]:
            del _JOBS[k]
    threading.Thread(target=_run_job, args=(job, config, parallel, persist), daemon=True).start()
    logger.info("Started experiment job %s with %s strategies (parallel=%s, persist=%s)",
                job_id, len(names), parallel, persist)
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
    with ExperimentMetaDataDataGateway(_resolve_db(config)) as gateway:
        return gateway.get_experiment_instance(config["experiment_id"])

@app.post("/list-experiments")
def list_experiments() -> list[Experiment]:
    """List all available experiments."""
    logger.info(f"Listing available experiments")
    with ExperimentMetaDataDataGateway(_resolve_db()) as gateway:
        return gateway.list_of_experiments() or []