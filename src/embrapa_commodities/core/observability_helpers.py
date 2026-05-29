"""Shared observability lifecycle for single-shot ingest pipelines.

The CLI layer (not the pipeline modules) owns the event lifecycle so the
pipelines stay pure and testable. This context manager encapsulates the
exact event sequence a single-chunk ingest emits, so every source-with-one-
sweep command (IBGE, BCB inflation, BCB currency, and future single-shot
sources) shares one code path and shows up identically in ``embrapa monitor``.

Multi-chunk flows (e.g. ``ingest ibge-batch``) emit a richer per-chunk
sequence by hand and intentionally do NOT use this helper.

Event sequence emitted (mirrors the original hand-written ``ingest ibge``):

    pipeline_start ─► chunk_start ─► [ your work runs here ]
                                        │
                          success ──────┤────► chunk_end + pipeline_end(ok=1)
                          exception ────┘────► chunk_error + pipeline_end(failed=1)  (re-raised)
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from embrapa_commodities import observability


@contextmanager
def pipeline_run(name: str, *, params: dict | None = None) -> Iterator[tuple[str, Path]]:
    """Wrap a single-chunk ingest in the standard observability event sequence.

    Yields ``(run_id, log_path)`` so the caller can surface the log location.
    On any exception the helper emits ``chunk_error`` + ``pipeline_end`` and
    re-raises, so callers keep their own error handling / exit codes.

    Usage::

        with pipeline_run("bcb-inflation", params={"full": full}) as (run_id, log_path):
            console.print(f"event log: {log_path}")
            destination = bcb_inflation.run(settings, full=full)
        # destination is in scope here; only reached on success
    """
    run_id, log_path = observability.init_run(name)
    observability.emit(
        "pipeline_start",
        pipeline=name,
        run_id=run_id,
        chunks_total=1,
        params=params or {},
    )
    observability.emit("chunk_start", chunk_id=name, chunk_n=1, chunk_total=1)
    started = time.monotonic()
    try:
        yield run_id, log_path
    except Exception as exc:
        observability.emit("chunk_error", chunk_id=name, error=str(exc)[:300])
        observability.emit(
            "pipeline_end",
            duration_s=round(time.monotonic() - started, 2),
            chunks_ok=0,
            chunks_failed=1,
        )
        raise
    else:
        duration = round(time.monotonic() - started, 2)
        observability.emit("chunk_end", chunk_id=name, duration_s=duration)
        observability.emit(
            "pipeline_end",
            duration_s=duration,
            chunks_ok=1,
            chunks_failed=0,
        )
