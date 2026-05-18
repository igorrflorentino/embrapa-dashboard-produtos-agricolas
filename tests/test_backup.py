"""Tests for the Gold cold-storage backup pipeline (GCP fully mocked)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from google.cloud.exceptions import NotFound

from embrapa_commodities import backup
from embrapa_commodities.config import Settings


@pytest.fixture
def settings() -> Settings:
    return Settings(
        gcp_project_id="test-project",
        gcs_bucket="test-bucket",
        bq_gold_dataset="gold",
    )  # type: ignore[call-arg]


def test_run_extracts_every_gold_table(settings: Settings) -> None:
    """Happy path: 3 Gold tables → 3 extract jobs, 3 URIs returned."""
    with (
        patch("embrapa_commodities.backup.bigquery.Client") as bq_cls,
        patch("embrapa_commodities.backup.storage.Client"),
        patch("embrapa_commodities.backup.ensure_bucket"),
    ):
        client = bq_cls.return_value
        client.get_table.return_value = MagicMock()
        client.extract_table.return_value.result.return_value = None

        run_id, uris = backup.run(settings)

    assert client.extract_table.call_count == 3
    assert len(uris) == 3
    # All URIs land under the same run_id prefix.
    assert all(f"backups/run={run_id}/" in uri for uri in uris)
    # Each URI ends in a wildcard so BQ can shard the export.
    assert all(uri.endswith("-*.parquet") for uri in uris)


def test_run_skips_missing_tables(settings: Settings) -> None:
    """If only some tables exist (e.g. year_product was never built), we back
    up what's there instead of failing."""
    with (
        patch("embrapa_commodities.backup.bigquery.Client") as bq_cls,
        patch("embrapa_commodities.backup.storage.Client"),
        patch("embrapa_commodities.backup.ensure_bucket"),
    ):
        client = bq_cls.return_value
        client.get_table.side_effect = [MagicMock(), NotFound("missing"), MagicMock()]
        client.extract_table.return_value.result.return_value = None

        _, uris = backup.run(settings)

    assert client.extract_table.call_count == 2
    assert len(uris) == 2


def test_run_raises_when_no_tables_exist(settings: Settings) -> None:
    """All Gold tables missing → RuntimeError pointing at dbt-build-prod."""
    with (
        patch("embrapa_commodities.backup.bigquery.Client") as bq_cls,
        patch("embrapa_commodities.backup.storage.Client"),
        patch("embrapa_commodities.backup.ensure_bucket"),
    ):
        client = bq_cls.return_value
        client.get_table.side_effect = NotFound("nope")

        with pytest.raises(RuntimeError, match="dbt-build-prod"):
            backup.run(settings)


def test_run_uses_parquet_snappy_format(settings: Settings) -> None:
    """ExtractJobConfig must be Parquet + Snappy so backups are restorable."""
    with (
        patch("embrapa_commodities.backup.bigquery.Client") as bq_cls,
        patch("embrapa_commodities.backup.storage.Client"),
        patch("embrapa_commodities.backup.ensure_bucket"),
    ):
        client = bq_cls.return_value
        client.get_table.return_value = MagicMock()
        client.extract_table.return_value.result.return_value = None

        backup.run(settings)

    call_kwargs = client.extract_table.call_args.kwargs
    cfg = call_kwargs["job_config"]
    assert cfg.destination_format == "PARQUET"
    assert cfg.compression == "SNAPPY"
