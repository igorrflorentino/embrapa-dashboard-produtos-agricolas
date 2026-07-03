"""Tests for BigQuery helpers (BigQuery client fully mocked)."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

import pandas as pd
import pytest
from google.cloud import bigquery
from google.cloud.exceptions import NotFound

from embrapa_dashboard.gcp.bigquery import (
    ensure_dataset,
    latest_reference_date,
    latest_reference_year,
    load_dataframe,
)


def test_ensure_dataset_creates_when_missing() -> None:
    client = MagicMock()
    client.get_dataset.side_effect = NotFound("nope")

    ensure_dataset(client, "proj.dataset", "us-central1")

    client.create_dataset.assert_called_once()
    created = client.create_dataset.call_args.args[0]
    assert created.location == "us-central1"
    assert created.max_time_travel_hours == 48


def test_ensure_dataset_no_op_when_location_matches() -> None:
    client = MagicMock()
    existing = MagicMock()
    existing.location = "us-central1"
    client.get_dataset.return_value = existing

    ensure_dataset(client, "proj.dataset", "us-central1")

    client.create_dataset.assert_not_called()


def test_ensure_dataset_raises_on_location_mismatch() -> None:
    client = MagicMock()
    existing = MagicMock()
    existing.location = "EU"
    client.get_dataset.return_value = existing

    with pytest.raises(RuntimeError, match="Cross-region"):
        ensure_dataset(client, "proj.dataset", "us-central1")


def test_load_dataframe_configures_partitioning_and_clustering() -> None:
    client = MagicMock()
    job = MagicMock()
    client.load_table_from_dataframe.return_value = job

    df = pd.DataFrame({"a": [1], "ingestion_timestamp": [pd.Timestamp.now(tz="UTC")]})
    schema = [
        bigquery.SchemaField("a", "INT64"),
        bigquery.SchemaField("ingestion_timestamp", "TIMESTAMP", mode="REQUIRED"),
    ]

    load_dataframe(
        client,
        df,
        "proj.dataset.tbl",
        schema,
        time_partitioning_field="ingestion_timestamp",
        clustering_fields=["a"],
    )

    call_kwargs = client.load_table_from_dataframe.call_args.kwargs
    cfg = call_kwargs["job_config"]
    assert cfg.write_disposition == "WRITE_APPEND"
    assert cfg.time_partitioning.field == "ingestion_timestamp"
    assert cfg.time_partitioning.type_ == bigquery.TimePartitioningType.DAY
    assert cfg.clustering_fields == ["a"]
    job.result.assert_called_once()


def test_latest_reference_date_returns_none_when_table_missing() -> None:
    client = MagicMock()
    client.query.side_effect = NotFound("table missing")

    result = latest_reference_date(client, "proj.dataset.tbl", "433")

    assert result is None


def test_latest_reference_date_returns_max_when_rows_exist() -> None:
    client = MagicMock()
    row = MagicMock()
    row.max_date = date(2025, 12, 1)
    query_job = MagicMock()
    query_job.result.return_value = iter([row])
    client.query.return_value = query_job

    result = latest_reference_date(client, "proj.dataset.tbl", "433")

    assert result == date(2025, 12, 1)
    call_kwargs = client.query.call_args.kwargs
    params = {p.name: p.value for p in call_kwargs["job_config"].query_parameters}
    assert params == {"fmt": "%d/%m/%Y", "code": "433"}


def test_latest_reference_year_returns_none_when_table_missing() -> None:
    client = MagicMock()
    client.query.side_effect = NotFound("table missing")

    assert latest_reference_year(client, "proj.dataset.tbl") is None


def test_latest_reference_year_returns_max_year() -> None:
    client = MagicMock()
    row = MagicMock()
    row.max_year = 2024
    query_job = MagicMock()
    query_job.result.return_value = iter([row])
    client.query.return_value = query_job

    assert latest_reference_year(client, "proj.dataset.tbl") == 2024
    assert "safe_cast(ano as int64)" in client.query.call_args.args[0]


def test_latest_reference_year_returns_none_on_empty_table() -> None:
    """max() over an empty table yields a NULL max_year → None, not a crash."""
    client = MagicMock()
    row = MagicMock()
    row.max_year = None
    query_job = MagicMock()
    query_job.result.return_value = iter([row])
    client.query.return_value = query_job

    assert latest_reference_year(client, "proj.dataset.tbl") is None
