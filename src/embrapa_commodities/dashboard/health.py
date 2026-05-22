"""Central health/state tracker for the dashboard.

A single `Health` singleton accumulates structured signals from across the
app — boot metadata, BigQuery snapshot lifecycle, recent errors — and the
`/status` page surfaces them. The page itself never queries BigQuery, so
it's safe to open even when the rest of the dashboard is degraded.

Thread-safe via a single RLock; all mutators copy the underlying dicts so
the page callback always sees a consistent snapshot.
"""

from __future__ import annotations

import copy
import os
import threading
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class StageState:
    """A single named loading stage (e.g. BigQuery snapshot, layout render)."""

    name: str
    label: str
    status: str = "pending"  # pending | running | ok | error
    started_at: datetime | None = None
    finished_at: datetime | None = None
    detail: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def elapsed_seconds(self) -> float | None:
        if self.started_at is None:
            return None
        end = self.finished_at or datetime.now()
        return (end - self.started_at).total_seconds()


class Health:
    """Thread-safe in-memory health registry."""

    def __init__(self, error_history: int = 20) -> None:
        self._lock = threading.RLock()
        self._app_started_at = datetime.now()
        self._stages: dict[str, StageState] = {}
        self._errors: deque[dict[str, Any]] = deque(maxlen=error_history)

        # Static container metadata (Cloud Run sets these env vars).
        self._revision = os.environ.get("K_REVISION") or "local"
        self._service = os.environ.get("K_SERVICE") or "embrapa-dashboard-commodities"
        self._region = (
            os.environ.get("CLOUD_RUN_REGION") or os.environ.get("FUNCTION_REGION") or "unknown"
        )

        # Seed the well-known stages so the status page always renders the
        # full ladder even before anything has happened.
        for name, label in _STAGE_LABELS:
            self._stages[name] = StageState(name=name, label=label)

    # ── Stage mutators ────────────────────────────────────────────────────
    def stage_started(self, name: str, *, detail: str | None = None) -> None:
        with self._lock:
            stage = self._stages.get(name) or StageState(
                name=name, label=name.replace("_", " ").title()
            )
            stage.status = "running"
            stage.started_at = datetime.now()
            stage.finished_at = None
            stage.detail = detail
            self._stages[name] = stage

    def stage_ok(self, name: str, *, detail: str | None = None, **extra: Any) -> None:
        with self._lock:
            stage = self._stages.get(name) or StageState(
                name=name, label=name.replace("_", " ").title()
            )
            stage.status = "ok"
            stage.finished_at = datetime.now()
            if detail is not None:
                stage.detail = detail
            if extra:
                stage.extra.update(extra)
            self._stages[name] = stage

    def stage_error(self, name: str, message: str, **extra: Any) -> None:
        with self._lock:
            stage = self._stages.get(name) or StageState(
                name=name, label=name.replace("_", " ").title()
            )
            stage.status = "error"
            stage.finished_at = datetime.now()
            stage.detail = message
            if extra:
                stage.extra.update(extra)
            self._stages[name] = stage

    # ── Errors ────────────────────────────────────────────────────────────
    def record_error(self, payload: dict[str, Any]) -> None:
        with self._lock:
            self._errors.appendleft({**payload, "timestamp": datetime.now()})

    # ── Snapshot for the status page ──────────────────────────────────────
    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "app_started_at": self._app_started_at,
                "revision": self._revision,
                "service": self._service,
                "region": self._region,
                "uptime_seconds": (datetime.now() - self._app_started_at).total_seconds(),
                "stages": copy.deepcopy(list(self._stages.values())),
                "errors": list(self._errors),
            }

    def is_ready(self) -> bool:
        """All declared stages are in ok status."""
        with self._lock:
            return all(s.status == "ok" for s in self._stages.values())


# Pre-declared stages — keep label text in pt-BR for the UI.
_STAGE_LABELS: list[tuple[str, str]] = [
    ("container", "Container Cloud Run iniciado"),
    ("dash_app", "Aplicação Dash montada"),
    ("bq_snapshot", "Snapshot do BigQuery carregado"),
    ("page_callbacks", "Callbacks das páginas registradas"),
]


# Module-level singleton.
health = Health()
