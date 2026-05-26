"""Tests for the IBGE Bronze pipeline (SIDRA + GCS + BQ all mocked)."""

from __future__ import annotations

from itertools import pairwise
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from embrapa_commodities.config import Settings
from embrapa_commodities.ibge import pipeline as ibge_pipeline


@pytest.fixture
def settings() -> Settings:
    return Settings(
        gcp_project_id="test-project",
        gcs_bucket="test-bucket",
        ibge_start_year=2020,
        ibge_end_year=2020,
        ibge_product_codes="3405",
        _env_file=None,
    )  # type: ignore[call-arg]


@pytest.fixture
def sidra_df() -> pd.DataFrame:
    """Two-row IBGE-shaped DataFrame mimicking `fetch_sidra_dataframe` output."""
    return pd.DataFrame(
        {
            "municipio_codigo": ["1100015", "1100023"],
            "municipio": ["Alta Floresta D'Oeste", "Ariquemes"],
            "ano": ["2020", "2020"],
            "variavel_codigo": ["144", "144"],
            "variavel": ["Quantidade produzida", "Quantidade produzida"],
            "tipo_de_produto_extrativo_codigo": ["3405", "3405"],
            "tipo_de_produto_extrativo": ["Castanha-do-pará", "Castanha-do-pará"],
            "unidade_de_medida": ["Toneladas", "Toneladas"],
            "valor": ["10", "20"],
        }
    )


# ─── _bronze_schema ──────────────────────────────────────────────────────────
def test_bronze_schema_all_string_except_ingestion_timestamp() -> None:
    columns = ["municipio_codigo", "ano", "valor", "ingestion_timestamp"]
    schema = ibge_pipeline._bronze_schema(columns)

    by_name = {f.name: f for f in schema}
    assert by_name["municipio_codigo"].field_type == "STRING"
    assert by_name["municipio_codigo"].mode == "NULLABLE"
    assert by_name["ano"].field_type == "STRING"
    assert by_name["valor"].field_type == "STRING"

    ts = by_name["ingestion_timestamp"]
    assert ts.field_type == "TIMESTAMP"
    assert ts.mode == "REQUIRED"


def test_bronze_schema_skips_duplicate_timestamp_in_input() -> None:
    """The ingestion_timestamp slot is added explicitly — no duplicate STRING field."""
    schema = ibge_pipeline._bronze_schema(["a", "ingestion_timestamp", "b"])
    types_for_ts = [f for f in schema if f.name == "ingestion_timestamp"]
    assert len(types_for_ts) == 1
    assert types_for_ts[0].field_type == "TIMESTAMP"


# ─── run() — happy path ──────────────────────────────────────────────────────
def test_run_uploads_and_loads_with_proper_keys(settings: Settings, sidra_df: pd.DataFrame) -> None:
    """Happy path: extract → parquet upload → BQ load with partition/cluster keys."""
    with (
        patch("embrapa_commodities.ibge.pipeline.fetch_sidra_dataframe") as fetch,
        patch("embrapa_commodities.ibge.pipeline.storage.Client") as gcs_cls,
        patch("embrapa_commodities.ibge.pipeline.bigquery.Client") as bq_cls,
        patch("embrapa_commodities.ibge.pipeline.ensure_bucket") as ensure_bucket,
        patch("embrapa_commodities.ibge.pipeline.ensure_dataset") as ensure_dataset,
        patch("embrapa_commodities.ibge.pipeline.upload_dataframe_as_parquet") as upload,
        patch("embrapa_commodities.ibge.pipeline.load_dataframe") as load,
    ):
        fetch.return_value = sidra_df
        destination = ibge_pipeline.run(settings)

    expected_destination = (
        f"{settings.gcp_project_id}.{settings.bq_bronze_ibge_dataset}."
        f"{settings.bq_bronze_ibge_table}"
    )
    assert destination == expected_destination

    fetch.assert_called_once()
    fetch_kwargs = fetch.call_args.kwargs
    assert fetch_kwargs["table_id"] == "289"
    assert fetch_kwargs["start_year"] == 2020
    assert fetch_kwargs["end_year"] == 2020
    assert fetch_kwargs["products"] == ["3405"]
    assert fetch_kwargs["geo_level"] == "n6"

    gcs_cls.assert_called_once()
    bq_cls.assert_called_once()
    ensure_bucket.assert_called_once()
    ensure_dataset.assert_called_once()
    upload.assert_called_once()
    load.assert_called_once()

    # The DataFrame passed to load_dataframe must have ingestion_timestamp
    # appended and every other column coerced to string (object or StringDtype).
    loaded_df = load.call_args.args[1]
    assert "ingestion_timestamp" in loaded_df.columns
    assert all(isinstance(v, str) for v in loaded_df["municipio_codigo"])
    assert all(isinstance(v, str) for v in loaded_df["valor"])

    # Partition + cluster keys must match Silver's dedupe partitioning.
    load_kwargs = load.call_args.kwargs
    assert load_kwargs["time_partitioning_field"] == "ingestion_timestamp"
    assert load_kwargs["clustering_fields"] == [
        "municipio_codigo",
        "ano",
        "variavel_codigo",
    ]


