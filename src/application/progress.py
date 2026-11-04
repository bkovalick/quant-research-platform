"""
Run-progress reporting.

A progress callback has the signature ``progress(strategy_name: str, **fields)``.
Fields used: phase (queued | loading_data | running | analyzing | done | failed),
pct (0-100), as_of (backtest date, ISO string), error.

ProgressTracker is the in-process sink (thread-safe). QueueReporter is a picklable
callback for ProcessPoolExecutor workers; ExperimentRunner drains its queue into the
real callback on a background thread.
"""
import threading
import time
from typing import Callable, Dict, List, Optional

ProgressCallback = Callable[..., None]

PHASES = ("queued", "loading_data", "running", "analyzing", "done", "failed")


class ProgressTracker:
    def __init__(self, strategy_names: List[str]):
        self._lock = threading.Lock()
        self.started_at = time.time()
        self.finished_at: Optional[float] = None
        self.status = "running"          # running | finalizing | done | failed
        self.error: Optional[str] = None
        self._strategies: Dict[str, dict] = {
            name: {"name": name, "phase": "queued", "pct": 0.0, "as_of": None,
                   "started_at": None, "finished_at": None, "error": None}
            for name in strategy_names
        }

    def __call__(self, strategy_name: str, **fields) -> None:
        now = time.time()
        with self._lock:
            entry = self._strategies.setdefault(strategy_name, {
                "name": strategy_name, "phase": "queued", "pct": 0.0, "as_of": None,
                "started_at": None, "finished_at": None, "error": None,
            })
            phase = fields.get("phase")
            if phase in ("loading_data", "running") and entry["started_at"] is None:
                entry["started_at"] = now
            if phase in ("done", "failed"):
                entry["finished_at"] = now
                if phase == "done":
                    fields.setdefault("pct", 100.0)
            entry.update({k: v for k, v in fields.items() if k in entry})

    def set_status(self, status: str, error: Optional[str] = None) -> None:
        with self._lock:
            self.status = status
            self.error = error
            if status in ("done", "failed"):
                self.finished_at = time.time()

    def snapshot(self) -> dict:
        now = time.time()
        with self._lock:
            strategies = []
            for s in self._strategies.values():
                s = dict(s)
                start, end = s.pop("started_at"), s.pop("finished_at")
                s["elapsed_s"] = round(((end or now) - start), 1) if start else 0.0
                s["eta_s"] = _eta(s["pct"], s["elapsed_s"]) if s["phase"] == "running" else None
                strategies.append(s)
            total = len(strategies) or 1
            return {
                "status": self.status,
                "error": self.error,
                "elapsed_s": round((self.finished_at or now) - self.started_at, 1),
                "pct": round(sum(s["pct"] for s in strategies) / total, 1),
                "strategies": strategies,
            }


def _eta(pct: float, elapsed_s: float) -> Optional[float]:
    if pct < 2 or elapsed_s <= 0:
        return None
    return round(elapsed_s * (100 - pct) / pct, 1)


class QueueReporter:
    """Picklable progress callback that forwards events through a (Manager) queue."""
    def __init__(self, queue):
        self.queue = queue

    def __call__(self, strategy_name: str, **fields) -> None:
        try:
            self.queue.put((strategy_name, fields))
        except Exception:
            pass  # progress is best-effort; never fail a backtest over it
