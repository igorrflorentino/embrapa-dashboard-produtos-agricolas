"""Tests for the Comex Stat Bronze pipeline (delta planning + land/load shape).

GCP is fully mocked. The delta unit is (flow, year): the end year is always
re-fetched (MDIC revises it monthly), past years already in Bronze are skipped.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from google.cloud.exceptions import NotFound

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
    """One export row already shaped to SOURCE_COLUMNS (import-only cols NaN)."""
    row = {c: "x" for c in client.SOURCE_COLUMNS}
    row["CO_NCM"] = "08012100"
    row["VL_FRETE"] = None
    row["VL_SEGURO"] = None
    return pd.DataFrame([row]).reindex(columns=client.SOURCE_COLUMNS)


# ─── bronze_schema ────────────────────────────────────────────────────────────
def test_bronze_schema_shape() -> None:
    schema = pipeline.bronze_schema()
    names = [f.name for f in schema]
    assert names == ["flow", *client.SOURCE_COLUMNS, "ingestion_timestamp"]
    by_name = {f.name: f for f in schema}
    assert by_name["flow"].mode == "REQUIRED"
    assert by_name["ingestion_timestamp"].field_type == "TIMESTAMP"
    assert by_name["VL_FRETE"].mode == "NULLABLE"  # NULL for export rows


# ─── loaded_years ─────────────────────────────────────────────────────────────
def test_loaded_years_returns_empty_when_table_missing() -> None:
    bq = MagicMock()
    bq.query.side_effect = NotFound("no table")
    assert pipeline.loaded_years(bq, "proj.ds.tbl", "export") == set()


def test_loaded_years_parses_distinct_years() -> None:
    bq = MagicMock()
    bq.query.return_value.result.return_value = [
        MagicMock(y="2020"),
        MagicMock(y="2021"),
        MagicMock(y=None),  # tolerated, skipped
    ]
    assert pipeline.loaded_years(bq, "proj.ds.tbl", "export") == {2020, 2021}


# ─── plan_chunks ──────────────────────────────────────────────────────────────
def test_plan_chunks_full_covers_whole_window_both_flows(settings) -> None:
    bq = MagicMock()
    chunks = pipeline.plan_chunks(settings, bq, "proj.ds.tbl", full=True)
    bq.query.assert_not_called()  # full mode never looks up loaded years
    expected = [(f, y) for f in ("export", "import") for y in range(2020, 2024)]
    assert chunks == expected


def test_plan_chunks_delta_refetches_end_year_and_missing_past(settings) -> None:
    # export has 2020-2022 loaded; import has nothing loaded.
    def fake_loaded(_bq, _tbl, flow):
        return {2020, 2021, 2022} if flow == "export" else set()

    with patch.object(pipeline, "loaded_years", side_effect=fake_loaded):
        chunks = pipeline.plan_chunks(settings, MagicMock(), "proj.ds.tbl", full=False)

    # export: only 2023 (end year, always re-fetched) — 2020-2022 already loaded.
    assert ("export", 2023) in chunks
    assert ("export", 2020) not in chunks
    # import: nothing loaded → every year.
    assert [(f, y) for (f, y) in chunks if f == "import"] == [
        ("import", y) for y in range(2020, 2024)
    ]


# ─── ingest_one ───────────────────────────────────────────────────────────────
def test_ingest_one_empty_skips_load(settings) -> None:
    with (
        patch.object(
            client, "fetch_flow_year", return_value=pd.DataFrame(columns=client.SOURCE_COLUMNS)
        ),
        patch.object(pipeline, "land_and_load") as land,
    ):
        dest = pipeline.ingest_one(
            settings,
            "export",
            2023,
            storage_client=MagicMock(),
            bq_client=MagicMock(),
            table_fqn="proj.ds.tbl",
        )
    assert dest == ""
    land.assert_not_called()


def test_ingest_one_lands_with_flow_schema_and_clustering(settings) -> None:
    with (
        patch.object(client, "fetch_flow_year", return_value=_filtered_df()),
        patch.object(pipeline, "land_and_load", return_value="proj.ds.tbl") as land,
    ):
        dest = pipeline.ingest_one(
            settings,
            "export",
            2023,
            storage_client=MagicMock(),
            bq_client=MagicMock(),
            table_fqn="proj.ds.tbl",
        )
    assert dest == "proj.ds.tbl"
    df = land.call_args.args[0]
    kwargs = land.call_args.kwargs
    # flow stamped, column order canonical, timestamp typed.
    assert list(df.columns) == ["flow", *client.SOURCE_COLUMNS, "ingestion_timestamp"]
    assert (df["flow"] == "export").all()
    # NaN import-only columns landed as SQL NULL, not the string "nan".
    assert df["VL_FRETE"].iloc[0] is None
    assert kwargs["source"] == "comex"
    assert kwargs["object_basename"] == "EXP_2023"
    assert kwargs["clustering_fields"] == pipeline.CLUSTERING_FIELDS
    assert [f.name for f in kwargs["schema"]] == [
        "flow",
        *client.SOURCE_COLUMNS,
        "ingestion_timestamp",
    ]


# ─── run ──────────────────────────────────────────────────────────────────────
def test_run_loops_planned_chunks_and_returns_last_destination(settings) -> None:
    with (
        patch.object(pipeline, "get_credentials", return_value=None),
        patch("embrapa_commodities.comex.pipeline.bigquery.Client"),
        patch("embrapa_commodities.comex.pipeline.storage.Client"),
        patch.object(pipeline, "ensure_destination", return_value="proj.ds.tbl"),
        patch.object(
            pipeline,
            "plan_chunks",
            return_value=[("export", 2022), ("export", 2023)],
        ),
        patch.object(pipeline, "ingest_one", side_effect=["", "proj.ds.tbl"]) as ingest,
    ):
        dest = pipeline.run(settings, full=False)
    assert dest == "proj.ds.tbl"
    assert ingest.call_count == 2


def test_run_returns_empty_when_nothing_planned(settings) -> None:
    with (
        patch.object(pipeline, "get_credentials", return_value=None),
        patch("embrapa_commodities.comex.pipeline.bigquery.Client"),
        patch("embrapa_commodities.comex.pipeline.storage.Client"),
        patch.object(pipeline, "ensure_destination", return_value="proj.ds.tbl"),
        patch.object(pipeline, "plan_chunks", return_value=[]),
        patch.object(pipeline, "ingest_one") as ingest,
    ):
        dest = pipeline.run(settings, full=False)
    assert dest == ""
    ingest.assert_not_called()
