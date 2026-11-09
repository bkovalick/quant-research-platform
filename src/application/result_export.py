"""Shapes an Experiment for the UI and saves completed runs to disk.

The weight matrix is most of a run's serialized size and nothing in the UI reads it, so the
UI payload leaves it out. The pickle keeps everything (the Excel report's weights sheet needs it).
"""
import json
import logging
import pickle
from pathlib import Path

from fastapi.encoders import jsonable_encoder

from models.experiment import Experiment

logger = logging.getLogger(__name__)

UI_EXCLUDED_SERIES = frozenset({"portfolio_weights"})


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
        pickle.dump(experiment, fh, protocol=pickle.HIGHEST_PROTOCOL)

    logger.info("Saved experiment results: %s (%.1f MB), %s (%.1f MB)",
                json_path, json_path.stat().st_size / 1e6, pkl_path, pkl_path.stat().st_size / 1e6)
    return json_path, pkl_path


def load_experiment_pickle(path: str | Path) -> Experiment:
    with open(path, "rb") as fh:
        return pickle.load(fh)
