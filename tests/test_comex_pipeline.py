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
from embrapa_commodities.core import ChunkOutcome, IngestPartialFailure


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


def test_raw_is_current_never_trusts_content_length_alone(caplog) -> None:
    """Content-Length is a WEAK signal: a same-byte value correction (upstream
    edit that keeps the file the same size) must NOT be misread as unchanged.
    With only Content-Length on both sides — even matching — the function forces a
    re-download and warns, instead of short-circuiting to current."""
    import logging

    stored = {"source_content_length": "12345"}
    head = {"source_content_length": "12345"}  # identical bytes, yet untrusted
    with caplog.at_level(logging.WARNING):
        assert pipeline._raw_is_current(stored, head, label="EXP_2026") is False
    assert any("Content-Length alone is too weak" in r.getMessage() for r in caplog.records)


def test_raw_is_current_strong_id_still_wins_over_content_length() -> None:
    # A matching ETag is still authoritative even when Content-Length is also
    # present — Content-Length is simply ignored, not blocking.
    stored = {"source_etag": "a", "source_content_length": "1"}
    head = {"source_etag": "a", "source_content_length": "2"}
    assert pipeline._raw_is_current(stored, head) is True


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


# ─── needs_bronze (skip-safety) ──────────────────────────────────────────────
def test_needs_bronze_always_true_when_extracted(settings) -> None:
    # A (re)extract always loads — no provenance lookup needed.
    with patch.object(pipeline, "raw_provenance") as prov:
        assert pipeline.needs_bronze(
            settings, "export", 2022, extracted=True, storage_client=MagicMock()
        )
    prov.assert_not_called()


def test_needs_bronze_false_when_unchanged_and_already_loaded(settings) -> None:
    with patch.object(
        pipeline, "raw_provenance", return_value={"source_etag": "v1", "bronze_loaded_at": "2026"}
    ):
        assert not pipeline.needs_bronze(
            settings, "export", 2022, extracted=False, storage_client=MagicMock()
        )


def test_needs_bronze_true_when_unchanged_but_never_loaded(settings) -> None:
    # Raw present (prior run archived it) but no bronze_loaded marker → a prior
    # run aborted before Phase 2. Must still load, not skip.
    with patch.object(pipeline, "raw_provenance", return_value={"source_etag": "v1"}):
        assert pipeline.needs_bronze(
            settings, "export", 2022, extracted=False, storage_client=MagicMock()
        )


# ─── run orchestration ───────────────────────────────────────────────────────
def test_run_loads_bronze_only_for_changed_chunks(settings) -> None:
    # export 2020 changed, everything else unchanged + already loaded → 1 load.
    def fake_sync(_s, flow, year, *, storage_client, force):
        return flow == "export" and year == 2020

    with (
        patch("embrapa_commodities.gcp.clients.get_credentials", return_value=None),
        patch("embrapa_commodities.gcp.clients.bigquery.Client"),
        patch("embrapa_commodities.gcp.clients.storage.Client"),
        patch.object(pipeline, "ensure_destination", return_value="proj.ds.tbl"),
        patch.object(pipeline, "sync_raw", side_effect=fake_sync),
        patch.object(pipeline, "needs_bronze", side_effect=lambda *a, extracted, **k: extracted),
        patch.object(pipeline, "mark_bronze_loaded") as mark,
        patch.object(pipeline, "bronze_one", return_value="proj.ds.tbl") as bronze,
    ):
        dest = pipeline.run(settings, full=False)
    assert dest == "proj.ds.tbl"
    assert bronze.call_count == 1
    assert bronze.call_args.args[1:3] == ("export", 2020)
    assert mark.call_count == 1  # marked loaded after the single Phase 2


