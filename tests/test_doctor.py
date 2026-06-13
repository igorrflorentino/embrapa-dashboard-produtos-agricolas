"""Tests for the embrapa doctor health-check probes."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
import responses
from google.cloud.exceptions import NotFound

from embrapa_commodities import doctor
from embrapa_commodities.config import Settings


@pytest.fixture
def settings(settings_factory) -> Settings:
    # _env_file=None (via settings_factory) keeps these probes from reading the
    # developer's repo-root .env, so default-dependent assertions stay hermetic.
    return settings_factory(
        gcp_project_id="test-project",
        gcs_bucket="test-bucket",
        bcb_inflation_series="433:IPCA",
        bcb_currency_series="3694:USD",
    )


def test_check_env_passes_with_valid_settings(settings: Settings) -> None:
    result = doctor._check_env(settings)
    assert result.ok is True
    assert "433" in result.detail
    # The check vouches for ALL source mappings, not just PEVS/BCB.
    assert "pam=" in result.detail
    assert "comex=" in result.detail
    assert "comtrade=" in result.detail


def test_check_env_fails_on_bad_format(settings: Settings) -> None:
    # No colon — malformed pair.
    settings.bcb_inflation_series = "433_no_colon"
    result = doctor._check_env(settings)
    assert result.ok is False


def test_check_env_fails_on_bad_comex_ncm_codes(settings: Settings) -> None:
    """A malformed COMEX_NCM_CODES must fail '.env parsed' — not explode mid-ingest."""
    settings.comex_ncm_codes = "08012100_no_colon"
    result = doctor._check_env(settings)
    assert result.ok is False
    assert "08012100_no_colon" in result.detail


def test_check_env_fails_on_invalid_comtrade_flows(settings: Settings) -> None:
    settings.comtrade_flows = "X,Z"
    result = doctor._check_env(settings)
    assert result.ok is False
    assert "Z" in result.detail


def test_check_env_fails_on_empty_pam_codes(settings: Settings) -> None:
    settings.pam_product_codes = " , "
    result = doctor._check_env(settings)
    assert result.ok is False
    assert "PAM_PRODUCT_CODES" in result.detail


def test_check_inflation_pivot_codes_pass(settings: Settings) -> None:
    """All three Gold pivot codes present in BCB_INFLATION_SERIES → ok."""
    settings.bcb_inflation_series = "433:IPCA,189:IGPM,190:IGPDI"
    result = doctor._check_inflation_pivot_codes(settings)
    assert result.ok is True


def test_check_inflation_pivot_codes_fails_when_code_not_ingested(settings: Settings) -> None:
    """A pivot code absent from BCB_INFLATION_SERIES → fail.

    The fixture ingests only 433:IPCA, but the IGP-M (189) and IGP-DI (190)
    pivot codes default on, so they are missing from the ingested series —
    exactly the drift that would silently NULL the Gold val_real_igpm/igpdi_*
    columns.
    """
    result = doctor._check_inflation_pivot_codes(settings)
    assert result.ok is False
    assert "189" in result.detail or "190" in result.detail


def test_check_adc_returns_project_when_ok(settings: Settings) -> None:
    with patch("embrapa_commodities.doctor.google.auth.default") as auth:
        auth.return_value = (MagicMock(), "test-project")
        result = doctor._check_adc(settings)
    assert result.ok is True
    assert "test-project" in result.detail


def test_check_adc_fails_with_recovery_hint(settings: Settings) -> None:
    with patch("embrapa_commodities.doctor.google.auth.default") as auth:
        auth.side_effect = Exception("no credentials")
        result = doctor._check_adc(settings)
    assert result.ok is False
    assert "gcloud auth" in result.detail


def test_check_bq_calls_service_account(settings: Settings) -> None:
    with patch("embrapa_commodities.doctor.bigquery.Client") as bq_cls:
        bq_cls.return_value.get_service_account_email.return_value = "sa@x.iam"
        result = doctor._check_bq(settings)
    assert result.ok is True
    assert "sa@x.iam" in result.detail


def test_check_gcs_reports_existing_bucket(settings: Settings) -> None:
    with patch("embrapa_commodities.doctor.storage.Client") as gcs_cls:
        gcs_cls.return_value.list_blobs.return_value = iter([object()])
        result = doctor._check_gcs(settings)
    assert result.ok is True
    assert "exists" in result.detail


def test_check_gcs_passes_when_bucket_missing(settings: Settings) -> None:
    """Missing bucket is OK — it'll be lazily created on first ingest."""
    from google.cloud.exceptions import NotFound

    with patch("embrapa_commodities.doctor.storage.Client") as gcs_cls:
        gcs_cls.return_value.list_blobs.side_effect = NotFound("bucket not found")
        result = doctor._check_gcs(settings)
    assert result.ok is True
    assert "will be created" in result.detail


