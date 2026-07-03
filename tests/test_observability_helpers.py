"""Tests for the shared observability helpers (pipeline_run + chunked_run)."""

from __future__ import annotations

from pathlib import Path

import pytest

from embrapa_dashboard.core import observability_helpers
from embrapa_dashboard.core.observability_helpers import (
    ChunkOutcome,
    IngestPartialFailure,
    chunked_run,
    pipeline_run,
    run_chunks,
)


@pytest.fixture
def captured_events(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, dict]]:
    """Capture every observability.emit call as (event_name, fields).

    The context manager calls `observability.init_run` / `observability.emit`
    on the module object; patching those attributes intercepts the CM's calls
    regardless of where the CM lives (same module singleton).
    """
    events: list[tuple[str, dict]] = []
    monkeypatch.setattr(
        observability_helpers.observability,
        "init_run",
        lambda name: ("test-run-id", Path(f"/tmp/{name}.jsonl")),
    )
    monkeypatch.setattr(
        observability_helpers.observability,
        "emit",
        lambda event, **fields: events.append((event, fields)),
    )
    return events


def test_pipeline_run_success_emits_full_sequence(
    captured_events: list[tuple[str, dict]],
) -> None:
    """Happy path: pipeline_start → chunk_start → chunk_end → pipeline_end(ok=1)."""
    with pipeline_run("bcb-inflation", params={"full": True}) as (run_id, log_path):
        assert run_id == "test-run-id"
        assert log_path == Path("/tmp/bcb-inflation.jsonl")

    names = [name for name, _ in captured_events]
    assert names == ["pipeline_start", "chunk_start", "chunk_end", "pipeline_end"]

    start_fields = captured_events[0][1]
    assert start_fields["pipeline"] == "bcb-inflation"
    assert start_fields["chunks_total"] == 1
    assert start_fields["params"] == {"full": True}

    end_fields = captured_events[-1][1]
    assert end_fields["chunks_ok"] == 1
    assert end_fields["chunks_failed"] == 0


def test_pipeline_run_failure_emits_error_and_reraises(
    captured_events: list[tuple[str, dict]],
) -> None:
    """On exception: pipeline_start → chunk_start → chunk_error → pipeline_end(failed=1),
    and the original exception propagates."""
    with pytest.raises(RuntimeError, match="boom"), pipeline_run("bcb-currency") as _:
        raise RuntimeError("boom")

    names = [name for name, _ in captured_events]
    assert names == ["pipeline_start", "chunk_start", "chunk_error", "pipeline_end"]

    error_fields = captured_events[2][1]
    assert error_fields["chunk_id"] == "bcb-currency"
    assert "boom" in error_fields["error"]

    end_fields = captured_events[-1][1]
    assert end_fields["chunks_ok"] == 0
    assert end_fields["chunks_failed"] == 1


def test_pipeline_run_defaults_params_to_empty_dict(
    captured_events: list[tuple[str, dict]],
) -> None:
    """params is optional; omitted → empty dict (never None in the event)."""
    with pipeline_run("ibge"):
        pass

    start_fields = captured_events[0][1]
    assert start_fields["params"] == {}


# ─── chunked_run / ChunkTracker ──────────────────────────────────────────────
def test_chunked_run_emits_lifecycle_and_per_chunk_events(
    captured_events: list[tuple[str, dict]],
) -> None:
    """A 2-chunk run (1 ok, 1 failed) emits pipeline_start, the start/end pair per
    chunk, and a pipeline_end carrying the final ok/failed counts."""
    with chunked_run("comex", total=2, params={"full": False}) as tracker:
        assert tracker.log_path == Path("/tmp/comex.jsonl")
        tracker.start_chunk("EXP_2022")
        tracker.finish(ChunkOutcome("EXP_2022", "loaded", destination="p.d.t"))
        tracker.start_chunk("EXP_2023")
        tracker.finish(ChunkOutcome("EXP_2023", "failed", detail="boom"))

    names = [name for name, _ in captured_events]
    assert names == [
        "pipeline_start",
        "chunk_start",
        "chunk_end",
        "chunk_start",
        "chunk_error",
        "pipeline_end",
    ]
    assert captured_events[0][1]["chunks_total"] == 2
    end_fields = captured_events[-1][1]
    assert end_fields["chunks_ok"] == 1
    assert end_fields["chunks_failed"] == 1
    # The tracker exposes the collected outcomes for the caller's summary.
    assert tracker.chunks_ok == ["EXP_2022"]
    assert tracker.chunks_failed == [("EXP_2023", "boom")]


