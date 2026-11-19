import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from application.experiment_runner import ExperimentRunner
from application.progress import ProgressTracker, RunCancelled, raise_if_cancelled
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


def _stub_runner(monkeypatch, names):
    runner = ExperimentRunner({"strategies": [{"name": n} for n in names]})
    monkeypatch.setattr(runner, "_get_market_config", lambda: {})
    monkeypatch.setattr(runner, "_warm_market_cache", lambda m_cfg: None)
    return runner


def test_stop_unwinds_sequential_run_and_skips_remaining_strategies(monkeypatch):
    runner = _stub_runner(monkeypatch, ["first", "second"])
    cancel = threading.Event()
    started = []

    def run_strategy(strategy_cfg, market_config, report):
        started.append(strategy_cfg["name"])
        report(phase="running", pct=10.0)
        cancel.set()  # the user presses Stop mid-backtest
        report(phase="running", pct=11.0)
        raise AssertionError("the report after Stop should have raised")

    monkeypatch.setattr("application.experiment_runner._run_strategy", run_strategy)
    tracker = ProgressTracker(["first", "second"])

    with pytest.raises(RunCancelled):
        runner.run(tracker, cancel_event=cancel)

    assert started == ["first"]
    tracker.set_status("cancelled")
    phases = {s["name"]: s["phase"] for s in tracker.snapshot()["strategies"]}
    assert phases == {"first": "cancelled", "second": "cancelled"}


def test_stop_unwinds_parallel_run(monkeypatch):
    # Set before the run: each worker process stops at its first report (loading_data),
    # before touching market data, and the runner raises once they have exited.
    runner = _stub_runner(monkeypatch, ["a", "b", "c"])
    cancel = threading.Event()
    cancel.set()
    tracker = ProgressTracker(["a", "b", "c"])

    with pytest.raises(RunCancelled):
        runner.run_parallel(tracker, max_workers=2, cancel_event=cancel)


def test_final_reports_go_through_after_stop():
    cancel = threading.Event()
    cancel.set()
    for phase in ("done", "failed", "cancelled", "analyzing"):
        raise_if_cancelled(cancel, phase)  # must not raise
    with pytest.raises(RunCancelled):
        raise_if_cancelled(cancel, "running")