@responses.activate
def test_check_ibge_reachable(settings: Settings) -> None:
    responses.add(
        responses.GET,
        re.compile(r"https://servicodados\.ibge\.gov\.br/api/v3/agregados/289/metadados.*"),
        json={"classificacoes": []},
        status=200,
    )
    result = doctor._check_ibge(settings)
    assert result.ok is True


@responses.activate
def test_check_ibge_handles_5xx(settings: Settings) -> None:
    responses.add(
        responses.GET,
        re.compile(r"https://servicodados\.ibge\.gov\.br/api/v3/agregados/289/metadados.*"),
        status=503,
    )
    result = doctor._check_ibge(settings)
    assert result.ok is False


@responses.activate
def test_check_bcb_reachable(settings: Settings) -> None:
    responses.add(
        responses.GET,
        re.compile(r"https://api\.bcb\.gov\.br/dados/serie/bcdata\.sgs\.433/dados.*"),
        json=[{"data": "01/01/2024", "valor": "0.16"}],
        status=200,
    )
    result = doctor._check_bcb(settings)
    assert result.ok is True
    assert "sgs.433" in result.detail


def _comex_url(settings: Settings, year: int) -> str:
    return f"{settings.comex_csv_base_url.rstrip('/')}/EXP_{year}.csv"


@responses.activate
def test_check_comex_ok_when_end_year_file_published(settings: Settings) -> None:
    settings.comex_end_year = 2026
    responses.add(responses.HEAD, _comex_url(settings, 2026), status=200)
    result = doctor._check_comex(settings)
    assert result.ok is True
    assert "EXP_2026.csv 200 OK" in result.detail


@responses.activate
def test_check_comex_treats_current_year_404_as_healthy(settings: Settings) -> None:
    """Early in the year MDIC hasn't published EXP_<end_year>.csv yet.

    The ingest pipeline classifies that 404 as an expected skip, so doctor
    must not exit 1 for it — it falls back to probing the previous year.
    """
    settings.comex_end_year = 2026
    responses.add(responses.HEAD, _comex_url(settings, 2026), status=404)
    responses.add(responses.HEAD, _comex_url(settings, 2025), status=200)
    result = doctor._check_comex(settings)
    assert result.ok is True
    assert "EXP_2025.csv 200 OK" in result.detail
    assert "not published yet" in result.detail


@responses.activate
def test_check_comex_fails_when_previous_year_also_unreachable(settings: Settings) -> None:
    """404 on BOTH years is a real problem (wrong base URL, host down), not
    the expected not-yet-published window."""
    settings.comex_end_year = 2026
    responses.add(responses.HEAD, _comex_url(settings, 2026), status=404)
    responses.add(responses.HEAD, _comex_url(settings, 2025), status=404)
    result = doctor._check_comex(settings)
    assert result.ok is False


@responses.activate
def test_check_comex_fails_on_5xx_without_fallback(settings: Settings) -> None:
    """Only the expected 404 triggers the previous-year fallback — a 5xx is a
    hard failure straight away."""
    settings.comex_end_year = 2026
    responses.add(responses.HEAD, _comex_url(settings, 2026), status=503)
    result = doctor._check_comex(settings)
    assert result.ok is False
    assert len(responses.calls) == 1


