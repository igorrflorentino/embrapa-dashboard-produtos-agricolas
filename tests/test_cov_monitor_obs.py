"""Coverage top-up for the monitor (state/render) + observability edge branches.

Targets the small error/edge paths the main suites don't exercise:
  * state.py 40-41  — ``_parse_ts`` falls back to ``time.time()`` on a bad ISO string.
  * state.py 413    — ``_pipeline_eta`` returns None when no chunks remain but no
                      pipeline_end has arrived yet.
  * state.py 436    — ``_chunk_eta`` returns 0.0 when all 27 chunk states finished.
  * render.py 196   — ``_build_active_line`` "Pipeline finished" branch (ended, no
                      active chunk).
  * render.py 304-305 — ``run`` breaks cleanly when the log vanishes mid-loop
                      (FileNotFoundError out of ``_tail_jsonl``).
  * render.py 317-319 — ``run`` reaches ``time.sleep(tick_seconds)`` on a follow
                      iteration with no pipeline_end, and the ``KeyboardInterrupt``
                      handler prints the stop notice.

Style mirrors tests/test_monitor.py + tests/test_observability.py (the ``_evt``
event builder, tmp_path logs, monkeypatch on ``render.time.sleep``, the
``isolated_log_dir`` fixture pattern).
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from io import StringIO
from pathlib import Path

import pytest
from rich.console import Console
from rich.text import Text

from embrapa_dashboard import observability
from embrapa_dashboard.monitor import MonitorState, render
from embrapa_dashboard.monitor.render import _build_active_line
from embrapa_dashboard.monitor.state import (
    STATES_PER_CHUNK,
    _chunk_eta,
    _parse_ts,
    _pipeline_eta,
)


def _evt(event: str, **fields: object) -> dict:
    return {
        "ts": datetime.now(UTC).isoformat(),
        "event": event,
        **fields,
    }


# ── state.py 40-41 — _parse_ts fallback on malformed/typed-wrong input ────


def test_parse_ts_falls_back_on_unparseable_string() -> None:
    """A non-ISO string raises ValueError inside fromisoformat → fall back to now."""
    before = time.time()
    result = _parse_ts("not-a-timestamp")
    after = time.time()
    # The fallback returns the current wall-clock, not a parsed epoch.
    assert before <= result <= after


def test_parse_ts_falls_back_on_non_string_input() -> None:
    """A non-string (TypeError path) also takes the fallback rather than crashing."""
    before = time.time()
    result = _parse_ts(None)  # type: ignore[arg-type]
    after = time.time()
    assert before <= result <= after


# ── state.py 413 — _pipeline_eta: all chunks accounted for, no pipeline_end ─


def test_pipeline_eta_none_when_all_chunks_done_but_pipeline_not_ended() -> None:
    """chunks_total reached by chunks_done (remaining == 0) yet no pipeline_end →
    the "assume imminent" branch returns None instead of an ETA."""
    state = MonitorState()
    state.apply(_evt("pipeline_start", pipeline="ibge", run_id="r1", chunks_total=1))
    state.apply(_evt("chunk_start", chunk_id="c1"))
    state.apply(_evt("chunk_end", chunk_id="c1", duration_s=12.0))
    # 1/1 chunks done, chunk_durations populated, but no pipeline_end event.
    assert state.ended_at is None
    assert state.chunk_durations  # has fuel → not the "no data" early return
    assert _pipeline_eta(state) is None


# ── state.py 436 — _chunk_eta: remaining == 0 returns 0.0 ──────────────────


def test_chunk_eta_zero_when_all_states_finished() -> None:
    """With an active chunk and all 27 UFs finished, remaining == 0 → ETA 0.0."""
    state = MonitorState()
    state.apply(_evt("chunk_start", chunk_id="c1"))
    # Finish all 27 states so _states_finished_in_chunk == STATES_PER_CHUNK.
    for i in range(STATES_PER_CHUNK):
        state.apply(_evt("state_end", state=f"U{i:02d}", rows=1, duration_s=2.0))
    assert state.active_chunk == "c1"
    assert _chunk_eta(state) == 0.0


# ── render.py 196 — _build_active_line "Pipeline finished" branch ──────────


def test_build_active_line_shows_finished_when_ended_and_no_active_chunk() -> None:
    """ended_at set + active_chunk cleared → the green "Pipeline finished" line."""
    state = MonitorState()
    state.apply(_evt("pipeline_start", pipeline="ibge", run_id="r1", chunks_total=1))
    state.apply(_evt("chunk_start", chunk_id="c1"))
    # chunk_end clears active_chunk/active_chunk_started_at.
    state.apply(_evt("chunk_end", chunk_id="c1", duration_s=1.0))
    state.apply(_evt("pipeline_end", duration_s=1.0, chunks_ok=1, chunks_failed=0))
    assert state.active_chunk is None
    assert state.ended_at is not None

    line = _build_active_line(state, now=time.time())
    assert isinstance(line, Text)
    assert "Pipeline finished" in line.markup


# ── render.py 304-305 — run() breaks on a log that vanishes mid-loop ───────


def test_run_breaks_when_log_vanishes_midloop(tmp_path: Path, monkeypatch) -> None:
    """If _tail_jsonl raises FileNotFoundError on a follow iteration, run() must
    break the loop cleanly instead of propagating the error."""
    monkeypatch.setattr(render.time, "sleep", lambda *a, **k: None)

    log = tmp_path / "vanishing.jsonl"
    # A live (in-progress) log: no pipeline_end, so the loop would keep ticking.
    log.write_text("", encoding="utf-8")

    calls = {"n": 0}
    real_tail = render._tail_jsonl

    def _flaky_tail(path: Path, last_position: int):
        calls["n"] += 1
        if calls["n"] == 1:
            return real_tail(path, last_position)  # first pass succeeds (empty)
        raise FileNotFoundError(path)  # second pass: file pruned mid-run

    monkeypatch.setattr(render, "_tail_jsonl", _flaky_tail)

    # follow=True so the loop iterates again and hits the vanished file.
    render.run(
        log,
        follow=True,
        console=Console(file=StringIO(), force_terminal=False),
        tick_seconds=0.0,
    )

    assert calls["n"] >= 2  # looped at least once more and hit the FileNotFoundError


# ── render.py 317 — run() reaches time.sleep(tick_seconds) on a follow tick ─


def test_run_follow_sleeps_then_stops_via_keyboard_interrupt(tmp_path: Path, monkeypatch) -> None:
    """A live log (no pipeline_end) drives run() past ``time.sleep(tick_seconds)``;
    we raise KeyboardInterrupt from sleep to also cover the Ctrl-C handler
    (render.py 318-319) and return cleanly."""
    log = tmp_path / "live.jsonl"
    log.write_text("", encoding="utf-8")  # empty, in-progress run

    sleeps: list[float] = []

    def _fake_sleep(seconds: float = 0.0) -> None:
        sleeps.append(seconds)
        # First tick-sleep proves line 317 ran; then simulate Ctrl-C to exit.
        raise KeyboardInterrupt

    monkeypatch.setattr(render.time, "sleep", _fake_sleep)

    buf = StringIO()
    render.run(
        log,
        follow=True,
        console=Console(file=buf, force_terminal=False),
        tick_seconds=0.5,
    )

    # The per-tick sleep was reached with the configured interval (line 317) ...
    assert sleeps == [0.5]
    # ... and the KeyboardInterrupt handler printed the stop notice (lines 318-319).
    assert "Monitor stopped" in buf.getvalue()


# ── observability.py 98, 105, 118, 125 — empty-dir / no-candidate branches ─


@pytest.fixture
def isolated_log_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Point observability at a temp directory and reset module state per test.

    Mirrors tests/test_observability.py::isolated_log_dir.
    """
    monkeypatch.setenv("EMBRAPA_LOG_DIR", str(tmp_path))
    monkeypatch.setattr(observability, "_event_logger", None)
    monkeypatch.setattr(observability, "_current_run_id", None)
    monkeypatch.setattr(observability, "_current_log_path", None)
    return tmp_path


