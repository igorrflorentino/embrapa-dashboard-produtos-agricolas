"""Tests for the embrapa doctor health-check probes."""

from __future__ import annotations

import re
from unittest.mock import MagicMock, patch

import pytest
import responses
from google.cloud.exceptions import NotFound

from embrapa_commodities import doctor
from embrapa_commodities.config import Settings


@pytest.fixture
def settings() -> Settings:
    return Settings(
        gcp_project_id="test-project",
        gcs_bucket="test-bucket",
        bcb_inflation_series="433:IPCA",
        bcb_currency_series="3694:USD",
    )  # type: ignore[call-arg]


def test_check_env_passes_with_valid_settings(settings: Settings) -> None:
    result = doctor._check_env(settings)
    assert result.ok is True
    assert "433" in result.detail


def test_check_env_fails_on_bad_format(settings: Settings) -> None:
    # No colon — malformed pair.
    settings.bcb_inflation_series = "433_no_colon"
    result = doctor._check_env(settings)
    assert result.ok is False


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


def test_check_bronze_tables_distinguishes_present_vs_missing(settings: Settings) -> None:
    with patch("embrapa_commodities.doctor.bigquery.Client") as bq_cls:
        client = bq_cls.return_value
        # First table found, others missing.
        client.get_table.side_effect = [MagicMock(), NotFound("nope"), NotFound("nope")]
        result = doctor._check_bronze_tables(settings)
    assert result.ok is True  # informational only
    assert "missing" in result.detail


def test_run_all_executes_every_probe(settings: Settings) -> None:
    """run_all should call each probe exactly once in CHECKS order."""
    with (
        patch("embrapa_commodities.doctor.google.auth.default") as auth,
        patch("embrapa_commodities.doctor.bigquery.Client") as bq_cls,
        patch("embrapa_commodities.doctor.storage.Client") as gcs_cls,
        patch("embrapa_commodities.doctor.requests.get") as get,
    ):
        auth.return_value = (MagicMock(), "p")
        bq_cls.return_value.get_service_account_email.return_value = "sa@x"
        bq_cls.return_value.get_table.return_value = MagicMock()
        gcs_cls.return_value.bucket.return_value.exists.return_value = True
        get.return_value.status_code = 200
        get.return_value.raise_for_status.return_value = None

        results = doctor.run_all(settings)

    assert len(results) == len(doctor.CHECKS)
    assert [r.name for r in results] == [
        ".env parsed",
        "ADC credentials",
        "BigQuery reachable",
        "GCS bucket",
        "IBGE SIDRA reachable",
        "BCB SGS reachable",
        "Bronze tables",
    ]
