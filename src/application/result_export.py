"""Shapes an Experiment for the UI and saves completed runs to disk.

The two weight matrices are ~95% of a run's serialized size (~75 MB per stock strategy over
2000-2026) and nothing in the UI reads them, so the UI payload leaves them out. The pickle keeps
``portfolio_weights`` (the Excel report's weights sheet needs it) and drops only
``portfolio_weights_long``, which is the same matrix reshaped into rows.
"""
import json
import logging
import pickle
from dataclasses import replace
from pathlib import Path

from fastapi.encoders import jsonable_encoder

from models.experiment import Experiment

logger = logging.getLogger(__name__)

UI_EXCLUDED_SERIES = frozenset({"portfolio_weights", "portfolio_weights_long"})
PICKLE_EXCLUDED_SERIES = frozenset({"portfolio_weights_long"})


def experiment_ui_payload(experiment: Experiment) -> dict:
    """What the API returns and the UI loads: everything except the weight matrices."""
    return experiment.to_dict(exclude_series=UI_EXCLUDED_SERIES)


def save_experiment_files(experiment: Experiment, folder: str | Path, stamp: str) -> tuple[Path, Path]:
    """Write ``experiment_<stamp>.json`` (open it from the UI's Lab) and ``experiment_<stamp>.pkl``
    (full results, for rebuilding the Excel report without rerunning). Returns both paths."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)

    json_path = folder / f"experiment_{stamp}.json"
    payload = jsonable_encoder(experiment_ui_payload(experiment))
    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, allow_nan=False)    # same rules as the API's JSON response

    pkl_path = folder / f"experiment_{stamp}.pkl"
    with open(pkl_path, "wb") as fh:
        pickle.dump(_without_series(experiment, PICKLE_EXCLUDED_SERIES), fh, protocol=pickle.HIGHEST_PROTOCOL)

    logger.info("Saved experiment results: %s (%.1f MB), %s (%.1f MB)",
                json_path, json_path.stat().st_size / 1e6, pkl_path, pkl_path.stat().st_size / 1e6)
    return json_path, pkl_path


def load_experiment_pickle(path: str | Path) -> Experiment:
    with open(path, "rb") as fh:
        return pickle.load(fh)


def _without_series(experiment: Experiment, names: frozenset) -> Experiment:
    runs = [
        replace(run, result=replace(run.result, series={k: v for k, v in run.result.series.items() if k not in names}))
        if run.result is not None else run
        for run in experiment.strategy_runs
    ]
    return replace(experiment, strategy_runs=runs)
