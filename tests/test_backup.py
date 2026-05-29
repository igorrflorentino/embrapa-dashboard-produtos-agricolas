"""Tests for the Gold cold-storage backup pipeline (GCP fully mocked)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from embrapa_commodities import backup
from embrapa_commodities.config import Settings


@pytest.fixture
def settings() -> Settings:
    return Settings(
        gcp_project_id="test-project",
        gcs_bucket="test-bucket",
        bq_gold_dataset="gold",
    )  # type: ignore[call-arg]


def _fake_table(table_id: str, table_type: str = "TABLE") -> MagicMock:
    """Stand-in for a `google.cloud.bigquery.table.TableListItem`."""
    t = MagicMock()
    t.table_id = table_id
    t.table_type = table_type
    return t


def test_run_extracts_every_gold_table(settings: Settings) -> None:
    """Happy path: introspect Gold → 1 extract per `gold_*` table → URIs returned.

    Today only `gold_pevs_production` exists in the dbt project; this test
    exercises the multi-table path with a synthetic list so the contract
    survives when new Gold lineages (per-source: `gold_comex_*`,
    `gold_nfe_*`) are added later.
    """
    with (
        patch("embrapa_commodities.backup.bigquery.Client") as bq_cls,
        patch("embrapa_commodities.backup.storage.Client"),
        patch("embrapa_commodities.backup.ensure_bucket"),
    ):
        client = bq_cls.return_value
        client.list_tables.return_value = [
            _fake_table("gold_pevs_production"),
            _fake_table("gold_comex_flows"),
            _fake_table("gold_nfe_flows"),
        ]
        client.extract_table.return_value.result.return_value = None

        run_id, uris = backup.run(settings)

    assert client.extract_table.call_count == 3
    assert len(uris) == 3
    # All URIs land under the same run_id prefix.
    assert all(f"backups/run={run_id}/" in uri for uri in uris)
    # Each URI ends in a wildcard so BQ can shard the export.
    assert all(uri.endswith("-*.parquet") for uri in uris)


def test_run_filters_by_prefix_and_table_type(settings: Settings) -> None:
    """Introspection skips: (a) tables outside the prefix, (b) views.

    Replaces the old `test_run_skips_missing_tables` — the new flow can't see
    missing tables (`list_tables` only returns extant), so we test the filter
    that protects against backing up unrelated artefacts.
    """
    with (
        patch("embrapa_commodities.backup.bigquery.Client") as bq_cls,
        patch("embrapa_commodities.backup.storage.Client"),
        patch("embrapa_commodities.backup.ensure_bucket"),
    ):
        client = bq_cls.return_value
        client.list_tables.return_value = [
            _fake_table("gold_pevs_production"),  # backed up
            _fake_table("gold_explore_temp"),  # backed up (matches prefix)
            _fake_table("staging_temp"),  # filtered: wrong prefix
            _fake_table("gold_legacy_view", table_type="VIEW"),  # filtered: VIEW
        ]
        client.extract_table.return_value.result.return_value = None

        _, uris = backup.run(settings)

    assert client.extract_table.call_count == 2
    assert len(uris) == 2
    # Filtered names never reach extract_table.
    extracted_names = [call.args[0] for call in client.extract_table.call_args_list]
    assert all("staging_temp" not in n for n in extracted_names)
    assert all("legacy_view" not in n for n in extracted_names)


def test_run_raises_when_dataset_is_empty(settings: Settings) -> None:
    """Gold dataset has no matching tables → RuntimeError pointing at dbt-build-prod."""
    with (
        patch("embrapa_commodities.backup.bigquery.Client") as bq_cls,
        patch("embrapa_commodities.backup.storage.Client"),
        patch("embrapa_commodities.backup.ensure_bucket"),
    ):
        client = bq_cls.return_value
        client.list_tables.return_value = []

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
        client.list_tables.return_value = [_fake_table("gold_pevs_production")]
        client.extract_table.return_value.result.return_value = None

        backup.run(settings)

    call_kwargs = client.extract_table.call_args.kwargs
    cfg = call_kwargs["job_config"]
    assert cfg.destination_format == "PARQUET"
    assert cfg.compression == "SNAPPY"
