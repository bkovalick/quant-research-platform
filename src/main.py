from application.experiment_runner import ExperimentRunner
from reporting.reporting_module import ExcelGenerator
import json

from fastapi import FastAPI, Body
from fastapi.middleware.cors import CORSMiddleware

def local_run():
    with open(f"src/config/experiment_high_risk.json", 'r') as f:
        config = json.load(f)

    config = config.copy()
    runner = ExperimentRunner(config)
    experiment_results = runner.run_parallel()
    reporting_module = ExcelGenerator(experiment_results, "backtest_results")
    reporting_module.generate_report()

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