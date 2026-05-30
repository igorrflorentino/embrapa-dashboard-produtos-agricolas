"""Tests for the two-phase Comex pipeline (sync_raw + bronze_one). GCP mocked.

Phase 1 archives the verbatim CSV→Parquet to the raw zone only when the source
ETag changed; Phase 2 filters the raw Parquet and loads Bronze.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from embrapa_commodities.comex import client, pipeline
from embrapa_commodities.config import Settings


@pytest.fixture
def settings() -> Settings:
    return Settings(
        gcp_project_id="test-project",
        gcs_bucket="test-bucket",
        comex_flows="export,import",
        comex_ncm_codes="08012100:castanha_com_casca,08012200:castanha_sem_casca",
        comex_chapter_codes="44:madeira_carvao",
        comex_start_year=2020,
        comex_end_year=2023,
        _env_file=None,
    )  # type: ignore[call-arg]


def _filtered_df() -> pd.DataFrame:
    row = {c: "x" for c in client.SOURCE_COLUMNS}
    row["CO_NCM"] = "08012100"
    row["VL_FRETE"] = None
    row["VL_SEGURO"] = None
    return pd.DataFrame([row]).reindex(columns=client.SOURCE_COLUMNS)


# ─── all_chunks ──────────────────────────────────────────────────────────────
def test_all_chunks_enumerates_every_flow_year(settings) -> None:
    chunks = pipeline.all_chunks(settings)
    assert chunks == [(f, y) for f in ("export", "import") for y in range(2020, 2024)]


# ─── _raw_is_current ─────────────────────────────────────────────────────────
def test_raw_is_current_false_when_no_archive() -> None:
    assert pipeline._raw_is_current(None, {"source_etag": "a"}) is False


def test_raw_is_current_true_on_matching_etag() -> None:
    assert pipeline._raw_is_current({"source_etag": "a"}, {"source_etag": "a"}) is True


def test_raw_is_current_false_on_changed_etag() -> None:
    assert pipeline._raw_is_current({"source_etag": "a"}, {"source_etag": "b"}) is False


def test_raw_is_current_falls_back_to_last_modified() -> None:
    stored = {"source_last_modified": "Mon, 01 Jan 2024"}
    assert pipeline._raw_is_current(stored, {"source_last_modified": "Mon, 01 Jan 2024"}) is True


def test_raw_is_current_etag_takes_precedence_over_last_modified() -> None:
    # ETag present in both but differs → not current, even if last-modified matches.
    stored = {"source_etag": "a", "source_last_modified": "same"}
    head = {"source_etag": "b", "source_last_modified": "same"}
    assert pipeline._raw_is_current(stored, head) is False


# ─── bronze_schema ───────────────────────────────────────────────────────────
def test_bronze_schema_shape() -> None:
    schema = pipeline.bronze_schema()
    assert [f.name for f in schema] == ["flow", *client.SOURCE_COLUMNS, "ingestion_timestamp"]
    by_name = {f.name: f for f in schema}
    assert by_name["flow"].mode == "REQUIRED"
    assert by_name["VL_FRETE"].mode == "NULLABLE"
    assert by_name["ingestion_timestamp"].field_type == "TIMESTAMP"


# ─── sync_raw (Phase 1) ──────────────────────────────────────────────────────
def test_sync_raw_skips_when_source_unchanged(settings) -> None:
    with (
        patch.object(client, "head_source", return_value={"source_etag": "v1"}),
        patch.object(pipeline, "raw_provenance", return_value={"source_etag": "v1"}),
        patch.object(client, "extract_to_parquet") as extract,
        patch.object(pipeline, "land_raw_file") as land,
    ):
        changed = pipeline.sync_raw(settings, "export", 2022, storage_client=MagicMock())
    assert changed is False
    extract.assert_not_called()
    land.assert_not_called()


def test_sync_raw_extracts_and_lands_when_new(settings) -> None:
    with (
        patch.object(client, "head_source", return_value={"source_etag": "v2", "source_url": "u"}),
        patch.object(pipeline, "raw_provenance", return_value=None),  # nothing archived
        patch.object(client, "extract_to_parquet", return_value=123) as extract,
        patch.object(pipeline, "land_raw_file") as land,
    ):
        changed = pipeline.sync_raw(settings, "export", 2023, storage_client=MagicMock())
    assert changed is True
    extract.assert_called_once()
    land_kwargs = land.call_args.kwargs
    assert land_kwargs["source"] == "comex"
    assert land_kwargs["dataset"] == pipeline.RAW_DATASET
    assert land_kwargs["basename"] == "EXP_2023"
    assert land_kwargs["provenance"]["source_etag"] == "v2"
    assert land_kwargs["rows"] == 123


def test_sync_raw_force_ignores_freshness(settings) -> None:
    with (
        patch.object(client, "head_source", return_value={"source_etag": "v1"}),
        patch.object(pipeline, "raw_provenance", return_value={"source_etag": "v1"}) as prov,
        patch.object(client, "extract_to_parquet", return_value=1),
        patch.object(pipeline, "land_raw_file"),
    ):
        changed = pipeline.sync_raw(
            settings, "export", 2022, storage_client=MagicMock(), force=True
        )
    assert changed is True
    prov.assert_not_called()  # force skips the freshness lookup entirely


# ─── bronze_one (Phase 2) ────────────────────────────────────────────────────
def test_bronze_one_empty_skips_load(settings) -> None:
    with (
        patch.object(pipeline, "download_raw", return_value=b"parquet"),
        patch.object(
            client, "filter_products", return_value=pd.DataFrame(columns=client.SOURCE_COLUMNS)
        ),
        patch.object(pipeline, "load_dataframe") as load,
    ):
        dest = pipeline.bronze_one(
            settings,
            "export",
            2023,
            storage_client=MagicMock(),
            bq_client=MagicMock(),
            table_fqn="proj.ds.tbl",
        )
    assert dest == ""
    load.assert_not_called()


def test_bronze_one_loads_with_flow_schema_and_clustering(settings) -> None:
    with (
        patch.object(pipeline, "download_raw", return_value=b"parquet"),
        patch.object(client, "filter_products", return_value=_filtered_df()),
        patch.object(pipeline, "load_dataframe") as load,
    ):
        dest = pipeline.bronze_one(
            settings,
            "export",
            2023,
            storage_client=MagicMock(),
            bq_client=MagicMock(),
            table_fqn="proj.ds.tbl",
        )
    assert dest == "proj.ds.tbl"
    df = load.call_args.args[1]
    assert list(df.columns) == ["flow", *client.SOURCE_COLUMNS, "ingestion_timestamp"]
    assert (df["flow"] == "export").all()
    assert df["VL_FRETE"].iloc[0] is None  # NaN → SQL NULL, not "nan"
    kwargs = load.call_args.kwargs
    assert kwargs["clustering_fields"] == pipeline.CLUSTERING_FIELDS
    assert kwargs["time_partitioning_field"] == "ingestion_timestamp"


# ─── run orchestration ───────────────────────────────────────────────────────
def test_run_loads_bronze_only_for_changed_chunks(settings) -> None:
    # export 2020 changed, everything else unchanged → 1 bronze load.
    def fake_sync(_s, flow, year, *, storage_client, force):
        return flow == "export" and year == 2020

    with (
        patch.object(pipeline, "get_credentials", return_value=None),
        patch("embrapa_commodities.comex.pipeline.bigquery.Client"),
        patch("embrapa_commodities.comex.pipeline.storage.Client"),
        patch.object(pipeline, "ensure_destination", return_value="proj.ds.tbl"),
        patch.object(pipeline, "sync_raw", side_effect=fake_sync),
        patch.object(pipeline, "bronze_one", return_value="proj.ds.tbl") as bronze,
    ):
        dest = pipeline.run(settings, full=False)
    assert dest == "proj.ds.tbl"
    assert bronze.call_count == 1
    assert bronze.call_args.args[1:3] == ("export", 2020)


def test_run_from_raw_skips_sync_and_uses_has_raw(settings) -> None:
    with (
        patch.object(pipeline, "get_credentials", return_value=None),
        patch("embrapa_commodities.comex.pipeline.bigquery.Client"),
        patch("embrapa_commodities.comex.pipeline.storage.Client"),
        patch.object(pipeline, "ensure_destination", return_value="proj.ds.tbl"),
        patch.object(pipeline, "sync_raw") as sync,
        patch.object(pipeline, "has_raw", return_value=True),
        patch.object(pipeline, "bronze_one", return_value="proj.ds.tbl") as bronze,
    ):
        dest = pipeline.run(settings, from_raw=True)
    assert dest == "proj.ds.tbl"
    sync.assert_not_called()  # no internet in from-raw mode
    assert bronze.call_count == len(pipeline.all_chunks(settings))  # all 8 chunks rebuilt
