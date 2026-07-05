"""Coverage-focused tests for the Typer CLI (`embrapa_dashboard.cli`).

Targets command bodies + error/edge branches not exercised by test_cli.py:
 - `ingest ibge-ppm` (the PPM source command, both happy + skipped paths)
 - `bcb-currency` "nothing new" branch
 - the `_echo_chunk_result` "skipped" status line (via an ibge-batch chunk that
   returns no rows)
 - COMTRADE quota exhaustion WITH a genuine (non-quota) chunk failure → exit 1
 - `_reconcile_ibge` generic-exception branch (a non-BadParameter failure)
 - `discover ibge-periods`
 - `monitor --list` rendering actual log rows
 - the Curadoria lifecycle commands `mark-orphans` / `purge-orphan` and the
   `_with_webapp_context` helper (missing-extra + happy paths)

Style mirrors tests/test_cli.py: CliRunner.invoke + monkeypatching the pipeline
/ serving functions; no real ingestion or GCP.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock

import pytest
import typer
from typer.testing import CliRunner

from embrapa_dashboard import cli
from embrapa_dashboard.config import Settings

runner = CliRunner()


@pytest.fixture
def settings() -> Settings:
    return Settings(
        gcp_project_id="test-project",
        gcs_bucket="test-bucket",
        ibge_start_year=2020,
        ibge_end_year=2020,
        ibge_product_codes="3405",
        bcb_inflation_series="433:IPCA",
        bcb_currency_series="3694:USD",
        _env_file=None,
    )  # type: ignore[call-arg]


@pytest.fixture(autouse=True)
def _silence_observability(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Redirect the event-log directory and stub `emit` so no JSONL is written."""
    monkeypatch.setenv("EMBRAPA_LOG_DIR", str(tmp_path / "logs"))
    monkeypatch.setattr(
        cli.observability,
        "init_run",
        lambda pipeline: ("test-run-id", tmp_path / f"{pipeline}.jsonl"),
    )
    monkeypatch.setattr(cli.observability, "emit", lambda *a, **kw: None)


# ─── ingest ibge-ppm (lines 255-272) ───────────────────────────────────────────
def test_ingest_ibge_ppm_dispatches_and_prints_destination(
    monkeypatch: pytest.MonkeyPatch, settings: Settings
) -> None:
    """`ingest ibge-ppm` dispatches to ppm_pipeline.run with delta defaults and
    surfaces the loaded destination (both SIDRA tables behind one banco)."""
    pipeline_run = MagicMock(return_value="proj.bronze_ibge.sidra_t3939_raw")
    monkeypatch.setattr(cli, "get_settings", lambda: settings)
    monkeypatch.setattr(cli.ppm_pipeline, "run", pipeline_run)

    result = runner.invoke(cli.app, ["ingest", "ibge-ppm"])

    assert result.exit_code == 0, result.output
    pipeline_run.assert_called_once_with(settings, full=False, from_raw=False)
    assert "IBGE PPM bronze loaded" in result.output
    assert "proj.bronze_ibge.sidra_t3939_raw" in result.output


def test_ingest_ibge_ppm_full_flag_propagates(
    monkeypatch: pytest.MonkeyPatch, settings: Settings
) -> None:
    pipeline_run = MagicMock(return_value="proj.bronze_ibge.sidra_t3939_raw")
    monkeypatch.setattr(cli, "get_settings", lambda: settings)
    monkeypatch.setattr(cli.ppm_pipeline, "run", pipeline_run)

    result = runner.invoke(cli.app, ["ingest", "ibge-ppm", "--full"])

    assert result.exit_code == 0, result.output
    pipeline_run.assert_called_once_with(settings, full=True, from_raw=False)


def test_ingest_ibge_ppm_warns_when_pipeline_returns_empty(
    monkeypatch: pytest.MonkeyPatch, settings: Settings
) -> None:
    """An empty return means SIDRA had nothing new — print a hint, not a crash."""
    monkeypatch.setattr(cli, "get_settings", lambda: settings)
    monkeypatch.setattr(cli.ppm_pipeline, "run", lambda s, full=False, from_raw=False: "")

    result = runner.invoke(cli.app, ["ingest", "ibge-ppm"])

    assert result.exit_code == 0
    assert "skipped" in result.output
    assert "PPM_END_YEAR" in result.output


