"""Structured JSON event logging for pipeline runs.

One JSONL file per run in ``$EMBRAPA_LOG_DIR`` (default: ``~/.embrapa/logs/``).
Each line is a self-describing event consumed by the live `embrapa monitor`
CLI and by anyone grepping for incidents.

Design rules:
    * Events are append-only and ordered. The monitor relies on ordering.
    * Each event has ``ts`` (UTC ISO-8601) and ``event`` (slug). Other fields
      are event-specific — never re-key existing ones across versions.
    * Logging here is independent of the existing root logger so JSON never
      leaks into the user's console (and rich console output never leaks
      into the JSONL).
"""

from __future__ import annotations

import json
import logging
import os
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

DEFAULT_LOG_DIR = Path.home() / ".embrapa" / "logs"
_MAX_BYTES = 10 * 1024 * 1024  # 10 MB before rotation
_BACKUP_COUNT = 5  # keep 5 rotations → ~60 MB ceiling per run

_event_logger: logging.Logger | None = None
_current_run_id: str | None = None
_current_log_path: Path | None = None


def log_dir() -> Path:
    return Path(os.environ.get("EMBRAPA_LOG_DIR") or DEFAULT_LOG_DIR)


def init_run(pipeline: str) -> tuple[str, Path]:
    """Open a fresh JSONL event log for a pipeline run.

    Returns (run_id, log_path). The run_id is a UTC timestamp slug shared
    between log filename and the GCS run prefix so reconciliation is trivial.
    """
    global _event_logger, _current_run_id, _current_log_path
    directory = log_dir()
    directory.mkdir(parents=True, exist_ok=True)

    _current_run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    _current_log_path = directory / f"{pipeline}-{_current_run_id}.jsonl"

    logger = logging.getLogger(f"embrapa.events.{pipeline}")
    logger.setLevel(logging.INFO)
    for handler in list(logger.handlers):
        # close() before removeHandler() — removeHandler only detaches; the
        # RotatingFileHandler keeps its file open until GC otherwise. Re-init
        # of the same pipeline name in one process (tests, future multi-run
        # flows) would leak a file handle per call without this.
        handler.close()
        logger.removeHandler(handler)
    handler = RotatingFileHandler(
        _current_log_path,
        maxBytes=_MAX_BYTES,
        backupCount=_BACKUP_COUNT,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    logger.propagate = False  # don't leak JSON into the root rich console

    _event_logger = logger
    return _current_run_id, _current_log_path


def emit(event: str, **fields: object) -> None:
    """Append one JSON event. No-op if init_run() was never called."""
    if _event_logger is None:
        return
    record = {"ts": datetime.now(UTC).isoformat(), "event": event, **fields}
    _event_logger.info(json.dumps(record, default=str, ensure_ascii=False))


def latest_log_path(pipeline: str | None = None) -> Path | None:
    """Most recently modified log file, optionally filtered by pipeline prefix."""
    directory = log_dir()
    if not directory.exists():
        return None
    pattern = f"{pipeline}-*.jsonl" if pipeline else "*.jsonl"
    candidates = list(directory.glob(pattern))
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def list_log_paths() -> list[Path]:
    directory = log_dir()
    if not directory.exists():
        return []
    return sorted(directory.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