def test_run_from_raw_skips_sync_and_uses_has_raw(settings) -> None:
    with (
        patch("embrapa_commodities.gcp.clients.get_credentials", return_value=None),
        patch("embrapa_commodities.gcp.clients.bigquery.Client"),
        patch("embrapa_commodities.gcp.clients.storage.Client"),
        patch.object(pipeline, "ensure_destination", return_value="proj.ds.tbl"),
        patch.object(pipeline, "sync_raw") as sync,
        patch.object(pipeline, "has_raw", return_value=True),
        patch.object(pipeline, "mark_bronze_loaded"),
        patch.object(pipeline, "bronze_one", return_value="proj.ds.tbl") as bronze,
    ):
        dest = pipeline.run(settings, from_raw=True)
    assert dest == "proj.ds.tbl"
    sync.assert_not_called()  # no internet in from-raw mode
    assert bronze.call_count == len(pipeline.all_chunks(settings))  # all 8 chunks rebuilt


def test_run_reloads_unchanged_raw_when_bronze_marker_absent(settings) -> None:
    """Regression: a prior run archived raw then aborted before Phase 2. The raw
    is unchanged (sync_raw → False) but unmarked, so the re-run must still load."""
    with (
        patch("embrapa_commodities.gcp.clients.get_credentials", return_value=None),
        patch("embrapa_commodities.gcp.clients.bigquery.Client"),
        patch("embrapa_commodities.gcp.clients.storage.Client"),
        patch.object(pipeline, "ensure_destination", return_value="proj.ds.tbl"),
        patch.object(pipeline, "sync_raw", return_value=False),  # nothing re-extracted
        patch.object(pipeline, "raw_provenance", return_value={"source_etag": "v1"}),  # no marker
        patch.object(pipeline, "mark_bronze_loaded") as mark,
        patch.object(pipeline, "bronze_one", return_value="proj.ds.tbl") as bronze,
    ):
        pipeline.run(settings, full=False)
    n = len(pipeline.all_chunks(settings))
    assert bronze.call_count == n  # every unchanged-but-unloaded chunk still loads
    assert mark.call_count == n


# ─── continue-on-failure + aggregation (now inside run) ──────────────────────
def test_run_continues_after_chunk_failure_and_raises_aggregate(settings) -> None:
    """A chunk that raises must not strand the rest; with no on_chunk consumer the
    loop finishes every chunk then raises an aggregated IngestPartialFailure."""
    seen: list[tuple[str, int]] = []

    def flaky_sync(_s, flow, year, *, storage_client, force):
        seen.append((flow, year))
        if (flow, year) == ("export", 2021):
            raise RuntimeError("source 503")
        return True

    with (
        patch("embrapa_commodities.gcp.clients.get_credentials", return_value=None),
        patch("embrapa_commodities.gcp.clients.bigquery.Client"),
        patch("embrapa_commodities.gcp.clients.storage.Client"),
        patch.object(pipeline, "ensure_destination", return_value="p.d.t"),
        patch.object(pipeline, "sync_raw", side_effect=flaky_sync),
        patch.object(pipeline, "needs_bronze", side_effect=lambda *a, extracted, **k: extracted),
        patch.object(pipeline, "mark_bronze_loaded"),
        patch.object(pipeline, "bronze_one", return_value="p.d.t"),
        pytest.raises(IngestPartialFailure) as exc,
    ):
        pipeline.run(settings, full=False)

    # Every (flow, year) was attempted despite the 2021 failure.
    assert seen == pipeline.all_chunks(settings)
    # The aggregate names exactly the one failed chunk.
    assert [cid for cid, _ in exc.value.failures] == ["EXP_2021"]


def test_run_with_on_chunk_reports_each_outcome_and_does_not_raise(settings) -> None:
    """With an on_chunk consumer, run() forwards a ChunkOutcome per chunk and
    returns normally even on failure (the consumer owns the exit decision)."""
    outcomes: list[ChunkOutcome] = []

    def flaky_sync(_s, flow, year, *, storage_client, force):
        if (flow, year) == ("import", 2020):
            raise RuntimeError("boom")
        return True

    with (
        patch("embrapa_commodities.gcp.clients.get_credentials", return_value=None),
        patch("embrapa_commodities.gcp.clients.bigquery.Client"),
        patch("embrapa_commodities.gcp.clients.storage.Client"),
        patch.object(pipeline, "ensure_destination", return_value="p.d.t"),
        patch.object(pipeline, "sync_raw", side_effect=flaky_sync),
        patch.object(pipeline, "needs_bronze", side_effect=lambda *a, extracted, **k: extracted),
        patch.object(pipeline, "mark_bronze_loaded"),
        patch.object(pipeline, "bronze_one", return_value="p.d.t"),
    ):
        starts: list[str] = []
        pipeline.run(
            settings,
            full=False,
            on_chunk_start=starts.append,
            on_chunk=outcomes.append,
        )

    n = len(pipeline.all_chunks(settings))
    assert len(outcomes) == n and len(starts) == n
    failed = [o for o in outcomes if o.status == "failed"]
    assert [o.chunk_id for o in failed] == ["IMP_2020"]


