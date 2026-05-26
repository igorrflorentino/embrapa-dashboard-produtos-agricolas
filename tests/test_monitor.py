"""Tests for the monitor's state machine, diagnosis heuristics, and event summarisers."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from embrapa_commodities.monitor import MonitorState, _diagnose, _fmt_duration, _summarize


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


def test_pipeline_end_records_timestamp() -> None:
    state = MonitorState()
    state.apply(_evt("pipeline_start", pipeline="ibge", run_id="r1", chunks_total=0))
    assert state.ended_at is None
    state.apply(_evt("pipeline_end", rows_total=5000, duration_s=120.0))
    assert state.ended_at is not None


def test_ingest_loaded_accumulates_rows() -> None:
    state = MonitorState()
    state.apply(_evt("ingest_loaded", rows=100))
    state.apply(_evt("ingest_loaded", rows=200))
    assert state.rows_total == 300


def test_unknown_event_does_not_raise() -> None:
    """Events not in the handler table should be silently ignored."""
    state = MonitorState()
    state.apply(_evt("something_unknown", foo="bar"))
    assert state.last_event_at is not None
    assert len(state.recent) == 1


def test_chunk_start_resets_state_grid() -> None:
    state = MonitorState()
    state.apply(_evt("chunk_start", chunk_id="c1"))
    state.apply(_evt("state_start", state="SP"))
    assert "SP" in state.states
    state.apply(_evt("chunk_start", chunk_id="c2"))
    assert state.states == {}
    assert state.active_chunk == "c2"


def test_state_end_without_prior_state_start() -> None:
    """state_end for an unknown UF should create the entry via setdefault."""
    state = MonitorState()
    state.apply(_evt("state_end", state="RJ", rows=42, duration_s=1.5))
    assert state.states["RJ"]["status"] == "ok"
    assert state.states["RJ"]["rows"] == 42


def test_chunk_end_without_duration_does_not_record_duration() -> None:
    state = MonitorState()
    state.apply(_evt("chunk_end", chunk_id="c1", rows=10))
    assert state.chunks_done == 1
    assert state.chunk_durations == []


# ── _diagnose — comprehensive coverage ───────────────────────────────────


@pytest.mark.parametrize(
    ("msg", "expected_keyword"),
    [
        ("Read timed out", "slow-byte"),
        ("Read timeout on server", "slow-byte"),
        ("Connection refused", "manutenção"),
        ("Connection reset by peer", "resetada"),
        ("RemoteDisconnected", "resetada"),
        ("Name or service not known", "DNS"),
        ("nodename nor servname provided", "DNS"),
        ("Limite de valores excedido", "células"),
        ("Limite excedido para SIDRA", "células"),
        ("RetryError raised after 5 attempts", "retries"),
        ("stop_after_delay(180)", "retries"),
        ("stop_after_attempt(5)", "retries"),
        ("Unauthorized 401", "autenticado"),
        ("403 Forbidden", "permissão"),
        ("HTTP 404 not found", "produto"),
        ("HTTP 500 server error", "5xx"),
        ("Bad gateway 502", "5xx"),
        ("Service unavailable 503", "5xx"),
        ("Gateway timeout 504", "5xx"),
        ("SSL certificate verify failed", "SSL"),
        ("MemoryError", "Memória"),
        ("Out of memory allocating", "Memória"),
        ("returned no rows for the requested slice", "PEVS"),
        ("SIDRA returned no rows at all", "PEVS"),
    ],
)
def test_diagnose_recognizes_common_errors(msg: str, expected_keyword: str) -> None:
    diagnosis = _diagnose(msg)
    assert expected_keyword.lower() in diagnosis.lower()


def test_diagnose_falls_back_for_unknown_errors() -> None:
    diagnosis = _diagnose("some totally unique error")
    assert "automático" in diagnosis.lower()


def test_diagnose_empty_error() -> None:
    assert "registrada" in _diagnose("").lower()


def test_diagnose_gcs_permission_denied() -> None:
    """Two-condition pattern: both 'permission denied' and 'gs://' must appear."""
    result = _diagnose("Permission denied on gs://my-bucket/file.parquet")
    assert "GCS" in result


def test_diagnose_permission_denied_without_gcs_is_not_gcs_specific() -> None:
    result = _diagnose("Permission denied on /tmp/local-file")
    assert "GCS" not in result


# ── _summarize ────────────────────────────────────────────────────────────


def test_summarize_pipeline_start() -> None:
    ev = _evt("pipeline_start", pipeline="ibge", params={"start_year": 2020, "end_year": 2024},
              chunks_total=3)
    result = _summarize(ev)
    assert "ibge" in result
    assert "2020" in result
    assert "2024" in result


def test_summarize_chunk_start() -> None:
    result = _summarize(_evt("chunk_start", chunk_n=1, chunk_total=3, chunk_id="2020-2022"))
    assert "2020-2022" in result
    assert "1/3" in result


def test_summarize_chunk_end() -> None:
    result = _summarize(_evt("chunk_end", chunk_id="2020-2022", rows=5000, duration_s=12.3))
    assert "ok" in result
    assert "5,000" in result


def test_summarize_chunk_error() -> None:
    result = _summarize(_evt("chunk_error", chunk_id="2020-2022", error="HTTP 503"))
    assert "FAILED" in result
    assert "503" in result


def test_summarize_state_end() -> None:
    result = _summarize(_evt("state_end", state="BA", rows=1234, duration_s=3.2))
    assert "BA" in result
    assert "ok" in result
    assert "1,234" in result


def test_summarize_state_error() -> None:
    result = _summarize(_evt("state_error", state="MG", error="Timeout"))
    assert "MG" in result
    assert "ERROR" in result


def test_summarize_retry() -> None:
    result = _summarize(_evt("retry", state="SP", attempt=3, reason="ConnectionError"))
    assert "retry" in result
    assert "SP" in result
    assert "3" in result


def test_summarize_pipeline_end() -> None:
    result = _summarize(_evt("pipeline_end", rows_total=50000, duration_s=300.0))
    assert "done" in result
    assert "50,000" in result


def test_summarize_unknown_event_uses_generic_format() -> None:
    result = _summarize({"ts": "2024-01-01T00:00:00+00:00", "event": "custom", "foo": "bar"})
    assert "foo=bar" in result


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [(5, "5s"), (45, "45s"), (90, "1m30s"), (3700, "1h01m")],
)
def test_fmt_duration_human_friendly(seconds: int, expected: str) -> None:
    assert _fmt_duration(seconds) == expected