def test_check_bronze_tables_distinguishes_present_vs_missing(settings: Settings) -> None:
    with patch("embrapa_commodities.doctor.bigquery.Client") as bq_cls:
        client = bq_cls.return_value
        # First table found, others missing (6 Bronze targets: ibge, pam, bcb×2, comex, comtrade).
        client.get_table.side_effect = [
            MagicMock(),
            NotFound("nope"),
            NotFound("nope"),
            NotFound("nope"),
            NotFound("nope"),
            NotFound("nope"),
        ]
        result = doctor._check_bronze_tables(settings)
    assert result.ok is True  # informational only
    assert "missing" in result.detail


def test_check_serving_marts_all_present_and_populated(settings: Settings) -> None:
    with patch("embrapa_commodities.doctor.bigquery.Client") as bq_cls:
        bq_cls.return_value.get_table.return_value = MagicMock(num_rows=100)
        result = doctor._check_serving_marts(settings)
    assert result.ok is True
    assert "all present" in result.detail


def test_check_serving_marts_reports_missing(settings: Settings) -> None:
    with patch("embrapa_commodities.doctor.bigquery.Client") as bq_cls:
        # First six marts present; gold_source_metadata (the 7th target) missing.
        bq_cls.return_value.get_table.side_effect = [
            MagicMock(num_rows=10),
            MagicMock(num_rows=10),
            MagicMock(num_rows=10),
            MagicMock(num_rows=10),
            MagicMock(num_rows=10),
            MagicMock(num_rows=10),
            NotFound("nope"),
        ]
        result = doctor._check_serving_marts(settings)
    assert result.ok is True  # informational, never fails doctor on a fresh project
    assert "missing" in result.detail
    assert "dbt-build-prod" in result.detail


def test_check_serving_marts_flags_empty_mart(settings: Settings) -> None:
    with patch("embrapa_commodities.doctor.bigquery.Client") as bq_cls:
        # serving_pevs_annual is empty (0 rows); the view (last) reports
        # num_rows=0 too — but only the materialized mart may be flagged.
        bq_cls.return_value.get_table.side_effect = [
            MagicMock(num_rows=0, table_type="TABLE"),
            MagicMock(num_rows=10, table_type="TABLE"),
            MagicMock(num_rows=10, table_type="TABLE"),
            MagicMock(num_rows=10, table_type="TABLE"),
            MagicMock(num_rows=10, table_type="TABLE"),
            MagicMock(num_rows=10, table_type="TABLE"),
            MagicMock(num_rows=0, table_type="VIEW"),
        ]
        result = doctor._check_serving_marts(settings)
    assert result.ok is True
    assert "empty=['serving_pevs_annual']" in result.detail


def test_check_serving_marts_view_with_zero_num_rows_is_not_empty(settings: Settings) -> None:
    """The BigQuery API returns numRows=0 for VIEWs (verified against the live
    API) — gold_source_metadata must not be flagged 'empty' on every run."""
    with patch("embrapa_commodities.doctor.bigquery.Client") as bq_cls:
        bq_cls.return_value.get_table.side_effect = [
            MagicMock(num_rows=10, table_type="TABLE"),
            MagicMock(num_rows=10, table_type="TABLE"),
            MagicMock(num_rows=10, table_type="TABLE"),
            MagicMock(num_rows=10, table_type="TABLE"),
            MagicMock(num_rows=10, table_type="TABLE"),
            MagicMock(num_rows=10, table_type="TABLE"),
            MagicMock(num_rows=0, table_type="VIEW"),  # gold_source_metadata
        ]
        result = doctor._check_serving_marts(settings)
    assert result.ok is True
    assert "empty" not in result.detail
    assert "all present + populated" in result.detail


def _list_blobs_mock(prefixes: list[str]) -> MagicMock:
    """Build a list_blobs() return-value that exposes ``prefixes`` after iteration.

    The real GCS HTTPIterator only fills ``prefixes`` once the page iterator
    has been drained, so the production code does ``list(blobs)`` before
    reading ``.prefixes``. MagicMock's default ``__iter__`` already returns
    an empty iterator, so we only need to set the prefixes attribute.
    """
    iterator = MagicMock()
    iterator.prefixes = prefixes
    return iterator


