"""Pytest wrapper around the dashboard HTTP+callback smoke test.

Opt-in via ``make test-smoke`` (which selects ``-m smoke``). Excluded from the
default ``make test`` so contributors without live BigQuery credentials get a
fast, green unit-test run.

When opted in, the test **HARD-FAILS** on missing ``GCP_PROJECT_ID`` — silent
skips are exactly the pattern the 2026-05 audit flagged (P1, action item #4):
whoever invokes the smoke explicitly owes a configured environment, and a green
``make test-smoke`` should mean "live BQ + dashboard work", never "I didn't
have creds, so the test didn't actually run".

Source of truth for "did the dashboard work on this PR" is CI
(``.github/workflows/dashboard-smoke.yml``), which uses Workload Identity
Federation to inject the GCP credentials this test requires.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SMOKE_SCRIPT = REPO_ROOT / "scripts" / "dashboard_smoke.py"


def _load_smoke_module():
    """Load scripts/dashboard_smoke.py as a module.

    ``scripts/`` is not on sys.path (it's a CLI directory, not a package), so
    we import the file by path. Caches via sys.modules so repeated calls in
    the same session don't re-exec.
    """
    cached = sys.modules.get("dashboard_smoke")
    if cached is not None:
        return cached
    spec = importlib.util.spec_from_file_location("dashboard_smoke", SMOKE_SCRIPT)
    assert spec and spec.loader, f"cannot load {SMOKE_SCRIPT}"
    module = importlib.util.module_from_spec(spec)
    sys.modules["dashboard_smoke"] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.smoke
def test_dashboard_boots_and_renders_with_live_bigquery():
    """Boot the dashboard, force a live-BQ route render, assert every check passes.

    Reuses ``run_smoke()`` from the CLI script so this test and ``make
    dashboard-smoke`` exercise the *exact same* launch/check/teardown path.
    """
    if not os.environ.get("GCP_PROJECT_ID"):
        pytest.fail(
            "test-smoke requires GCP_PROJECT_ID and Application Default "
            "Credentials. This is a HARD FAIL, not a skip: whoever invoked "
            "the smoke test owes the environment (the 2026-05 audit flagged "
            "silent skips as P1). Set GCP_PROJECT_ID in your shell and run "
            "`gcloud auth application-default login`, then retry."
        )

    smoke = _load_smoke_module()
    results = smoke.run_smoke()

    failures = [(name, detail) for name, ok, detail in results if not ok]
    assert not failures, "dashboard smoke failed:\n" + "\n".join(
        f"  - {name}: {detail}" for name, detail in failures
    )
