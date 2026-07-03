"""Tests for the structured event-log observability layer."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

import pytest

from embrapa_dashboard import observability


@pytest.fixture
def isolated_log_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Point observability at a temp directory and reset module state per test."""
    monkeypatch.setenv("EMBRAPA_LOG_DIR", str(tmp_path))
    monkeypatch.setattr(observability, "_event_logger", None)
    monkeypatch.setattr(observability, "_current_run_id", None)
    monkeypatch.setattr(observability, "_current_log_path", None)
    return tmp_path


def test_init_run_creates_jsonl_log(isolated_log_dir: Path) -> None:
    run_id, path = observability.init_run("ibge")

    assert path.parent == isolated_log_dir
    assert path.name.startswith("ibge-")
    assert path.name.endswith(".jsonl")
    assert run_id in path.name


def test_emit_writes_json_line(isolated_log_dir: Path) -> None:
    _, path = observability.init_run("ibge")
    observability.emit("state_start", state="BA", state_code=29)
    observability.emit("state_end", state="BA", rows=1234, duration_s=5.2)

    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    payload = [json.loads(line) for line in lines]
    assert payload[0]["event"] == "state_start"
    assert payload[0]["state"] == "BA"
    assert payload[1]["event"] == "state_end"
    assert payload[1]["rows"] == 1234


def test_emit_is_noop_before_init_run(monkeypatch: pytest.MonkeyPatch) -> None:
    """Calling emit without init_run() must not crash — pipelines that opt-out of
    logging (single ingest commands) rely on this graceful fallback."""
    monkeypatch.setattr(observability, "_event_logger", None)
    observability.emit("anything", foo="bar")  # should not raise


def test_latest_log_path_filters_by_pipeline(isolated_log_dir: Path) -> None:
    # Two runs of different pipelines.
    _, ibge_path = observability.init_run("ibge")
    # Force a measurable mtime gap so the "newest first" assertion below
    # is deterministic on fast filesystems (Linux CI creates both files
    # within the same second otherwise — see test_list_log_paths_sorted_newest_first
    # which applies the same trick).
    os.utime(ibge_path, (ibge_path.stat().st_atime, ibge_path.stat().st_mtime - 100))
    _, bcb_path = observability.init_run("bcb")

    assert observability.latest_log_path("ibge") == ibge_path
    assert observability.latest_log_path("bcb") == bcb_path
    # Unfiltered: returns the most recently modified (bcb, since it was second).
    assert observability.latest_log_path() == bcb_path


def test_latest_log_path_does_not_prefix_collide_on_hyphenated_pipelines(
    isolated_log_dir: Path,
) -> None:
    """`--pipeline ibge` must NOT match ibge-batch / ibge-pam logs.

    Pipeline names themselves contain hyphens, so a bare `ibge-*.jsonl` glob
    would attach the monitor to whichever of ibge / ibge-batch / ibge-pam ran
    most recently. The filter anchors the run_id slug after the name instead.
    """
    _, ibge_path = observability.init_run("ibge")
    # Make the plain-ibge log the OLDEST so the buggy prefix glob would pick
    # one of the hyphenated siblings below instead.
    os.utime(ibge_path, (ibge_path.stat().st_atime, ibge_path.stat().st_mtime - 200))
    _, pam_path = observability.init_run("ibge-pam")
    os.utime(pam_path, (pam_path.stat().st_atime, pam_path.stat().st_mtime - 100))
    _, batch_path = observability.init_run("ibge-batch")

    assert observability.latest_log_path("ibge") == ibge_path
    assert observability.latest_log_path("ibge-pam") == pam_path
    assert observability.latest_log_path("ibge-batch") == batch_path


def test_latest_log_path_tolerates_vanished_candidate(
    isolated_log_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A log file pruned between glob() and stat() must not crash the lookup.

    Logs are explicitly prunable, so max(..., key=p.stat) could otherwise raise
    FileNotFoundError (TOCTOU). The vanished file is skipped and the remaining
    valid candidate is returned.
    """
    # Build two DISTINCT log files directly with valid run_id slugs and distinct
    # mtimes — init_run() stamps the run_id to the second, so two init_run("ibge")
    # calls in the same wall-clock second would collide on one filename and make
    # this test flaky. The "newer" file is the one we simulate as pruned.
    old_path = isolated_log_dir / "ibge-20260101T000000Z.jsonl"
    new_path = isolated_log_dir / "ibge-20260101T000100Z.jsonl"
    old_path.write_text("", encoding="utf-8")
    new_path.write_text("", encoding="utf-8")
    os.utime(old_path, (old_path.stat().st_atime, old_path.stat().st_mtime - 100))

    real_stat = Path.stat

    def flaky_stat(self: Path, *args: object, **kwargs: object) -> os.stat_result:
        # Simulate new_path being pruned just before its mtime is read.
        if self == new_path:
            raise FileNotFoundError(self)
        return real_stat(self, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", flaky_stat)

    # No crash; the surviving (older) candidate wins.
    assert observability.latest_log_path("ibge") == old_path


def test_list_log_paths_sorted_newest_first(isolated_log_dir: Path) -> None:
    _, first = observability.init_run("ibge")
    # Force a measurable mtime gap.
    os.utime(first, (first.stat().st_atime, first.stat().st_mtime - 100))
    _, second = observability.init_run("bcb")

    paths = observability.list_log_paths()

    assert paths[0] == second
    assert paths[1] == first


def test_log_dir_respects_env_var(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("EMBRAPA_LOG_DIR", str(tmp_path / "custom"))
    assert observability.log_dir() == tmp_path / "custom"


def test_init_run_closes_previous_handler_on_reinit(isolated_log_dir: Path) -> None:
    """Re-initialising the same pipeline name must CLOSE the stale handler, not
    just detach it. logging caches loggers by name, so without close() each
    re-init would leak an open FileHandler file. A unique pipeline name
    keeps this isolated from the logger cache other tests populate."""
    observability.init_run("leak-test")
    assert observability._event_logger is not None
    first_handler = observability._event_logger.handlers[0]
    first_stream = first_handler.stream  # capture now — close() sets .stream = None
    assert not first_stream.closed

    # Same name → init_run finds the cached logger's handler and must close it.
    observability.init_run("leak-test")

    assert first_stream.closed, "stale FileHandler file must be closed, not leaked"


def test_init_run_uses_non_rotating_handler(isolated_log_dir: Path) -> None:
    """The event log must never rotate mid-run.

    The monitor tails the file by byte offset (`_tail_jsonl`); a
    RotatingFileHandler rollover renames the live file and replaces it with an
    empty one, silently freezing the tail until the new file outgrows the
    stale offset. The handler therefore must be a PLAIN FileHandler.
    """
    observability.init_run("rotation-test")
    assert observability._event_logger is not None
    handler = observability._event_logger.handlers[0]
    assert type(handler) is logging.FileHandler
