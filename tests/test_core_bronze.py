"""Unit tests for the shared Bronze landing primitive (core/bronze.py).

The source pipelines delegate their GCS-land + BQ-load tail here; these tests
pin the contract that tail must honour (object-name skeleton, partition/cluster
passthrough, run_id minting) independently of any one source.
"""

from __future__ import annotations

import re
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from google.cloud import bigquery

from embrapa_commodities.config import Settings
from embrapa_commodities.core import bronze


@pytest.fixture
def settings() -> Settings:
    return Settings(
        gcp_project_id="test-project",
        gcs_bucket="test-bucket",
        _env_file=None,
    )  # type: ignore[call-arg]


@pytest.fixture
def df() -> pd.DataFrame:
    return pd.DataFrame({"a": ["1"], "ingestion_timestamp": [pd.Timestamp.now()]})


SCHEMA = [
    bigquery.SchemaField("a", "STRING"),
    bigquery.SchemaField("ingestion_timestamp", "TIMESTAMP"),
]


def _call(settings: Settings, df: pd.DataFrame, **overrides):
    kwargs = dict(
        settings=settings,
        storage_client=MagicMock(name="gcs"),
        bq_client=MagicMock(name="bq"),
        source="bcb",
        table="some_raw",
        object_basename="some_1980_2026",
        destination="test-project.bronze_bcb.some_raw",
        schema=SCHEMA,
        clustering_fields=["series_code"],
    )
    kwargs.update(overrides)
    return bronze.land_and_load(df, **kwargs)


def test_returns_destination_unchanged(settings: Settings, df: pd.DataFrame) -> None:
    with (
        patch("embrapa_commodities.core.bronze.ensure_bucket"),
        patch("embrapa_commodities.core.bronze.upload_dataframe_as_parquet"),
        patch("embrapa_commodities.core.bronze.load_dataframe"),
    ):
        result = _call(settings, df, destination="proj.ds.tbl")

    assert result == "proj.ds.tbl"


def test_object_name_skeleton(settings: Settings, df: pd.DataFrame) -> None:
    """Path is {prefix}/{source}/{table}/run=<ts>/{basename}.parquet."""
    with (
        patch("embrapa_commodities.core.bronze.ensure_bucket"),
        patch("embrapa_commodities.core.bronze.upload_dataframe_as_parquet") as upload,
        patch("embrapa_commodities.core.bronze.load_dataframe"),
    ):
        _call(
            settings,
            df,
            source="ibge",
            table="sidra_t289_raw",
            object_basename="products_3405_2020_2020",
        )

    object_name = upload.call_args.args[2]
    assert re.fullmatch(
        r"landing/ibge/sidra_t289_raw/run=\d{8}T\d{6}Z/products_3405_2020_2020\.parquet",
        object_name,
    )


def test_explicit_run_id_lands_in_path(settings: Settings, df: pd.DataFrame) -> None:
    """When a caller (IBGE) shares its column timestamp, that exact run_id is used."""
    with (
        patch("embrapa_commodities.core.bronze.ensure_bucket"),
        patch("embrapa_commodities.core.bronze.upload_dataframe_as_parquet") as upload,
        patch("embrapa_commodities.core.bronze.load_dataframe"),
    ):
        _call(settings, df, run_id="20200101T000000Z")

    assert "run=20200101T000000Z/" in upload.call_args.args[2]


def test_partition_and_cluster_keys_forwarded(settings: Settings, df: pd.DataFrame) -> None:
    with (
        patch("embrapa_commodities.core.bronze.ensure_bucket"),
        patch("embrapa_commodities.core.bronze.upload_dataframe_as_parquet"),
        patch("embrapa_commodities.core.bronze.load_dataframe") as load,
    ):
        _call(settings, df, clustering_fields=["series_code", "reference_date_str"])

    load_kwargs = load.call_args.kwargs
    assert load_kwargs["time_partitioning_field"] == "ingestion_timestamp"
    assert load_kwargs["clustering_fields"] == ["series_code", "reference_date_str"]


def test_uses_passed_clients(settings: Settings, df: pd.DataFrame) -> None:
    """Clients are injected, never constructed here — and reach both sinks."""
    gcs = MagicMock(name="gcs")
    bq = MagicMock(name="bq")
    with (
        patch("embrapa_commodities.core.bronze.ensure_bucket") as ensure_bucket,
        patch("embrapa_commodities.core.bronze.upload_dataframe_as_parquet") as upload,
        patch("embrapa_commodities.core.bronze.load_dataframe") as load,
    ):
        _call(settings, df, storage_client=gcs, bq_client=bq)

    ensure_bucket.assert_called_once_with(gcs, settings.gcs_bucket, settings.bq_location)
    assert upload.call_args.args[0] is gcs
    assert load.call_args.args[0] is bq
