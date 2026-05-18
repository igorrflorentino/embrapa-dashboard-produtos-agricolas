"""Tests for the structured event-log observability layer."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from embrapa_commodities import observability


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
    observability.init_run("ibge")
    ibge_path = observability.current_log_path()
    observability.init_run("bcb")
    bcb_path = observability.current_log_path()

    assert observability.latest_log_path("ibge") == ibge_path
    assert observability.latest_log_path("bcb") == bcb_path
    # Unfiltered: returns the most recently modified (bcb, since it was second).
    assert observability.latest_log_path() == bcb_path


def test_list_log_paths_sorted_newest_first(isolated_log_dir: Path) -> None:
    observability.init_run("ibge")
    first = observability.current_log_path()
    # Force a measurable mtime gap.
    os.utime(first, (first.stat().st_atime, first.stat().st_mtime - 100))
    observability.init_run("bcb")
    second = observability.current_log_path()

    paths = observability.list_log_paths()

    assert paths[0] == second
    assert paths[1] == first


def test_log_dir_respects_env_var(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("EMBRAPA_LOG_DIR", str(tmp_path / "custom"))
    assert observability.log_dir() == tmp_path / "custom"