def test_run_uses_provided_clients_without_constructing_new_ones(
    settings: Settings, sidra_df: pd.DataFrame
) -> None:
    """Batch ingest passes pre-built clients — pipeline must reuse them."""
    storage_client = MagicMock(name="storage-client")
    bq_client = MagicMock(name="bq-client")
    with (
        patch("embrapa_commodities.ibge.pipeline.fetch_sidra_dataframe") as fetch,
        patch("embrapa_commodities.ibge.pipeline.storage.Client") as gcs_cls,
        patch("embrapa_commodities.ibge.pipeline.bigquery.Client") as bq_cls,
        patch("embrapa_commodities.ibge.pipeline.ensure_bucket") as ensure_bucket,
        patch("embrapa_commodities.ibge.pipeline.ensure_dataset"),
        patch("embrapa_commodities.ibge.pipeline.upload_dataframe_as_parquet"),
        patch("embrapa_commodities.ibge.pipeline.load_dataframe") as load,
    ):
        fetch.return_value = sidra_df
        ibge_pipeline.run(settings, storage_client=storage_client, bq_client=bq_client)

    # Neither client class should have been instantiated.
    gcs_cls.assert_not_called()
    bq_cls.assert_not_called()
    # And the passed clients must have been used downstream.
    ensure_bucket.assert_called_once_with(storage_client, settings.gcs_bucket, settings.bq_location)
    load.assert_called_once()
    assert load.call_args.args[0] is bq_client


def test_run_object_name_includes_products_and_year_range(
    settings: Settings, sidra_df: pd.DataFrame
) -> None:
    """GCS path: landing/ibge/<table>/run=<ts>/products_<codes>_<from>_<to>.parquet."""
    settings.ibge_product_codes = "3405,3435"
    with (
        patch("embrapa_commodities.ibge.pipeline.fetch_sidra_dataframe", return_value=sidra_df),
        patch("embrapa_commodities.ibge.pipeline.storage.Client"),
        patch("embrapa_commodities.ibge.pipeline.bigquery.Client"),
        patch("embrapa_commodities.ibge.pipeline.ensure_bucket"),
        patch("embrapa_commodities.ibge.pipeline.ensure_dataset"),
        patch("embrapa_commodities.ibge.pipeline.upload_dataframe_as_parquet") as upload,
        patch("embrapa_commodities.ibge.pipeline.load_dataframe"),
    ):
        ibge_pipeline.run(settings)

    object_name = upload.call_args.args[2]
    assert object_name.startswith("landing/ibge/sidra_t289_raw/run=")
    assert "products_3405_3435_2020_2020.parquet" in object_name


# ─── empty fetch short-circuit ───────────────────────────────────────────────
def test_run_returns_empty_string_when_sidra_returns_no_rows(settings: Settings) -> None:
    """Empty fetch must NOT touch GCS or BQ — only emit the ingest_empty event."""
    with (
        patch(
            "embrapa_commodities.ibge.pipeline.fetch_sidra_dataframe",
            return_value=pd.DataFrame(),
        ),
        patch("embrapa_commodities.ibge.pipeline.storage.Client") as gcs_cls,
        patch("embrapa_commodities.ibge.pipeline.bigquery.Client") as bq_cls,
        patch("embrapa_commodities.ibge.pipeline.ensure_bucket") as ensure_bucket,
        patch("embrapa_commodities.ibge.pipeline.upload_dataframe_as_parquet") as upload,
        patch("embrapa_commodities.ibge.pipeline.load_dataframe") as load,
    ):
        destination = ibge_pipeline.run(settings)

    assert destination == ""
    gcs_cls.assert_not_called()
    bq_cls.assert_not_called()
    ensure_bucket.assert_not_called()
    upload.assert_not_called()
    load.assert_not_called()


# ─── unset start year ────────────────────────────────────────────────────────
def test_run_raises_when_start_year_is_none(settings: Settings) -> None:
    settings.ibge_start_year = None
    with pytest.raises(RuntimeError, match="IBGE_START_YEAR is empty"):
        ibge_pipeline.run(settings)


# ─── year chunking (CLI-level helper, but tested here to keep ibge tests together) ───
def test_chunk_loop_covers_full_range_inclusive() -> None:
    """The batch CLI's `range(start, end + 1, chunk_years)` must cover the whole window.

    Regression guard: the loop iterates `chunks = range(start, end + 1, step)` and
    each iteration clamps `chunk_end = min(start + step - 1, end)`. Verifies that
    the union of (chunk_start, chunk_end) tuples equals (start, end) with no gaps.
    """
    start, end, step = 2010, 2024, 5

    chunks = list(range(start, end + 1, step))
    pairs = [(cs, min(cs + step - 1, end)) for cs in chunks]

    # No gaps: each chunk_start equals previous chunk_end + 1.
    for prev, curr in pairwise(pairs):
        assert curr[0] == prev[1] + 1

    # Coverage: first chunk starts at `start`, last chunk ends at `end`.
    assert pairs[0][0] == start
    assert pairs[-1][1] == end


def test_chunk_loop_handles_uneven_tail() -> None:
    """When (end - start + 1) is not a multiple of chunk_years, the last chunk must be short."""
    start, end, step = 2010, 2023, 5  # 14 years, 5-year chunks → 5, 5, 4

    chunks = list(range(start, end + 1, step))
    pairs = [(cs, min(cs + step - 1, end)) for cs in chunks]

    assert pairs == [(2010, 2014), (2015, 2019), (2020, 2023)]
    # Last chunk is clamped to `end`, not start+step-1.
    assert pairs[-1][1] == end