def test_latest_log_path_returns_none_when_dir_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """observability.py:98 — no log directory at all → None."""
    missing = tmp_path / "does-not-exist"
    monkeypatch.setenv("EMBRAPA_LOG_DIR", str(missing))
    assert not missing.exists()
    assert observability.latest_log_path() is None
    assert observability.latest_log_path("ibge") is None


def test_latest_log_path_returns_none_when_no_candidates(isolated_log_dir: Path) -> None:
    """observability.py:105 — dir exists but holds no matching .jsonl → None."""
    # Directory exists (the fixture created tmp_path) but is empty of logs.
    assert isolated_log_dir.exists()
    assert observability.latest_log_path() is None
    assert observability.latest_log_path("ibge") is None


def test_latest_log_path_returns_none_when_all_candidates_vanish(
    isolated_log_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """observability.py:118 — every globbed candidate vanishes before stat() →
    ``rated`` is empty → None (not a crash)."""
    only_path = isolated_log_dir / "ibge-20260101T000000Z.jsonl"
    only_path.write_text("", encoding="utf-8")

    real_stat = Path.stat

    def _all_vanished(self: Path, *args: object, **kwargs: object):
        if self.suffix == ".jsonl":
            raise FileNotFoundError(self)
        return real_stat(self, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", _all_vanished)

    assert observability.latest_log_path("ibge") is None


def test_list_log_paths_returns_empty_when_dir_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """observability.py:125 — no log directory → empty list."""
    missing = tmp_path / "absent"
    monkeypatch.setenv("EMBRAPA_LOG_DIR", str(missing))
    assert not missing.exists()
    assert observability.list_log_paths() == []