def test_process_chunk_current_year_404_is_skipped_not_failed(settings) -> None:
    """A 404 for the latest configured year (file not published yet) is a skip,
    so the blind cron never aborts on it."""
    # settings.comex_end_year == 2023 (fixture) → 2023 is the "current" year.
    with patch.object(
        pipeline, "sync_raw", side_effect=client.ComexRequestError("HTTP 404 for .../EXP_2023.csv")
    ):
        outcome = pipeline.process_chunk(
            settings,
            "export",
            2023,
            storage_client=MagicMock(),
            bq_client=MagicMock(),
            table_fqn="p.d.t",
        )
    assert outcome.status == "skipped"
    assert "404" in outcome.detail


def test_process_chunk_does_not_mark_loaded_when_no_product_matched(settings) -> None:
    """Regression: bronze_one returns "" only when NO configured product matched.
    Stamping bronze_loaded there would freeze the raw out of Phase 2 forever, so a
    later product addition could never backfill it. The stamp must be skipped."""
    with (
        patch.object(pipeline, "sync_raw", return_value=True),
        patch.object(pipeline, "needs_bronze", return_value=True),
        patch.object(pipeline, "bronze_one", return_value=""),  # nothing matched
        patch.object(pipeline, "mark_bronze_loaded") as mark,
    ):
        outcome = pipeline.process_chunk(
            settings,
            "export",
            2022,
            storage_client=MagicMock(),
            bq_client=MagicMock(),
            table_fqn="p.d.t",
        )
    assert outcome.status == "skipped"
    assert "no configured products" in outcome.detail
    mark.assert_not_called()  # left unmarked so a future product can backfill


def test_process_chunk_marks_loaded_when_product_matched(settings) -> None:
    """The happy path still stamps bronze_loaded after a real load (at-least-once),
    so an unchanged raw is correctly skipped on the next run."""
    with (
        patch.object(pipeline, "sync_raw", return_value=True),
        patch.object(pipeline, "needs_bronze", return_value=True),
        patch.object(pipeline, "bronze_one", return_value="p.d.t"),
        patch.object(pipeline, "mark_bronze_loaded") as mark,
    ):
        outcome = pipeline.process_chunk(
            settings,
            "export",
            2022,
            storage_client=MagicMock(),
            bq_client=MagicMock(),
            table_fqn="p.d.t",
        )
    assert outcome.status == "loaded"
    mark.assert_called_once()


def test_process_chunk_404_on_past_year_still_raises(settings) -> None:
    """A 404 on a historical year is anomalous → it must surface, not be skipped."""
    with (
        patch.object(
            pipeline,
            "sync_raw",
            side_effect=client.ComexRequestError("HTTP 404 for .../EXP_2020.csv"),
        ),
        pytest.raises(client.ComexRequestError),
    ):
        pipeline.process_chunk(
            settings,
            "export",
            2020,  # not the latest configured year
            storage_client=MagicMock(),
            bq_client=MagicMock(),
            table_fqn="p.d.t",
        )


# ─── freshness-degradation warning (task 7) ──────────────────────────────────
def test_raw_is_current_warns_when_no_comparable_identifier(caplog) -> None:
    """An archived raw with no comparable freshness header on either side forces a
    re-download AND logs a WARNING so the silent degradation is visible."""
    import logging

    with caplog.at_level(logging.WARNING):
        result = pipeline._raw_is_current(
            {"some_other_meta": "x"}, {"source_url": "u"}, label="EXP_2026"
        )
    assert result is False
    assert any("freshness identifier" in r.message for r in caplog.records)
    assert any("EXP_2026" in r.getMessage() for r in caplog.records)
