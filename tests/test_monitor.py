"""Tests for the monitor's state machine, diagnosis heuristics, and event summarisers."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from embrapa_commodities.monitor import (
    STUCK_THRESHOLD_S,
    MonitorState,
    _build_state_grid,
    _diagnose,
    _fmt_duration,
    _render_state_cell,
    _summarize,
    _tail_jsonl,
)


def _evt(event: str, **fields: object) -> dict:
    return {
        "ts": datetime.now(UTC).isoformat(),
        "event": event,
        **fields,
    }


def _write_log(path: Path, events: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")


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
        ("Connection refused", "maintenance"),
        ("Connection reset by peer", "reset"),
        ("RemoteDisconnected", "reset"),
        ("Name or service not known", "DNS"),
        ("nodename nor servname provided", "DNS"),
        ("Limite de valores excedido", "cell limit"),
        ("Limite excedido para SIDRA", "cell limit"),
        ("RetryError raised after 5 attempts", "retries"),
        ("stop_after_delay(180)", "retries"),
        ("stop_after_attempt(5)", "retries"),
        ("Unauthorized 401", "authenticated"),
        ("403 Forbidden", "permission"),
        ("HTTP 404 not found", "product"),
        ("HTTP 500 server error", "5xx"),
        ("Bad gateway 502", "5xx"),
        ("Service unavailable 503", "5xx"),
        ("Gateway timeout 504", "5xx"),
        ("SSL certificate verify failed", "SSL"),
        ("MemoryError", "memory"),
        ("Out of memory allocating", "memory"),
        ("returned no rows for the requested slice", "PEVS"),
        ("SIDRA returned no rows at all", "PEVS"),
    ],
)
def test_diagnose_recognizes_common_errors(msg: str, expected_keyword: str) -> None:
    diagnosis = _diagnose(msg)
    assert expected_keyword.lower() in diagnosis.lower()


def test_diagnose_falls_back_for_unknown_errors() -> None:
    diagnosis = _diagnose("some totally unique error")
    assert "automatic" in diagnosis.lower()


def test_diagnose_empty_error() -> None:
    assert "recorded" in _diagnose("").lower()


def test_diagnose_gcs_permission_denied() -> None:
    """Two-condition pattern: both 'permission denied' and 'gs://' must appear."""
    result = _diagnose("Permission denied on gs://my-bucket/file.parquet")
    assert "GCS" in result


def test_diagnose_permission_denied_without_gcs_is_not_gcs_specific() -> None:
    result = _diagnose("Permission denied on /tmp/local-file")
    assert "GCS" not in result


# ── _summarize ────────────────────────────────────────────────────────────


def test_summarize_pipeline_start() -> None:
    ev = _evt(
        "pipeline_start",
        pipeline="ibge",
        params={"start_year": 2020, "end_year": 2024},
        chunks_total=3,
    )
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


def test_summarize_retry_falls_back_to_series_for_comex_style_events() -> None:
    """COMEX/COMTRADE retries carry 'series' (not 'state') — the summary must
    show that target instead of 'retry ?'."""
    result = _summarize(
        _evt("retry", series="EXP_2024.csv", window="", attempt=2, reason="timeout")
    )
    assert "EXP_2024.csv" in result
    assert "retry ?" not in result


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


# ── _render_state_cell — per-status renderers (P1 refactor coverage) ────


# NOTE: timestamps in these fixtures use 1000.0 (not 0.0) as the baseline.
# ``_render_state_cell`` resolves ``last_seen`` via ``info.get("last_seen") or
# info.get("started_at") or now`` — the ``or`` chain treats 0.0 as falsy and
# would silently fall through to ``now``, defeating the stuck check. In
# production this never matters (time.time() ≈ 1.7e9) but tests must respect
# the implicit "timestamps are truthy" invariant.
_T0 = 1000.0


def _state_with_one_uf(uf: str, **info_fields: object) -> tuple[MonitorState, dict]:
    """Build a MonitorState whose ``states`` dict has one UF with the given fields."""
    state = MonitorState()
    info: dict = {"status": "running", "started_at": _T0, "last_seen": _T0, **info_fields}
    state.states[uf] = info
    return state, info


def test_render_state_running_normal_uses_cyan_with_elapsed() -> None:
    state, info = _state_with_one_uf("SP", started_at=_T0, last_seen=_T0 + 10)
    cell = _render_state_cell("SP", info, state, now=_T0 + 10)
    text = cell.markup
    assert "cyan" in text
    assert "yellow" not in text
    assert "10s" in text
    assert "STUCK" not in text


def test_render_state_running_stuck_uses_yellow_when_last_seen_stale() -> None:
    # last_seen is older than STUCK_THRESHOLD_S → must flip to yellow STUCK.
    state, info = _state_with_one_uf("BA", started_at=_T0, last_seen=_T0)
    now = _T0 + STUCK_THRESHOLD_S + 5  # 5s past the stuck threshold
    cell = _render_state_cell("BA", info, state, now=now)
    text = cell.markup
    assert "yellow" in text
    assert "STUCK" in text


def test_render_state_ok_uses_green_check_with_rows_and_duration() -> None:
    state, info = _state_with_one_uf("MG", status="ok", rows=1234, duration_s=3.5)
    cell = _render_state_cell("MG", info, state, now=10.0)
    text = cell.markup
    assert "green" in text
    assert "✓" in text
    assert "1,234" in text
    assert "3.5s" in text


def test_render_state_ok_handles_missing_rows_and_duration() -> None:
    # state_end with no rows/duration → both render as '?'.
    state, info = _state_with_one_uf("PR", status="ok")
    cell = _render_state_cell("PR", info, state, now=10.0)
    assert "?" in cell.markup


def test_render_state_error_uses_red_cross_with_truncated_message() -> None:
    long_err = "x" * 100  # truncation kicks in at 20 chars
    state, info = _state_with_one_uf("RJ", status="error", error=long_err)
    cell = _render_state_cell("RJ", info, state, now=10.0)
    text = cell.markup
    assert "red" in text
    assert "✗" in text
    # 20-char slice, no more.
    assert "x" * 20 in text
    assert "x" * 21 not in text


def test_render_state_other_falls_through_to_dim_for_unknown_status() -> None:
    state, info = _state_with_one_uf("AC", status="mystery")
    cell = _render_state_cell("AC", info, state, now=10.0)
    text = cell.markup
    assert "dim" in text
    assert "mystery" in text
    # None of the four known styles should leak through.
    assert "green" not in text
    assert "red" not in text
    assert "yellow" not in text
    assert "cyan" not in text


def test_build_state_grid_arranges_cells_in_four_column_rows() -> None:
    # 27 Brazilian UFs → ceil(27/4) = 7 rows.
    state = MonitorState()
    ufs = [f"U{i:02d}" for i in range(27)]
    for i, uf in enumerate(ufs):
        state.states[uf] = {
            "status": "ok",
            "started_at": 0.0,
            "last_seen": 0.0,
            "rows": i,
            "duration_s": 1.0,
        }
    grid = _build_state_grid(state, now=10.0)
    assert len(grid.columns) == 4
    assert grid.row_count == 7


# ── _build_progress — chunk UI applicability per pipeline shape ──────────


def test_build_progress_hides_chunk_states_bar_without_state_events() -> None:
    """COMEX/COMTRADE/BCB never emit state_* events — the 'Chunk states 0/27'
    bar must not render for them (it would sit frozen with ETA '?')."""
    from embrapa_commodities.monitor.render import _build_progress

    state = MonitorState()
    state.apply(_evt("pipeline_start", pipeline="comex", run_id="r1", chunks_total=4))
    state.apply(_evt("chunk_start", chunk_id="export-2024", chunk_n=1, chunk_total=4))

    progress = _build_progress(state, now=1000.0)

    assert len(progress.tasks) == 1  # chunks row only — no bogus states bar


def test_build_progress_shows_chunk_states_bar_for_uf_sweeping_pipelines() -> None:
    from embrapa_commodities.monitor.render import _build_progress

    state = MonitorState()
    state.apply(_evt("pipeline_start", pipeline="ibge", run_id="r1", chunks_total=2))
    state.apply(_evt("chunk_start", chunk_id="2020-2022", chunk_n=1, chunk_total=2))
    state.apply(_evt("state_start", state="SP"))

    progress = _build_progress(state, now=1000.0)

    assert len(progress.tasks) == 2


def test_build_progress_keeps_states_bar_across_chunk_boundaries() -> None:
    """saw_state_events is sticky: a fresh chunk resets the UF grid but the
    bar must not flicker away for IBGE-style pipelines."""
    from embrapa_commodities.monitor.render import _build_progress

    state = MonitorState()
    state.apply(_evt("pipeline_start", pipeline="ibge", run_id="r1", chunks_total=2))
    state.apply(_evt("chunk_start", chunk_id="2020-2022", chunk_n=1, chunk_total=2))
    state.apply(_evt("state_start", state="SP"))
    state.apply(_evt("state_end", state="SP", rows=10, duration_s=1.0))
    state.apply(_evt("chunk_end", chunk_id="2020-2022", rows=10, duration_s=2.0))
    state.apply(_evt("chunk_start", chunk_id="2023-2024", chunk_n=2, chunk_total=2))

    progress = _build_progress(state, now=1000.0)

    assert len(progress.tasks) == 2


def test_build_progress_shows_rows_unknown_until_reported() -> None:
    """COMEX/COMTRADE chunk_end events carry no rows field — the header must
    show 'rows ?' rather than a misleading 0."""
    from embrapa_commodities.monitor.render import _build_progress

    state = MonitorState()
    state.apply(_evt("pipeline_start", pipeline="comex", run_id="r1", chunks_total=2))
    state.apply(_evt("chunk_end", chunk_id="export-2024", duration_s=3.0))

    progress = _build_progress(state, now=1000.0)
    assert "[bold]?[/bold]" in progress.tasks[0].fields["extra"]

    state.apply(_evt("ingest_loaded", rows=120))
    progress = _build_progress(state, now=1000.0)
    assert "120" in progress.tasks[0].fields["extra"]


# ── _tail_jsonl — file tailing helper (P1 refactor coverage) ─────────────


def _write_jsonl(path: Path, events: list[dict]) -> int:
    """Append events to path, return the new end-of-file byte position."""
    with path.open("a", encoding="utf-8") as f:
        for ev in events:
            f.write(json.dumps(ev) + "\n")
        return f.tell()


def test_tail_jsonl_reads_all_events_from_start(tmp_path: Path) -> None:
    log = tmp_path / "run.jsonl"
    _write_jsonl(log, [{"event": "a"}, {"event": "b"}, {"event": "c"}])
    events, position = _tail_jsonl(log, last_position=0)
    assert [e["event"] for e in events] == ["a", "b", "c"]
    assert position == log.stat().st_size


def test_tail_jsonl_resumes_from_last_position(tmp_path: Path) -> None:
    log = tmp_path / "run.jsonl"
    _write_jsonl(log, [{"event": "first"}])
    _, position = _tail_jsonl(log, last_position=0)

    # New events appended after our last read should be the only ones returned.
    _write_jsonl(log, [{"event": "second"}, {"event": "third"}])
    events, new_position = _tail_jsonl(log, last_position=position)

    assert [e["event"] for e in events] == ["second", "third"]
    assert new_position == log.stat().st_size


def test_tail_jsonl_skips_blank_lines_and_invalid_json(tmp_path: Path) -> None:
    log = tmp_path / "run.jsonl"
    log.write_text(
        '{"event": "ok"}\n'
        "\n"  # blank
        "{not json}\n"  # malformed
        "   \n"  # whitespace-only
        '{"event": "ok2"}\n',
        encoding="utf-8",
    )
    events, _ = _tail_jsonl(log, last_position=0)
    assert [e["event"] for e in events] == ["ok", "ok2"]


def test_tail_jsonl_raises_filenotfound_for_missing_log(tmp_path: Path) -> None:
    log = tmp_path / "does-not-exist.jsonl"
    with pytest.raises(FileNotFoundError):
        _tail_jsonl(log, last_position=0)


# ── ETA computations + end-to-end render (coverage for builders) ─────────
#
# Function-local imports below keep the pre-commit "unused-import" hook from
# stripping them between iterations. They could move to the top once the test
# suite stabilises.


def _make_running_state() -> MonitorState:
    """Build a representative in-flight MonitorState the renderer can consume."""
    state = MonitorState()
    state.apply(
        _evt(
            "pipeline_start",
            pipeline="ibge",
            run_id="r1",
            chunks_total=3,
            params={"start_year": 2020, "end_year": 2024},
        )
    )
    state.apply(_evt("chunk_start", chunk_id="2020-2021", chunk_n=1, chunk_total=3))
    state.apply(_evt("state_start", state="SP"))
    state.apply(_evt("state_end", state="SP", rows=1000, duration_s=2.0))
    state.apply(_evt("state_start", state="MG"))
    state.apply(_evt("state_error", state="RJ", error="Read timed out"))
    state.apply(_evt("chunk_end", chunk_id="2020-2021", rows=1000, duration_s=10.0))
    state.apply(_evt("chunk_start", chunk_id="2022-2024", chunk_n=2, chunk_total=3))
    state.apply(_evt("state_start", state="BA"))
    state.apply(_evt("retry", state="BA", attempt=2, reason="timeout"))
    return state


def test_pipeline_eta_returns_none_before_first_chunk_completes() -> None:
    from embrapa_commodities.monitor import _pipeline_eta

    state = MonitorState()
    state.apply(_evt("pipeline_start", pipeline="ibge", run_id="r1", chunks_total=3))
    assert _pipeline_eta(state) is None


def test_pipeline_eta_uses_average_of_completed_chunks() -> None:
    from embrapa_commodities.monitor import _pipeline_eta

    state = MonitorState()
    state.apply(_evt("pipeline_start", pipeline="ibge", run_id="r1", chunks_total=3))
    state.apply(_evt("chunk_start", chunk_id="c1"))
    state.apply(_evt("chunk_end", chunk_id="c1", duration_s=20.0))
    # One chunk done at 20s, two remaining → ETA ≈ 40s (minus current-chunk burn = 0).
    eta = _pipeline_eta(state)
    assert eta is not None
    assert 35 <= eta <= 45


def test_pipeline_eta_zero_when_pipeline_ended() -> None:
    from embrapa_commodities.monitor import _pipeline_eta

    state = MonitorState()
    state.apply(_evt("pipeline_start", pipeline="ibge", run_id="r1", chunks_total=1))
    state.apply(_evt("pipeline_end", rows_total=0, duration_s=1.0))
    assert _pipeline_eta(state) == 0.0


def test_chunk_eta_none_when_no_active_chunk() -> None:
    from embrapa_commodities.monitor import _chunk_eta

    state = MonitorState()
    assert _chunk_eta(state) is None


def test_chunk_eta_none_when_no_state_durations_yet() -> None:
    from embrapa_commodities.monitor import _chunk_eta

    state = MonitorState()
    state.apply(_evt("chunk_start", chunk_id="c1"))
    # active chunk but no completed states → no median → ETA unknowable.
    assert _chunk_eta(state) is None


def test_chunk_eta_returns_positive_when_data_available() -> None:
    from embrapa_commodities.monitor import _chunk_eta

    state = MonitorState()
    state.apply(_evt("chunk_start", chunk_id="c1"))
    state.apply(_evt("state_end", state="SP", rows=100, duration_s=5.0))
    eta = _chunk_eta(state)
    assert eta is not None
    assert eta > 0


def test_render_produces_panel_for_running_pipeline(tmp_path: Path) -> None:
    """Smoke-level coverage for the full _render() composition path.

    Doesn't assert on visual content (Rich Panels are nested object trees);
    asserts the renderer doesn't crash on a representative state and that
    every builder it calls executes. This single test reaches _build_header,
    _build_progress, _build_active_line, _build_state_grid, _build_recent_panel,
    and _build_errors_panel in one shot.
    """
    from rich.panel import Panel

    from embrapa_commodities.monitor import _render

    state = _make_running_state()
    panel = _render(state, tmp_path / "fake-log.jsonl")
    assert isinstance(panel, Panel)
    # Title carries the log file basename.
    assert "fake-log.jsonl" in str(panel.title)


def test_render_handles_finished_pipeline(tmp_path: Path) -> None:
    """``_build_active_line`` has a separate branch for state.ended_at — cover it."""
    from rich.panel import Panel

    from embrapa_commodities.monitor import _render

    state = _make_running_state()
    state.apply(_evt("pipeline_end", rows_total=1000, duration_s=30.0))
    panel = _render(state, tmp_path / "fake-log.jsonl")
    assert isinstance(panel, Panel)


def test_render_handles_idle_pipeline_between_chunks(tmp_path: Path) -> None:
    """``_build_active_line`` third branch: no active chunk, not ended."""
    from rich.panel import Panel

    from embrapa_commodities.monitor import _render

    state = MonitorState()
    state.apply(_evt("pipeline_start", pipeline="ibge", run_id="r1", chunks_total=2))
    panel = _render(state, tmp_path / "fake-log.jsonl")
    assert isinstance(panel, Panel)


# ── run() — the live tail+render loop ────────────────────────────────────


def test_run_tails_renders_and_exits_on_pipeline_end(tmp_path: Path, monkeypatch) -> None:
    """run() tails the log, applies events, renders, and exits on pipeline_end."""
    from io import StringIO

    from rich.console import Console
    from rich.text import Text

    from embrapa_commodities.monitor import render

    monkeypatch.setattr(render.time, "sleep", lambda *a, **k: None)  # no real 1s pause
    rendered: list[MonitorState] = []

    def _spy(state: MonitorState, log_path: Path) -> Text:
        rendered.append(state)
        return Text("frame")

    monkeypatch.setattr(render, "_render", _spy)

    log = tmp_path / "run.jsonl"
    _write_log(
        log,
        [
            _evt("pipeline_start", pipeline="ibge", run_id="r1", chunks_total=1),
            _evt("chunk_start", chunk_id="2020", chunk_n=1, chunk_total=1),
            _evt("chunk_end", chunk_id="2020", chunk_n=1, chunk_total=1, duration_s=1.0),
            _evt("pipeline_end", duration_s=1.0, chunks_ok=1, chunks_failed=0),
        ],
    )
    render.run(
        log, follow=True, console=Console(file=StringIO(), force_terminal=False), tick_seconds=0.0
    )

    assert rendered, "run() never rendered a frame"
    assert rendered[-1].ended_at is not None  # saw pipeline_end and stopped


def test_run_reports_missing_log(tmp_path: Path) -> None:
    """A non-existent log path prints a clear error and returns (no crash)."""
    from io import StringIO

    from rich.console import Console

    from embrapa_commodities.monitor import render

    buf = StringIO()
    render.run(tmp_path / "absent.jsonl", console=Console(file=buf, force_terminal=False))
    assert "Log not found" in buf.getvalue()


def test_run_without_follow_renders_once(tmp_path: Path, monkeypatch) -> None:
    """follow=False renders the current state once and returns without looping."""
    from io import StringIO

    from rich.console import Console
    from rich.text import Text

    from embrapa_commodities.monitor import render

    monkeypatch.setattr(render.time, "sleep", lambda *a, **k: None)
    calls: list[int] = []

    def _spy(state: MonitorState, log_path: Path) -> Text:
        calls.append(1)
        return Text("f")

    monkeypatch.setattr(render, "_render", _spy)
    log = tmp_path / "once.jsonl"
    _write_log(log, [_evt("pipeline_start", pipeline="bcb", run_id="r2", chunks_total=0)])
    render.run(
        log, follow=False, console=Console(file=StringIO(), force_terminal=False), tick_seconds=0.0
    )

    assert calls  # rendered, then returned (no pipeline_end, no hang)