def _mark_complete(gcs_cls: MagicMock, complete_markers: set[str] | None = None) -> None:
    """Configure which `_SUCCESS` marker blobs exist on the mocked GCS client.

    ``None`` means every snapshot is complete (every marker exists); otherwise
    only the given blob names exist — modelling crashed half-backups.
    """

    def _blob(name: str) -> MagicMock:
        blob = MagicMock()
        blob.exists.return_value = complete_markers is None or name in complete_markers
        return blob

    gcs_cls.return_value.bucket.return_value.blob.side_effect = _blob


def test_check_backup_freshness_reports_fresh_snapshot(settings: Settings) -> None:
    """Recent snapshot (well within threshold): ok=True, no warn marker."""
    now = datetime.now(UTC)
    recent = (now - timedelta(days=2)).strftime("%Y%m%dT%H%M%SZ")
    with patch("embrapa_commodities.doctor.storage.Client") as gcs_cls:
        gcs_cls.return_value.list_blobs.return_value = _list_blobs_mock([f"backups/run={recent}/"])
        _mark_complete(gcs_cls)
        result = doctor._check_backup_freshness(settings)
    assert result.ok is True
    assert "⚠" not in result.detail
    assert "2d ago" in result.detail or "1d ago" in result.detail


def test_check_backup_freshness_warns_on_stale(settings: Settings) -> None:
    """Snapshot older than BACKUP_STALENESS_DAYS: ok=True but ⚠ in detail."""
    settings.backup_staleness_days = 14
    stale_ts = (datetime.now(UTC) - timedelta(days=30)).strftime("%Y%m%dT%H%M%SZ")
    with patch("embrapa_commodities.doctor.storage.Client") as gcs_cls:
        gcs_cls.return_value.list_blobs.return_value = _list_blobs_mock(
            [f"backups/run={stale_ts}/"]
        )
        _mark_complete(gcs_cls)
        result = doctor._check_backup_freshness(settings)
    assert result.ok is True  # warn, not fail
    assert "⚠" in result.detail
    assert "stale" in result.detail


def test_check_backup_freshness_picks_latest_of_many(settings: Settings) -> None:
    """When multiple snapshots exist, freshness is measured from the most recent one."""
    now = datetime.now(UTC)
    old = (now - timedelta(days=400)).strftime("%Y%m%dT%H%M%SZ")
    middle = (now - timedelta(days=100)).strftime("%Y%m%dT%H%M%SZ")
    recent = (now - timedelta(days=3)).strftime("%Y%m%dT%H%M%SZ")
    with patch("embrapa_commodities.doctor.storage.Client") as gcs_cls:
        gcs_cls.return_value.list_blobs.return_value = _list_blobs_mock(
            [
                f"backups/run={old}/",
                f"backups/run={recent}/",
                f"backups/run={middle}/",
            ]
        )
        _mark_complete(gcs_cls)
        result = doctor._check_backup_freshness(settings)
    assert result.ok is True
    assert "⚠" not in result.detail


def test_check_backup_freshness_skips_incomplete_snapshot(settings: Settings) -> None:
    """A crashed half-backup (run prefix without _SUCCESS) must not satisfy
    freshness — the newest COMPLETE snapshot counts instead."""
    now = datetime.now(UTC)
    complete_ts = (now - timedelta(days=3)).strftime("%Y%m%dT%H%M%SZ")
    partial_ts = (now - timedelta(days=1)).strftime("%Y%m%dT%H%M%SZ")
    with patch("embrapa_commodities.doctor.storage.Client") as gcs_cls:
        gcs_cls.return_value.list_blobs.return_value = _list_blobs_mock(
            [f"backups/run={complete_ts}/", f"backups/run={partial_ts}/"]
        )
        _mark_complete(gcs_cls, {f"backups/run={complete_ts}/_SUCCESS"})
        result = doctor._check_backup_freshness(settings)
    assert result.ok is True
    assert "3d ago" in result.detail  # measured from the complete one, not 1d
    assert "skipped 1 newer incomplete" in result.detail