# ─── bcb-currency "nothing new" branch (line 330) ───────────────────────────────
def test_ingest_bcb_currency_empty_returns_friendly_message(
    monkeypatch: pytest.MonkeyPatch, settings: Settings
) -> None:
    monkeypatch.setattr(cli, "get_settings", lambda: settings)
    monkeypatch.setattr(cli.bcb_currency, "run", lambda s, full, from_raw=False: "")

    result = runner.invoke(cli.app, ["ingest", "bcb-currency"])

    assert result.exit_code == 0
    assert "nothing new" in result.output


# ─── _echo_chunk_result "skipped" status line (line 115) ────────────────────────
def test_ingest_ibge_batch_prints_skipped_line_when_chunk_returns_no_rows(
    monkeypatch: pytest.MonkeyPatch, settings: Settings
) -> None:
    """An ibge-batch chunk whose pipeline returns "" is recorded as `skipped`,
    exercising the dim "·" result line in _echo_chunk_result."""
    settings.ibge_start_year = 2010
    settings.ibge_end_year = 2010  # single chunk
    monkeypatch.setattr(cli, "get_settings", lambda: settings)
    monkeypatch.setattr(cli, "recommended_chunk_years", lambda n_products: 1)
    monkeypatch.setattr(cli, "resolve_clients", lambda s: (MagicMock(), MagicMock()))
    # Empty return → the chunk is "skipped (SIDRA returned no rows)".
    monkeypatch.setattr(cli.ibge_pipeline, "run", lambda s, **kw: "")

    result = runner.invoke(cli.app, ["ingest", "ibge-batch"])

    assert result.exit_code == 0, result.output
    assert "skipped" in result.output


# ─── COMTRADE quota + genuine chunk failure → exit 1 (lines 569-571) ────────────
def _wire_comtrade(monkeypatch: pytest.MonkeyPatch, settings: Settings) -> Settings:
    settings.comtrade_api_key = "k"
    settings.comtrade_reporters = "76,842"  # explicit list → no list_reporters() call
    monkeypatch.setattr(cli, "get_settings", lambda: settings)
    monkeypatch.setattr(cli, "resolve_clients", lambda s: (MagicMock(), MagicMock()))
    monkeypatch.setattr(cli.comtrade_pipeline, "ensure_destination", lambda s, c: "p.d.t")
    monkeypatch.setattr(cli.comtrade_pipeline, "bronze_one", lambda *a, **k: "p.d.t")
    return settings


def test_ingest_comtrade_quota_plus_genuine_failure_exits_1(
    monkeypatch: pytest.MonkeyPatch, settings: Settings
) -> None:
    """When the run stops on quota BUT a non-quota chunk also genuinely failed, the
    command must list the failed chunk(s) and exit 1 (the alert must still fire)."""
    from embrapa_dashboard.comtrade.client import ComtradeQuotaError

    _wire_comtrade(monkeypatch, settings)
    settings.comtrade_start_year = 2022
    settings.comtrade_end_year = 2023  # 2 years × 1 batch = 2 chunks

    def first_fails_then_quota(_s: Settings, year: int, _batch: object, **kwargs: object) -> bool:
        if year == 2022:
            raise RuntimeError("genuine non-quota failure")  # recorded as a failed chunk
        raise ComtradeQuotaError("quota exhausted — re-run to resume")

    monkeypatch.setattr(cli.comtrade_pipeline, "sync_raw", first_fails_then_quota)

    result = runner.invoke(cli.app, ["ingest", "comtrade"])

    assert result.exit_code == 1, result.output
    assert "quota exhausted" in result.output
    # The genuine 2022 failure is listed in the failure tail.
    assert "2022" in result.output


