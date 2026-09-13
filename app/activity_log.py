"""
Local Activity Log — REAL, append-only JSON-lines audit trail.

Every planning, routing and tool-call step writes one line here. This is
the "Activity Log" box in the architecture, and it is also the single
most important thing on screen during the demo video: it is what visibly
proves multi-step agentic reasoning rather than one black-box call.

Owner: Track B.
"""
import json
import os
import threading
import time

from . import config

LOG_PATH = os.path.join(config.LOGS_DIR, "activity.log")

_lock = threading.Lock()


def log_step(task_id: str, stage: str, detail: str, meta: dict | None = None) -> dict:
    entry = {
        "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
        "task_id": task_id,
        "stage": stage,
        "detail": detail,
        "meta": meta or {},
    }
    with _lock:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    return entry


def read_log(limit: int = 200) -> list[dict]:
    if not os.path.exists(LOG_PATH):
        return []
    with _lock:
        with open(LOG_PATH, encoding="utf-8") as f:
            lines = f.readlines()[-limit:]
    out = []
    for line in lines:
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def clear_log() -> None:
    with _lock:
        open(LOG_PATH, "w", encoding="utf-8").close()
