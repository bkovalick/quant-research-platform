import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from application.experiment_runner import ExperimentRunner
from models.strategy_run import StrategyRun


def test_experiment_continues_after_strategy_failure(monkeypatch):
    runner = ExperimentRunner(
        {"strategies": [{"name": "broken"}, {"name": "working"}]}
    )
    monkeypatch.setattr(runner, "_get_market_config", lambda: {})
    monkeypatch.setattr(
        runner,
        "_build_benchmark_run",
        lambda market_config, experiment: StrategyRun(
            run_id="benchmark", strategy_name="Benchmark", result=None
        ),
    )

    def run_strategy(strategy_cfg, market_config, report):
        if strategy_cfg["name"] == "broken":
            raise ValueError("invalid strategy config")
        return StrategyRun(
            run_id="working-run", strategy_name="working", result=None
        )

    monkeypatch.setattr("application.experiment_runner._run_strategy", run_strategy)
    progress_events = []

    experiment = runner.run(
        lambda strategy_name, **fields: progress_events.append((strategy_name, fields))
    )

    assert [run.strategy_name for run in experiment.strategy_runs] == [
        "working",
        "Benchmark",
    ]
    assert ("broken", {
        "phase": "failed",
        "error": "ValueError: invalid strategy config",
    }) in progress_events
    assert ("working", {"phase": "done"}) in progress_events