# ─── _reconcile_ibge generic-exception branch (lines 686-688) ───────────────────
def test_ingest_reconcile_records_ibge_setup_failure(
    monkeypatch: pytest.MonkeyPatch, settings: Settings
) -> None:
    """A non-BadParameter exception raised while setting up the IBGE batch leg (e.g.
    resolve_clients fails) is caught and recorded as an IBGE source failure (exit 1),
    while the remaining full sources still run."""
    settings.ibge_start_year = 2010
    settings.ibge_end_year = 2010
    monkeypatch.setattr(cli, "get_settings", lambda: settings)
    monkeypatch.setattr(cli, "recommended_chunk_years", lambda n_products: 1)

    def boom_clients(_s: Settings) -> tuple:
        raise RuntimeError("ADC unavailable")

    monkeypatch.setattr(cli, "resolve_clients", boom_clients)

    ran_other: list[str] = []
    monkeypatch.setattr(cli.pam_pipeline, "run", lambda s, full: ran_other.append("pam") or "")
    monkeypatch.setattr(cli.ppm_pipeline, "run", lambda s, full: ran_other.append("ppm") or "")
    monkeypatch.setattr(
        cli.bcb_inflation, "run", lambda s, full: ran_other.append("inflation") or ""
    )
    monkeypatch.setattr(cli.bcb_currency, "run", lambda s, full: ran_other.append("currency") or "")
    monkeypatch.setattr(cli.comex_pipeline, "run", lambda s, full: ran_other.append("comex") or "")

    result = runner.invoke(cli.app, ["ingest", "reconcile"])

    assert result.exit_code == 1, result.output
    assert "IBGE PEVS failed" in result.output
    # The full-source leg still ran despite the IBGE setup failure.
    assert ran_other == ["pam", "ppm", "inflation", "currency", "comex"]


# ─── discover ibge-periods (lines 762-768) ──────────────────────────────────────
def test_discover_ibge_periods_prints_year_span(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli.discover, "list_ibge_periods", lambda table_id: [1986, 1990, 2024])

    result = runner.invoke(cli.app, ["discover", "ibge-periods", "--table-id", "289"])

    assert result.exit_code == 0, result.output
    assert "3 years available" in result.output
    assert "1986" in result.output
    assert "2024" in result.output
    assert "IBGE_START_YEAR=1986" in result.output


def test_discover_ibge_periods_empty_exits_1(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli.discover, "list_ibge_periods", lambda table_id: [])

    result = runner.invoke(cli.app, ["discover", "ibge-periods", "--table-id", "999"])

    assert result.exit_code == 1
    assert "no periods" in result.output


