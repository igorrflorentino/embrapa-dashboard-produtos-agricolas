"""Tests for the two-phase, chunked, resumable Comtrade pipeline. GCP + API mocked.

Phase 1 (sync_raw) archives one (year, reporter-batch) keyed call to the raw zone,
skipping past-year chunks already archived but always re-fetching the latest year;
Phase 2 (bronze_one) stamps ingestion_timestamp and loads Bronze. ``run`` enumerates
reporters and loops the chunk plan, resumable across a daily-quota interruption.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from embrapa_commodities.comtrade import client, pipeline
from embrapa_commodities.config import Settings


@pytest.fixture
def settings() -> Settings:
    return Settings(
        gcp_project_id="test-project",
        gcs_bucket="test-bucket",
        comtrade_api_key="secret-key",
        comtrade_cmd_codes="0801:castanha,44:madeira_carvao",
        comtrade_flows="X,M",
        comtrade_reporters="all",
        comtrade_start_year=2022,
        comtrade_end_year=2023,
        _env_file=None,
    )  # type: ignore[call-arg]


def _bronze_df() -> pd.DataFrame:
    row = {c: "x" for c in client.BRONZE_COLUMNS}
    row["reporterCode"] = "76"
    row["partnerCode"] = "0"
    row["cmdCode"] = "0801"
    row["refYear"] = "2022"
    return pd.DataFrame([row], dtype="string").reindex(columns=client.BRONZE_COLUMNS)


# ─── _reporter_batches / _basename / plan_chunks ─────────────────────────────
def test_reporter_batches_chunks_by_size() -> None:
    reporters = [str(i) for i in range(60)]
    batches = pipeline._reporter_batches(reporters)
    assert len(batches) == 3  # 25 + 25 + 10
    assert [len(b) for b in batches] == [25, 25, 10]
    assert batches[0][0] == "0" and batches[2][-1] == "59"


def test_basename_zero_pads_batch_index() -> None:
    assert pipeline._basename(2022, 3) == "2022_r03"
    assert pipeline._basename(2023, 12) == "2023_r12"


def test_plan_chunks_enumerates_year_then_batch(settings) -> None:
    reporters = [str(i) for i in range(30)]  # 2 batches
    chunks = pipeline.plan_chunks(settings, reporters)
    # 2 years × 2 batches = 4 chunks, year-then-batch order.
    assert [(y, idx) for y, idx, _ in chunks] == [(2022, 0), (2022, 1), (2023, 0), (2023, 1)]
    assert len(chunks[0][2]) == 25 and len(chunks[1][2]) == 5


# ─── bronze_schema ───────────────────────────────────────────────────────────
def test_bronze_schema_shape() -> None:
    schema = pipeline.bronze_schema()
    assert [f.name for f in schema] == [*client.BRONZE_COLUMNS, "ingestion_timestamp"]
    by_name = {f.name: f for f in schema}
    assert by_name["ingestion_timestamp"].field_type == "TIMESTAMP"
    assert by_name["ingestion_timestamp"].mode == "REQUIRED"
    assert by_name["reporterCode"].mode == "NULLABLE"


# ─── sync_raw (Phase 1) ──────────────────────────────────────────────────────
def test_sync_raw_skips_past_year_already_archived(settings) -> None:
    """A non-latest year whose raw exists is skipped — no API call."""
    with (
        patch.object(pipeline, "raw_provenance", return_value={"source": "un-comtrade"}),
        patch.object(client, "fetch_chunk") as fetch,
        patch.object(pipeline, "land_raw") as land,
    ):
        changed = pipeline.sync_raw(settings, 2022, 0, ["76"], storage_client=MagicMock())
    assert changed is False
    fetch.assert_not_called()
    land.assert_not_called()


def test_sync_raw_always_refetches_latest_year(settings) -> None:
    """The latest configured year is re-fetched even when raw already exists."""
    with (
        patch.object(pipeline, "raw_provenance", return_value={"x": "y"}) as prov,
        patch.object(client, "fetch_chunk", return_value=_bronze_df()) as fetch,
        patch.object(pipeline, "land_raw") as land,
    ):
        changed = pipeline.sync_raw(settings, 2023, 0, ["76"], storage_client=MagicMock())
    assert changed is True
    prov.assert_not_called()  # latest year skips the freshness lookup
    fetch.assert_called_once()
    land.assert_called_once()


def test_sync_raw_force_ignores_archive(settings) -> None:
    with (
        patch.object(pipeline, "raw_provenance") as prov,
        patch.object(client, "fetch_chunk", return_value=_bronze_df()),
        patch.object(pipeline, "land_raw"),
    ):
        changed = pipeline.sync_raw(
            settings, 2022, 0, ["76"], storage_client=MagicMock(), force=True
        )
    assert changed is True
    prov.assert_not_called()


def test_sync_raw_empty_response_lands_nothing(settings) -> None:
    with (
        patch.object(pipeline, "raw_provenance", return_value=None),
        patch.object(
            client, "fetch_chunk", return_value=pd.DataFrame(columns=client.BRONZE_COLUMNS)
        ),
        patch.object(pipeline, "land_raw") as land,
    ):
        changed = pipeline.sync_raw(settings, 2022, 0, ["76"], storage_client=MagicMock())
    assert changed is False
    land.assert_not_called()


def test_sync_raw_fetches_and_lands_with_provenance(settings) -> None:
    with (
        patch.object(pipeline, "raw_provenance", return_value=None),
        patch.object(client, "fetch_chunk", return_value=_bronze_df()) as fetch,
        patch.object(pipeline, "land_raw") as land,
    ):
        changed = pipeline.sync_raw(settings, 2022, 1, ["76", "842"], storage_client=MagicMock())
    assert changed is True
    fetch_kwargs = fetch.call_args.kwargs
    assert fetch_kwargs["reporters"] == ["76", "842"]
    assert fetch_kwargs["years"] == [2022]
    assert fetch_kwargs["cmd_codes"] == ["0801", "44"]
    assert fetch_kwargs["flows"] == ["X", "M"]
    land_kwargs = land.call_args.kwargs
    assert land_kwargs["source"] == "comtrade"
    assert land_kwargs["dataset"] == pipeline.RAW_DATASET
    assert land_kwargs["basename"] == "2022_r01"
    assert land_kwargs["provenance"]["source"] == "un-comtrade"
    assert land_kwargs["provenance"]["year"] == "2022"


# ─── bronze_one (Phase 2) ────────────────────────────────────────────────────
def test_bronze_one_empty_raw_skips_load(settings) -> None:
    with (
        patch.object(
            pipeline, "read_raw", return_value=pd.DataFrame(columns=client.BRONZE_COLUMNS)
        ),
        patch.object(pipeline, "load_dataframe") as load,
    ):
        dest = pipeline.bronze_one(
            settings, 2022, 0, storage_client=MagicMock(), bq_client=MagicMock(), table_fqn="p.d.t"
        )
    assert dest == ""
    load.assert_not_called()


def test_bronze_one_loads_with_timestamp_and_clustering(settings) -> None:
    with (
        patch.object(pipeline, "read_raw", return_value=_bronze_df()),
        patch.object(pipeline, "load_dataframe") as load,
    ):
        dest = pipeline.bronze_one(
            settings, 2022, 0, storage_client=MagicMock(), bq_client=MagicMock(), table_fqn="p.d.t"
        )
    assert dest == "p.d.t"
    df = load.call_args.args[1]
    assert list(df.columns) == [*client.BRONZE_COLUMNS, "ingestion_timestamp"]
    kwargs = load.call_args.kwargs
    assert kwargs["clustering_fields"] == pipeline.CLUSTERING_FIELDS
    assert kwargs["time_partitioning_field"] == "ingestion_timestamp"


# ─── run orchestration ───────────────────────────────────────────────────────
def test_run_raises_without_api_key() -> None:
    s = Settings(gcp_project_id="p", gcs_bucket="b", comtrade_api_key="", _env_file=None)  # type: ignore[call-arg]
    with pytest.raises(RuntimeError, match="COMTRADE_API_KEY"):
        pipeline.run(s)


def test_run_enumerates_reporters_and_loads_changed_chunks(settings) -> None:
    # Only (2022, batch 0) "changed"; the rest skip → exactly one bronze load.
    def fake_sync(_s, year, idx, _batch, *, storage_client, force):
        return year == 2022 and idx == 0

    with (
        patch.object(pipeline, "get_credentials", return_value=None),
        patch("embrapa_commodities.comtrade.pipeline.bigquery.Client"),
        patch("embrapa_commodities.comtrade.pipeline.storage.Client"),
        patch.object(pipeline, "ensure_destination", return_value="p.d.t"),
        patch.object(client, "list_reporters", return_value=[str(i) for i in range(30)]) as lr,
        patch.object(pipeline, "sync_raw", side_effect=fake_sync),
        patch.object(pipeline, "bronze_one", return_value="p.d.t") as bronze,
    ):
        dest = pipeline.run(settings, full=False)
    assert dest == "p.d.t"
    lr.assert_called_once()  # "all" → enumerate from the reference
    assert bronze.call_count == 1
    assert bronze.call_args.args[1:3] == (2022, 0)


def test_run_from_raw_skips_sync_uses_has_raw(settings) -> None:
    with (
        patch.object(pipeline, "get_credentials", return_value=None),
        patch("embrapa_commodities.comtrade.pipeline.bigquery.Client"),
        patch("embrapa_commodities.comtrade.pipeline.storage.Client"),
        patch.object(pipeline, "ensure_destination", return_value="p.d.t"),
        patch.object(client, "list_reporters", return_value=[str(i) for i in range(30)]),
        patch.object(pipeline, "sync_raw") as sync,
        patch.object(pipeline, "has_raw", return_value=True),
        patch.object(pipeline, "bronze_one", return_value="p.d.t") as bronze,
    ):
        dest = pipeline.run(settings, from_raw=True)
    assert dest == "p.d.t"
    sync.assert_not_called()  # from-raw never touches the API
    # 2 years × 2 batches (30 reporters / 25) = 4 chunks, all rebuilt.
    assert bronze.call_count == 4


def test_run_explicit_reporter_list_skips_enumeration(settings) -> None:
    settings = settings.model_copy(update={"comtrade_reporters": "76,842"})
    with (
        patch.object(pipeline, "get_credentials", return_value=None),
        patch("embrapa_commodities.comtrade.pipeline.bigquery.Client"),
        patch("embrapa_commodities.comtrade.pipeline.storage.Client"),
        patch.object(pipeline, "ensure_destination", return_value="p.d.t"),
        patch.object(client, "list_reporters") as lr,
        patch.object(pipeline, "sync_raw", return_value=False),
        patch.object(pipeline, "bronze_one", return_value="p.d.t"),
    ):
        pipeline.run(settings)
    lr.assert_not_called()  # explicit list → no reference lookup