def test_chunked_run_emits_pipeline_end_even_when_body_raises(
    captured_events: list[tuple[str, dict]],
) -> None:
    """If the command body raises (e.g. a quota error bubbling out of run), the
    pipeline_end event still fires (finally), so the monitor never hangs open."""
    with pytest.raises(RuntimeError, match="quota"):  # noqa: SIM117
        with chunked_run("comtrade", total=3) as tracker:
            tracker.start_chunk("2022_rabc")
            tracker.finish(ChunkOutcome("2022_rabc", "loaded", destination="p.d.t"))
            raise RuntimeError("quota exhausted")

    names = [name for name, _ in captured_events]
    assert names[-1] == "pipeline_end"
    # One chunk finished ok before the raise.
    assert captured_events[-1][1]["chunks_ok"] == 1


def test_chunk_tracker_start_chunk_returns_incrementing_index() -> None:
    """start_chunk returns the 1-based index for the [i/total] console heading."""
    tracker = observability_helpers.ChunkTracker(total=3)
    assert tracker.start_chunk("a") == 1
    tracker.finish(ChunkOutcome("a", "skipped"))
    assert tracker.start_chunk("b") == 2


# ── run_chunks: the shared run-loop for the chunked pipelines (COMEX/COMTRADE) ──
def _outcome(chunk_id, status, *, destination="", detail=""):
    return lambda: ChunkOutcome(chunk_id, status, destination=destination, detail=detail)


def test_run_chunks_returns_last_destination_and_calls_hooks() -> None:
    starts: list[str] = []
    seen: list[str] = []
    chunks = [
        ("a", _outcome("a", "loaded", destination="p.d.t1")),
        ("b", _outcome("b", "skipped", detail="unchanged")),
        ("c", _outcome("c", "loaded", destination="p.d.t2")),
    ]
    dest = run_chunks(
        chunks,
        on_chunk_start=starts.append,
        on_chunk=lambda o: seen.append(o.chunk_id),
    )
    assert dest == "p.d.t2"  # last NON-EMPTY destination wins
    assert starts == ["a", "b", "c"]  # on_chunk_start fires before each chunk
    assert seen == ["a", "b", "c"]  # on_chunk fires after each


def test_run_chunks_continues_after_failure_and_raises_when_no_consumer() -> None:
    ran: list[str] = []

    def proc(cid, status, **kw):
        def _p():
            ran.append(cid)
            return ChunkOutcome(cid, status, **kw)

        return _p

    chunks = [
        ("a", proc("a", "loaded", destination="p.d.t1")),
        ("b", proc("b", "failed", detail="boom")),
        ("c", proc("c", "loaded", destination="p.d.t2")),
    ]
    # No on_chunk consumer → the loop still runs EVERY chunk (continue-on-failure),
    # then raises the aggregated failure at the end.
    with pytest.raises(IngestPartialFailure) as exc:
        run_chunks(chunks)
    assert ran == ["a", "b", "c"]  # the failure did not strand c
    assert exc.value.failures == [("b", "boom")]


def test_run_chunks_with_consumer_does_not_raise_on_failure() -> None:
    seen: list[tuple[str, str]] = []
    chunks = [
        ("a", _outcome("a", "failed", detail="boom")),
        ("b", _outcome("b", "loaded", destination="p.d.t")),
    ]
    # WITH an on_chunk consumer, failures are forwarded, not raised — the caller
    # (the CLI) decides the exit code from the outcomes it saw.
    dest = run_chunks(chunks, on_chunk=lambda o: seen.append((o.chunk_id, o.status)))
    assert dest == "p.d.t"
    assert seen == [("a", "failed"), ("b", "loaded")]


def test_run_chunks_truncates_failure_detail_to_200_chars() -> None:
    long = "x" * 500
    with pytest.raises(IngestPartialFailure) as exc:
        run_chunks([("a", _outcome("a", "failed", detail=long))])
    assert exc.value.failures == [("a", "x" * 200)]
