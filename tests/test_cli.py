"""Tests for the Typer-based CLI dispatcher.

We mock the underlying pipeline calls; the goal is to confirm:
 1. each command parses its arguments correctly, and
 2. dispatches to the right function with the right values.

We do NOT exercise the real ingestion logic here — separate
test_ibge_pipeline / test_bcb_*_pipeline files cover that surface.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from embrapa_commodities import cli
from embrapa_commodities.config import Settings

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


# ─── ingest ibge ─────────────────────────────────────────────────────────────
def test_ingest_ibge_dispatches_and_prints_destination(
    monkeypatch: pytest.MonkeyPatch, settings: Settings
) -> None:
    pipeline_run = MagicMock(return_value="proj.bronze_ibge.sidra_t289_raw")
    monkeypatch.setattr(cli, "get_settings", lambda: settings)
    monkeypatch.setattr(cli.ibge_pipeline, "run", pipeline_run)

    result = runner.invoke(cli.app, ["ingest", "ibge"])

    assert result.exit_code == 0, result.output
    pipeline_run.assert_called_once_with(settings, from_raw=False)
    assert "IBGE bronze loaded" in result.output
    assert "proj.bronze_ibge.sidra_t289_raw" in result.output


def test_ingest_ibge_warns_when_pipeline_returns_empty(
    monkeypatch: pytest.MonkeyPatch, settings: Settings
) -> None:
    """An empty return value means SIDRA had nothing — print a hint, not a crash."""
    monkeypatch.setattr(cli, "get_settings", lambda: settings)
    monkeypatch.setattr(cli.ibge_pipeline, "run", lambda s, from_raw=False: "")

    result = runner.invoke(cli.app, ["ingest", "ibge"])

    assert result.exit_code == 0
    assert "skipped" in result.output
    assert "IBGE_END_YEAR" in result.output


def test_ingest_ibge_propagates_pipeline_error(
    monkeypatch: pytest.MonkeyPatch, settings: Settings
) -> None:
    monkeypatch.setattr(cli, "get_settings", lambda: settings)

    def boom(_settings: Settings, from_raw: bool = False) -> str:
        raise RuntimeError("sidra exploded")

    monkeypatch.setattr(cli.ibge_pipeline, "run", boom)

    result = runner.invoke(cli.app, ["ingest", "ibge"])

    assert result.exit_code != 0
    assert isinstance(result.exception, RuntimeError)


# ─── ingest bcb-inflation ────────────────────────────────────────────────────
def test_ingest_bcb_inflation_delta_by_default(
    monkeypatch: pytest.MonkeyPatch, settings: Settings
) -> None:
    bcb_run = MagicMock(return_value="proj.bronze_bcb.inflation_series_raw")
    monkeypatch.setattr(cli, "get_settings", lambda: settings)
    monkeypatch.setattr(cli.bcb_inflation, "run", bcb_run)

    result = runner.invoke(cli.app, ["ingest", "bcb-inflation"])

    assert result.exit_code == 0, result.output
    bcb_run.assert_called_once_with(settings, full=False, from_raw=False)
    assert "BCB inflation bronze loaded" in result.output


def test_ingest_bcb_inflation_full_flag_propagates(
    monkeypatch: pytest.MonkeyPatch, settings: Settings
) -> None:
    bcb_run = MagicMock(return_value="proj.bronze_bcb.inflation_series_raw")
    monkeypatch.setattr(cli, "get_settings", lambda: settings)
    monkeypatch.setattr(cli.bcb_inflation, "run", bcb_run)

    result = runner.invoke(cli.app, ["ingest", "bcb-inflation", "--full"])

    assert result.exit_code == 0, result.output
    bcb_run.assert_called_once_with(settings, full=True, from_raw=False)


def test_ingest_bcb_inflation_empty_returns_friendly_message(
    monkeypatch: pytest.MonkeyPatch, settings: Settings
) -> None:
    monkeypatch.setattr(cli, "get_settings", lambda: settings)
    monkeypatch.setattr(cli.bcb_inflation, "run", lambda s, full, from_raw=False: "")

    result = runner.invoke(cli.app, ["ingest", "bcb-inflation"])

    assert result.exit_code == 0
    assert "nothing new" in result.output


# ─── ingest bcb-currency ─────────────────────────────────────────────────────
def test_ingest_bcb_currency_delta_by_default(
    monkeypatch: pytest.MonkeyPatch, settings: Settings
) -> None:
    bcb_run = MagicMock(return_value="proj.bronze_bcb.currency_series_raw")
    monkeypatch.setattr(cli, "get_settings", lambda: settings)
    monkeypatch.setattr(cli.bcb_currency, "run", bcb_run)

    result = runner.invoke(cli.app, ["ingest", "bcb-currency"])

    assert result.exit_code == 0, result.output
    bcb_run.assert_called_once_with(settings, full=False, from_raw=False)


def test_ingest_bcb_currency_full_flag_propagates(
    monkeypatch: pytest.MonkeyPatch, settings: Settings
) -> None:
    bcb_run = MagicMock(return_value="proj.bronze_bcb.currency_series_raw")
    monkeypatch.setattr(cli, "get_settings", lambda: settings)
    monkeypatch.setattr(cli.bcb_currency, "run", bcb_run)

    result = runner.invoke(cli.app, ["ingest", "bcb-currency", "--full"])

    assert result.exit_code == 0, result.output
    bcb_run.assert_called_once_with(settings, full=True, from_raw=False)


# ─── ingest ibge-batch ───────────────────────────────────────────────────────
def test_ingest_ibge_batch_auto_chunk_iterates_full_window(
    monkeypatch: pytest.MonkeyPatch, settings: Settings
) -> None:
    """No --chunk-years: chunk_years is auto-computed; the pipeline is invoked once per chunk."""
    settings.ibge_start_year = 2010
    settings.ibge_end_year = 2014
    monkeypatch.setattr(cli, "get_settings", lambda: settings)
    # Force a known chunk size (1 year) so we know exactly how many calls happen.
    monkeypatch.setattr(cli, "recommended_chunk_years", lambda n_products: 1)
    monkeypatch.setattr(cli, "get_credentials", lambda s: None)
    monkeypatch.setattr(cli.storage, "Client", MagicMock())
    monkeypatch.setattr(cli.bigquery, "Client", MagicMock())

    pipeline_run = MagicMock(return_value="proj.bronze_ibge.sidra_t289_raw")
    monkeypatch.setattr(cli.ibge_pipeline, "run", pipeline_run)

    result = runner.invoke(cli.app, ["ingest", "ibge-batch"])

    assert result.exit_code == 0, result.output
    # 5 years, chunk_years=1 → 5 chunks → 5 pipeline runs.
    assert pipeline_run.call_count == 5
    # Each call must have received a chunked Settings, not the full window.
    chunk_years = [
        (c.args[0].ibge_start_year, c.args[0].ibge_end_year) for c in pipeline_run.call_args_list
    ]
    assert chunk_years == [(2010, 2010), (2011, 2011), (2012, 2012), (2013, 2013), (2014, 2014)]


def test_ingest_ibge_batch_manual_chunk_size_overrides_auto(
    monkeypatch: pytest.MonkeyPatch, settings: Settings
) -> None:
    settings.ibge_start_year = 2010
    settings.ibge_end_year = 2013  # 4 years total
    monkeypatch.setattr(cli, "get_settings", lambda: settings)
    auto = MagicMock(return_value=999)  # should NOT be called when --chunk-years given.
    monkeypatch.setattr(cli, "recommended_chunk_years", auto)
    monkeypatch.setattr(cli, "get_credentials", lambda s: None)
    monkeypatch.setattr(cli.storage, "Client", MagicMock())
    monkeypatch.setattr(cli.bigquery, "Client", MagicMock())

    pipeline_run = MagicMock(return_value="proj.bronze_ibge.sidra_t289_raw")
    monkeypatch.setattr(cli.ibge_pipeline, "run", pipeline_run)

    result = runner.invoke(cli.app, ["ingest", "ibge-batch", "--chunk-years", "2"])

    assert result.exit_code == 0, result.output
    auto.assert_not_called()
    # 4 years / 2 = 2 chunks.
    assert pipeline_run.call_count == 2


def test_ingest_ibge_batch_raises_when_start_year_unset(
    monkeypatch: pytest.MonkeyPatch, settings: Settings
) -> None:
    settings.ibge_start_year = None
    monkeypatch.setattr(cli, "get_settings", lambda: settings)

    result = runner.invoke(cli.app, ["ingest", "ibge-batch"])

    assert result.exit_code != 0
    assert "IBGE_START_YEAR" in result.output


def test_ingest_ibge_batch_continues_after_chunk_failure(
    monkeypatch: pytest.MonkeyPatch, settings: Settings
) -> None:
    """A single failed chunk must not strand the rest. Exit 1, but every chunk ran."""
    settings.ibge_start_year = 2010
    settings.ibge_end_year = 2012
    monkeypatch.setattr(cli, "get_settings", lambda: settings)
    monkeypatch.setattr(cli, "recommended_chunk_years", lambda n_products: 1)
    monkeypatch.setattr(cli, "get_credentials", lambda s: None)
    monkeypatch.setattr(cli.storage, "Client", MagicMock())
    monkeypatch.setattr(cli.bigquery, "Client", MagicMock())

    call_log: list[int] = []

    def flaky(chunk_settings: Settings, **kwargs: object) -> str:
        call_log.append(chunk_settings.ibge_start_year)
        if chunk_settings.ibge_start_year == 2011:
            raise RuntimeError("network blip")
        return "proj.bronze_ibge.sidra_t289_raw"

    monkeypatch.setattr(cli.ibge_pipeline, "run", flaky)

    result = runner.invoke(cli.app, ["ingest", "ibge-batch"])

    # Continue-on-failure: every chunk attempted.
    assert call_log == [2010, 2011, 2012]
    # But exit code reports the failure so CI/cron can react.
    assert result.exit_code == 1
    assert "2011 failed" in result.output or "2011-2011 failed" in result.output


# ─── ingest all ──────────────────────────────────────────────────────────────
def test_ingest_all_runs_every_pipeline_in_order(
    monkeypatch: pytest.MonkeyPatch, settings: Settings
) -> None:
    order: list[str] = []
    monkeypatch.setattr(cli, "get_settings", lambda: settings)
    monkeypatch.setattr(cli.ibge_pipeline, "run", lambda s: order.append("ibge") or "")
    monkeypatch.setattr(
        cli.bcb_inflation, "run", lambda s, full: order.append(f"inflation-{full}") or ""
    )
    monkeypatch.setattr(
        cli.bcb_currency, "run", lambda s, full: order.append(f"currency-{full}") or ""
    )
    monkeypatch.setattr(
        cli.comex_pipeline, "run", lambda s, full: order.append(f"comex-{full}") or ""
    )

    result = runner.invoke(cli.app, ["ingest", "all"])

    assert result.exit_code == 0, result.output
    assert order == ["ibge", "inflation-False", "currency-False", "comex-False"]


def test_ingest_all_full_flag_propagates_to_delta_pipelines(
    monkeypatch: pytest.MonkeyPatch, settings: Settings
) -> None:
    """`--full` cascades to delta-aware pipelines (BCB + COMEX) but not IBGE."""
    seen_full: list[bool] = []
    monkeypatch.setattr(cli, "get_settings", lambda: settings)
    monkeypatch.setattr(cli.ibge_pipeline, "run", lambda s: "")
    monkeypatch.setattr(cli.bcb_inflation, "run", lambda s, full: seen_full.append(full) or "")
    monkeypatch.setattr(cli.bcb_currency, "run", lambda s, full: seen_full.append(full) or "")
    monkeypatch.setattr(cli.comex_pipeline, "run", lambda s, full: seen_full.append(full) or "")

    result = runner.invoke(cli.app, ["ingest", "all", "--full"])

    assert result.exit_code == 0, result.output
    assert seen_full == [True, True, True]


def test_ingest_all_wraps_each_pipeline_in_observability(
    monkeypatch: pytest.MonkeyPatch, settings: Settings
) -> None:
    """`ingest all` must open an event log per pipeline (via pipeline_run), so the
    batch is visible in `embrapa monitor` like the individual ingest commands —
    not run silently with no event log as it did before."""
    init_calls: list[str] = []
    monkeypatch.setattr(cli, "get_settings", lambda: settings)
    monkeypatch.setattr(cli.ibge_pipeline, "run", lambda s: "")
    monkeypatch.setattr(cli.bcb_inflation, "run", lambda s, full: "")
    monkeypatch.setattr(cli.bcb_currency, "run", lambda s, full: "")
    monkeypatch.setattr(cli.comex_pipeline, "run", lambda s, full: "")
    monkeypatch.setattr(
        cli.observability,
        "init_run",
        lambda pipeline: init_calls.append(pipeline) or ("rid", Path(f"{pipeline}.jsonl")),
    )

    result = runner.invoke(cli.app, ["ingest", "all"])

    assert result.exit_code == 0, result.output
    # One event log opened per registered pipeline, in INGESTS order.
    assert init_calls == ["ibge", "bcb-inflation", "bcb-currency", "comex"]


# ─── discover ────────────────────────────────────────────────────────────────
def test_discover_ibge_products_prints_matches(monkeypatch: pytest.MonkeyPatch) -> None:
    from embrapa_commodities.discover import ProductMatch

    def fake_search(table_id: str, needles: list[str]) -> list[ProductMatch]:
        assert table_id == "289"
        assert needles == ["castanha", "madeira"]
        return [
            ProductMatch(code="3405", name="Castanha-do-pará", classification_id="193"),
            ProductMatch(code="3435", name="Madeira em tora", classification_id="193"),
        ]

    monkeypatch.setattr(cli.discover, "search_ibge_products", fake_search)

    result = runner.invoke(cli.app, ["discover", "ibge-products", "--keywords", "castanha,madeira"])

    assert result.exit_code == 0, result.output
    assert "3405" in result.output
    assert "3435" in result.output
    # Suggested .env line should include both codes.
    assert "IBGE_PRODUCT_CODES=3405,3435" in result.output


def test_discover_ibge_products_exits_1_when_no_matches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(cli.discover, "search_ibge_products", lambda *_a: [])

    result = runner.invoke(cli.app, ["discover", "ibge-products", "--keywords", "nada"])

    assert result.exit_code == 1


def test_discover_bcb_series_prints_sample(monkeypatch: pytest.MonkeyPatch) -> None:
    from embrapa_commodities.discover import BcbSeriesSample

    monkeypatch.setattr(
        cli.discover,
        "sample_bcb_series",
        lambda code, n: BcbSeriesSample(
            code=code, sample=[{"data": "01/01/2025", "valor": "0.16"}]
        ),
    )

    result = runner.invoke(cli.app, ["discover", "bcb-series", "433", "--last", "1"])

    assert result.exit_code == 0, result.output
    assert "SGS series 433" in result.output
    assert "0.16" in result.output


def test_discover_bcb_series_empty_exits_1(monkeypatch: pytest.MonkeyPatch) -> None:
    from embrapa_commodities.discover import BcbSeriesSample

    monkeypatch.setattr(
        cli.discover,
        "sample_bcb_series",
        lambda code, n: BcbSeriesSample(code=code, sample=[]),
    )

    result = runner.invoke(cli.app, ["discover", "bcb-series", "999"])

    assert result.exit_code == 1


# ─── monitor ─────────────────────────────────────────────────────────────────
def test_monitor_list_flag_shows_table(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli.observability, "list_log_paths", lambda: [])
    monkeypatch.setattr(cli.observability, "log_dir", lambda: Path("/tmp/logs"))

    result = runner.invoke(cli.app, ["monitor", "--list"])

    assert result.exit_code == 0
    assert "No event logs" in result.output


def test_monitor_no_logs_exits_1(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli.observability, "latest_log_path", lambda pipeline: None)
    monkeypatch.setattr(cli.observability, "log_dir", lambda: Path("/tmp/logs"))

    result = runner.invoke(cli.app, ["monitor"])

    assert result.exit_code == 1
    assert "No event logs" in result.output


def test_monitor_dispatches_to_monitor_run(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    log = tmp_path / "ibge-XYZ.jsonl"
    log.write_text('{"event":"pipeline_start"}\n', encoding="utf-8")
    captured: dict = {}

    def fake_run(target, follow, console):  # type: ignore[no-untyped-def]
        captured["target"] = target
        captured["follow"] = follow

    monkeypatch.setattr(cli.monitor, "run", fake_run)

    result = runner.invoke(cli.app, ["monitor", str(log), "--no-follow"])

    assert result.exit_code == 0, result.output
    assert captured["target"] == log
    assert captured["follow"] is False


# ─── doctor ──────────────────────────────────────────────────────────────────
def test_doctor_all_passing_returns_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    from embrapa_commodities.doctor import CheckResult

    monkeypatch.setattr(
        cli.doctor,
        "run_all",
        lambda: [CheckResult(name="a", ok=True, detail="ok")],
    )

    result = runner.invoke(cli.app, ["doctor"])

    assert result.exit_code == 0
    assert "All checks passed" in result.output


def test_doctor_failure_exits_1(monkeypatch: pytest.MonkeyPatch) -> None:
    from embrapa_commodities.doctor import CheckResult

    monkeypatch.setattr(
        cli.doctor,
        "run_all",
        lambda: [
            CheckResult(name="a", ok=True, detail="ok"),
            CheckResult(name="b", ok=False, detail="broken"),
        ],
    )

    result = runner.invoke(cli.app, ["doctor"])

    assert result.exit_code == 1
    assert "check(s) failed" in result.output


# ─── backup-gold ─────────────────────────────────────────────────────────────
def test_backup_gold_calls_backup_run_with_settings(
    monkeypatch: pytest.MonkeyPatch, settings: Settings
) -> None:
    backup_run = MagicMock(return_value=("2026-05-25T00-00-00Z", ["gs://b/backups/x.parquet"]))
    monkeypatch.setattr(cli, "get_settings", lambda: settings)
    monkeypatch.setattr(cli.backup, "run", backup_run)

    result = runner.invoke(cli.app, ["backup-gold"])

    assert result.exit_code == 0, result.output
    backup_run.assert_called_once_with(settings)
    assert "Gold backup complete" in result.output
    assert "gs://b/backups/x.parquet" in result.output


# ─── dbt passthrough ─────────────────────────────────────────────────────────
def test_dbt_passthrough_invokes_dbt_module(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}

    def fake_run(cmd, cwd, check):  # type: ignore[no-untyped-def]
        captured["cmd"] = cmd
        captured["cwd"] = cwd
        return MagicMock(returncode=0)

    monkeypatch.setattr(cli.subprocess, "run", fake_run)

    # `--` separator stops typer from trying to parse `--select` as its own option.
    result = runner.invoke(cli.app, ["dbt", "--", "build", "--select", "silver"])

    assert result.exit_code == 0, result.output
    # First two items: <python> -m dbt.cli.main
    assert captured["cmd"][1:3] == ["-m", "dbt.cli.main"]
    # Trailing args forwarded verbatim.
    assert captured["cmd"][-3:] == ["build", "--select", "silver"]
    # CWD must point at the dbt project directory.
    assert captured["cwd"].name == "dbt"


def test_dbt_passthrough_no_args_defaults_to_help(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict = {}

    def fake_run(cmd, cwd, check):  # type: ignore[no-untyped-def]
        captured["cmd"] = cmd
        return MagicMock(returncode=0)

    monkeypatch.setattr(cli.subprocess, "run", fake_run)

    result = runner.invoke(cli.app, ["dbt"])

    assert result.exit_code == 0
    assert captured["cmd"][-1] == "--help"


def test_dbt_passthrough_propagates_nonzero_exit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(cli.subprocess, "run", lambda *a, **kw: MagicMock(returncode=2))

    result = runner.invoke(cli.app, ["dbt", "compile"])

    assert result.exit_code == 2
