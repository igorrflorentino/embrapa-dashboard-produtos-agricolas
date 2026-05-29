"""Tests for the shared pipeline_run observability context manager."""

from __future__ import annotations

from pathlib import Path

import pytest

from embrapa_commodities.core import observability_helpers
from embrapa_commodities.core.observability_helpers import pipeline_run


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