# ─── monitor --list with real rows (lines 826-836) ──────────────────────────────
def test_monitor_list_renders_log_rows(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """`monitor --list` with at least one log path renders the table (modified / size
    / path columns) and returns 0 — exercising the per-path stat() row loop."""
    log = tmp_path / "ibge-XYZ.jsonl"
    log.write_text('{"event":"pipeline_start"}\n', encoding="utf-8")
    monkeypatch.setattr(cli.observability, "list_log_paths", lambda: [log])
    monkeypatch.setattr(cli.observability, "log_dir", lambda: tmp_path)

    result = runner.invoke(cli.app, ["monitor", "--list"])

    assert result.exit_code == 0, result.output
    # The table header + a stat()-derived size column prove the per-path row loop ran
    # (Rich truncates the long temp path, so we assert on stable, non-truncated text).
    assert "Run logs" in result.output
    assert "KB" in result.output  # the "<size> KB" cell rendered for the row


# ─── Curadoria lifecycle: mark-orphans (lines 937-940) ──────────────────────────
def _bypass_webapp_context(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make `_with_webapp_context(fn)` simply call fn() — no flask app context."""
    monkeypatch.setattr(cli, "_with_webapp_context", lambda fn: fn())


def test_mark_orphans_reports_counts(monkeypatch: pytest.MonkeyPatch) -> None:
    """`mark-orphans` dispatches to catalog_lifecycle.auto_mark_orphans (imported at
    call time) and prints the detected/newly_marked/already_marked summary."""
    from embrapa_dashboard.serving import catalog_lifecycle

    _bypass_webapp_context(monkeypatch)
    monkeypatch.setattr(
        catalog_lifecycle,
        "auto_mark_orphans",
        lambda: {"detected": 3, "newly_marked": 2, "already_marked": 1},
    )

    result = runner.invoke(cli.app, ["mark-orphans"])

    assert result.exit_code == 0, result.output
    assert "detected=3" in result.output
    assert "newly_marked=2" in result.output
    assert "already_marked=1" in result.output


# ─── Curadoria lifecycle: purge-orphan (lines 959-992) ──────────────────────────
def test_purge_orphan_prints_plan_with_backup_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    """The default (no --mark-purged) path prints the human-runnable purge plan with a
    healthy backup status and the DELETE statements."""
    from embrapa_dashboard.serving import catalog_lifecycle

    _bypass_webapp_context(monkeypatch)
    monkeypatch.setattr(
        catalog_lifecycle,
        "purge_plan",
        lambda banco, code: {
            "banco": banco,
            "code": code,
            "statements": ["DELETE FROM `proj.gold.t` WHERE codigo LIKE '3405%';"],
            "backup_ok": True,
            "backup_msg": "snapshot 1h old",
        },
    )

    result = runner.invoke(cli.app, ["purge-orphan", "--banco", "pevs", "--code", "3405"])

    assert result.exit_code == 0, result.output
    assert "Purge plan" in result.output
    assert "backup OK" in result.output
    assert "DELETE FROM" in result.output
    assert "--mark-purged" in result.output


def test_purge_orphan_warns_when_backup_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """The backup-absent branch warns in red before printing the DELETEs."""
    from embrapa_dashboard.serving import catalog_lifecycle

    _bypass_webapp_context(monkeypatch)
    monkeypatch.setattr(
        catalog_lifecycle,
        "purge_plan",
        lambda banco, code: {
            "banco": banco,
            "code": code,
            "statements": ["DELETE FROM `proj.gold.t` WHERE codigo LIKE '3405%';"],
            "backup_ok": False,
            "backup_msg": "no snapshot found",
        },
    )

    result = runner.invoke(cli.app, ["purge-orphan", "--banco", "pevs", "--code", "3405"])

    assert result.exit_code == 0, result.output
    assert "backup MISSING/STALE" in result.output
    assert "Back up Gold BEFORE" in result.output


def test_purge_orphan_exits_1_on_value_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """A ValueError from purge_plan (not Descontinuado / malformed code) → exit 1."""
    from embrapa_dashboard.serving import catalog_lifecycle

    _bypass_webapp_context(monkeypatch)

    def boom(banco: str, code: str) -> dict:
        raise ValueError("not marked Descontinuado")

    monkeypatch.setattr(catalog_lifecycle, "purge_plan", boom)

    result = runner.invoke(cli.app, ["purge-orphan", "--banco", "pevs", "--code", "3405"])

    assert result.exit_code == 1
    assert "not marked Descontinuado" in result.output


def test_purge_orphan_mark_purged_records_event(monkeypatch: pytest.MonkeyPatch) -> None:
    """With --mark-purged, the command records the terminal audit event via
    mark_purged and prints the confirmation (the dedup-aware verb)."""
    from embrapa_dashboard.serving import catalog_lifecycle

    _bypass_webapp_context(monkeypatch)
    captured: dict = {}

    def fake_mark_purged(banco: str, code: str, *, edited_by: str) -> dict:
        captured.update(banco=banco, code=code, edited_by=edited_by)
        return {"deduped": False}

    monkeypatch.setattr(catalog_lifecycle, "mark_purged", fake_mark_purged)

    result = runner.invoke(
        cli.app,
        ["purge-orphan", "--banco", "pevs", "--code", "3405", "--mark-purged", "--author", "alice"],
    )

    assert result.exit_code == 0, result.output
    assert captured == {"banco": "pevs", "code": "3405", "edited_by": "alice"}
    assert "recorded" in result.output
    assert "by alice" in result.output


def test_purge_orphan_mark_purged_dedup_verb(monkeypatch: pytest.MonkeyPatch) -> None:
    """A deduped mark_purged result swaps the verb to 'already recorded'."""
    from embrapa_dashboard.serving import catalog_lifecycle

    _bypass_webapp_context(monkeypatch)
    monkeypatch.setattr(
        catalog_lifecycle,
        "mark_purged",
        lambda banco, code, *, edited_by: {"deduped": True},
    )

    result = runner.invoke(
        cli.app, ["purge-orphan", "--banco", "pevs", "--code", "3405", "--mark-purged"]
    )

    assert result.exit_code == 0, result.output
    assert "already recorded" in result.output


# ─── _with_webapp_context helper (lines 920-929) ────────────────────────────────
def test_with_webapp_context_happy_path_runs_fn_in_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the webapi extra is importable, the helper enters the app context and
    returns the callback's result."""
    entered: list[bool] = []

    class _Ctx:
        def __enter__(self):
            entered.append(True)
            return self

        def __exit__(self, *exc):
            return False

    fake_app = SimpleNamespace(app_context=lambda: _Ctx())
    fake_module = ModuleType("embrapa_dashboard.webapi.app")
    fake_module.app = fake_app  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "embrapa_dashboard.webapi.app", fake_module)

    result = cli._with_webapp_context(lambda: "done")

    assert result == "done"
    assert entered == [True]


def test_with_webapp_context_missing_extra_exits_1(monkeypatch: pytest.MonkeyPatch) -> None:
    """When the webapi extra is NOT installed, importing the app raises
    ModuleNotFoundError → the helper prints the hint and raises typer.Exit(1)."""
    import builtins

    real_import = builtins.__import__

    def fake_import(name: str, *args: object, **kwargs: object):
        if name == "embrapa_dashboard.webapi.app" or name.startswith("embrapa_dashboard.webapi"):
            raise ModuleNotFoundError("No module named 'flask'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    with pytest.raises(typer.Exit) as excinfo:
        cli._with_webapp_context(lambda: "unused")

    assert excinfo.value.exit_code == 1


# ─── authorization allowlists CLI (editors / attribute editors) + catalog-seed-from-env ──


def test_editors_add_authorizes(monkeypatch: pytest.MonkeyPatch) -> None:
    """`editors add` dispatches to curation.add_catalog_editor (resource defaults to
    produto_catalog) and reports the authorized email."""
    from embrapa_dashboard.serving import curation

    _bypass_webapp_context(monkeypatch)
    seen: dict = {}
    monkeypatch.setattr(
        curation,
        "add_catalog_editor",
        lambda resource, email, added_by="cli": (
            seen.update(resource=resource, email=email) or email.strip().lower()
        ),
    )
    result = runner.invoke(cli.app, ["editors", "add", "--email", "Alice@Embrapa.BR"])
    assert result.exit_code == 0, result.output
    assert "editor authorized" in result.output
    assert seen["resource"] == "produto_catalog"


def test_editors_remove_reports_count(monkeypatch: pytest.MonkeyPatch) -> None:
    from embrapa_dashboard.serving import curation

    _bypass_webapp_context(monkeypatch)
    monkeypatch.setattr(curation, "remove_catalog_editor", lambda resource, email: 1)
    result = runner.invoke(cli.app, ["editors", "remove", "--email", "alice@embrapa.br"])
    assert result.exit_code == 0, result.output
    assert "removed 1 row" in result.output


def test_attribute_editors_add_authorizes(monkeypatch: pytest.MonkeyPatch) -> None:
    from embrapa_dashboard.serving import research_inputs

    _bypass_webapp_context(monkeypatch)
    monkeypatch.setattr(
        research_inputs, "add_attribute_editor", lambda email, added_by="cli": email.strip().lower()
    )
    result = runner.invoke(cli.app, ["attribute-editors", "add", "--email", "bob@x.br"])
    assert result.exit_code == 0, result.output
    assert "attribute editor authorized" in result.output


def test_catalog_seed_from_env_reports_counts(monkeypatch: pytest.MonkeyPatch) -> None:
    """`catalog-seed-from-env` builds an IAP-author header and prints the seeded/skipped
    summary from curation.seed_catalog_from_env."""
    from embrapa_dashboard.serving import curation

    _bypass_webapp_context(monkeypatch)
    seen: dict = {}

    def _seed(headers, agrupamento_default=None):
        seen["headers"] = headers
        return {"seeded": 28, "skipped": 0}

    monkeypatch.setattr(curation, "seed_catalog_from_env", _seed)
    result = runner.invoke(cli.app, ["catalog-seed-from-env", "--author", "me@x.br"])
    assert result.exit_code == 0, result.output
    assert "seeded=28" in result.output
    assert "me@x.br" in seen["headers"]["X-Goog-Authenticated-User-Email"]
