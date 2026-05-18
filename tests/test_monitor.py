"""Tests for the monitor's state machine and diagnosis heuristics."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from embrapa_commodities.monitor import MonitorState, _diagnose, _fmt_duration


def _evt(event: str, **fields: object) -> dict:
    return {
        "ts": datetime.now(UTC).isoformat(),
        "event": event,
        **fields,
    }


def test_pipeline_lifecycle_updates_aggregates() -> None:
    state = MonitorState()

    state.apply(
        _evt(
            "pipeline_start",
            pipeline="ibge",
            run_id="r1",
            chunks_total=2,
            params={"start_year": 2020, "end_year": 2024},
        )
    )
    assert state.pipeline == "ibge"
    assert state.chunks_total == 2
    assert state.started_at is not None

    state.apply(_evt("chunk_start", chunk_id="2020-2022", chunk_n=1, chunk_total=2))
    assert state.active_chunk == "2020-2022"

    state.apply(_evt("state_start", state="BA", state_code=29))
    state.apply(_evt("state_end", state="BA", rows=1234, duration_s=4.1))
    assert state.states["BA"]["status"] == "ok"
    assert state.states["BA"]["rows"] == 1234
    assert list(state.state_durations) == [4.1]

    state.apply(_evt("ingest_loaded", pipeline="ibge", rows=1234))
    assert state.rows_total == 1234

    state.apply(_evt("chunk_end", chunk_id="2020-2022", duration_s=10.5))
    assert state.chunks_done == 1
    assert state.active_chunk is None
    assert state.chunk_durations == [10.5]


def test_state_error_increments_error_history() -> None:
    state = MonitorState()
    state.apply(_evt("pipeline_start", pipeline="ibge", run_id="r1", chunks_total=1))
    state.apply(_evt("state_error", state="MG", error="Read timed out"))

    assert state.errors == 1
    assert len(state.error_history) == 1
    err = state.error_history[0]
    assert err["target"] == "MG"
    assert "timed out" in err["error"].lower()


def test_chunk_error_counts_and_clears_active() -> None:
    state = MonitorState()
    state.apply(_evt("pipeline_start", pipeline="ibge", run_id="r1", chunks_total=3))
    state.apply(_evt("chunk_start", chunk_id="2020-2022", chunk_n=1, chunk_total=3))
    state.apply(
        _evt("chunk_error", chunk_id="2020-2022", chunk_n=1, error="HTTP 503", duration_s=2.3)
    )

    assert state.chunks_failed == 1
    assert state.active_chunk is None
    assert state.chunk_durations == [2.3]
    assert len(state.error_history) == 1


def test_retry_event_refreshes_last_seen_to_prevent_stuck_flag() -> None:
    state = MonitorState()
    state.apply(_evt("pipeline_start", pipeline="ibge", run_id="r1", chunks_total=1))
    state.apply(_evt("state_start", state="SP", state_code=35))
    original_last_seen = state.states["SP"]["last_seen"]

    state.apply(_evt("retry", state="SP", attempt=2, reason="ConnectionError"))

    assert state.retries == 1
    assert state.states["SP"]["last_seen"] >= original_last_seen


@pytest.mark.parametrize(
    ("msg", "expected_keyword"),
    [
        ("Read timed out", "slow-byte"),
        ("Connection refused", "manutenção"),
        ("Limite de valores excedido", "células"),
        ("HTTP 503 server error", "5xx"),
        ("Unauthorized 401", "autenticado"),
        ("returned no rows for the requested slice", "PEVS"),
    ],
)
def test_diagnose_recognizes_common_errors(msg: str, expected_keyword: str) -> None:
    diagnosis = _diagnose(msg)
    assert expected_keyword.lower() in diagnosis.lower()


def test_diagnose_falls_back_for_unknown_errors() -> None:
    diagnosis = _diagnose("some totally unique error")
    assert "automático" in diagnosis.lower()


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [(5, "5s"), (45, "45s"), (90, "1m30s"), (3700, "1h01m")],
)
def test_fmt_duration_human_friendly(seconds: int, expected: str) -> None:
    assert _fmt_duration(seconds) == expected