def test_check_backup_freshness_fails_when_only_incomplete_snapshots(settings: Settings) -> None:
    """Run prefixes exist but none carries the _SUCCESS marker → hard fail.

    This is exactly the partial/failed-backup scenario: the operator must not
    be told the cold-storage rollback path is intact."""
    fresh_ts = (datetime.now(UTC) - timedelta(days=1)).strftime("%Y%m%dT%H%M%SZ")
    with patch("embrapa_commodities.doctor.storage.Client") as gcs_cls:
        gcs_cls.return_value.list_blobs.return_value = _list_blobs_mock(
            [f"backups/run={fresh_ts}/"]
        )
        _mark_complete(gcs_cls, set())  # no marker anywhere
        result = doctor._check_backup_freshness(settings)
    assert result.ok is False
    assert "_SUCCESS" in result.detail
    assert "dbt-build-prod-with-backup" in result.detail


def test_check_backup_freshness_fails_when_no_snapshot(settings: Settings) -> None:
    """Empty backups/ prefix is a hard fail with a recovery hint."""
    with patch("embrapa_commodities.doctor.storage.Client") as gcs_cls:
        gcs_cls.return_value.list_blobs.return_value = _list_blobs_mock([])
        result = doctor._check_backup_freshness(settings)
    assert result.ok is False
    assert "dbt-build-prod-with-backup" in result.detail


def test_check_backup_freshness_ignores_malformed_prefixes(settings: Settings) -> None:
    """Stray prefixes that don't match the run=<ts>/ pattern are skipped.

    A human poking around with `gsutil cp` could land arbitrary objects under
    `backups/`; the probe must not crash and must not let them count as a
    snapshot.
    """
    with patch("embrapa_commodities.doctor.storage.Client") as gcs_cls:
        gcs_cls.return_value.list_blobs.return_value = _list_blobs_mock(
            ["backups/ad-hoc-thing/", "backups/run=not-a-timestamp/"]
        )
        result = doctor._check_backup_freshness(settings)
    assert result.ok is False  # no valid snapshot → fail like the empty case
    assert "no snapshot" in result.detail


def test_run_all_executes_every_probe(settings: Settings) -> None:
    """run_all should call each probe exactly once in CHECKS order."""
    with (
        patch("embrapa_commodities.doctor.google.auth.default") as auth,
        patch("embrapa_commodities.doctor.bigquery.Client") as bq_cls,
        patch("embrapa_commodities.doctor.storage.Client") as gcs_cls,
        patch("embrapa_commodities.doctor.requests.get") as get,
        patch("embrapa_commodities.doctor.requests.head") as head,
    ):
        auth.return_value = (MagicMock(), "p")
        bq_cls.return_value.get_service_account_email.return_value = "sa@x"
        bq_cls.return_value.get_table.return_value = MagicMock()
        gcs_cls.return_value.bucket.return_value.exists.return_value = True
        # list_blobs is consumed twice: once by _check_gcs (truthy iterator)
        # and once by _check_backup_freshness (prefixes attribute).
        gcs_cls.return_value.list_blobs.return_value = _list_blobs_mock([])
        get.return_value.status_code = 200
        get.return_value.raise_for_status.return_value = None
        # _check_comex probes with HEAD (avoids pulling the 100+ MB body).
        head.return_value.status_code = 200
        head.return_value.raise_for_status.return_value = None

        results = doctor.run_all(settings)

    assert len(results) == len(doctor.CHECKS)
    assert [r.name for r in results] == [
        ".env parsed",
        "Inflation pivot codes",
        "ADC credentials",
        "BigQuery reachable",
        "GCS bucket",
        "IBGE SIDRA reachable",
        "IBGE PAM reachable",
        "BCB SGS reachable",
        "COMEX reachable",
        "COMTRADE reachable",
        "Bronze tables",
        "Serving marts",
        "Gold backup freshness",
    ]
