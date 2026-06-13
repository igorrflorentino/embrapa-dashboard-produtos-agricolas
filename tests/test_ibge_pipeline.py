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


# ─── run() — two-phase happy path ────────────────────────────────────────────
def _patch_phase2_df(read_raw, sidra_df: pd.DataFrame) -> None:
    """Phase 2 reads the raw archive back — return the same SIDRA frame."""
    read_raw.return_value = sidra_df.astype(str)


def test_run_extracts_to_raw_then_loads_bronze(settings: Settings, sidra_df: pd.DataFrame) -> None:
    """Happy path: SIDRA fetch → land_raw (Phase 1) → read_raw → BQ load (Phase 2)."""
    with (
        patch("embrapa_commodities.ibge.pipeline.fetch_sidra_dataframe") as fetch,
        patch("embrapa_commodities.ibge.pipeline.storage.Client") as gcs_cls,
        patch("embrapa_commodities.ibge.pipeline.bigquery.Client") as bq_cls,
        patch("embrapa_commodities.ibge.pipeline.ensure_dataset") as ensure_dataset,
        patch("embrapa_commodities.ibge.pipeline.land_raw") as land_raw,
        patch("embrapa_commodities.ibge.pipeline.read_raw") as read_raw,
        patch("embrapa_commodities.ibge.pipeline.load_dataframe") as load,
    ):
        fetch.return_value = sidra_df
        _patch_phase2_df(read_raw, sidra_df)
        destination = ibge_pipeline.run(settings)

    expected_destination = (
        f"{settings.gcp_project_id}.{settings.bq_bronze_ibge_dataset}."
        f"{settings.bq_bronze_ibge_table}"
    )
    assert destination == expected_destination

    fetch_kwargs = fetch.call_args.kwargs
    assert fetch_kwargs["table_id"] == "289"
    assert fetch_kwargs["products"] == ["3405"]
    assert fetch_kwargs["geo_level"] == "n6"

    gcs_cls.assert_called_once()
    bq_cls.assert_called_once()
    ensure_dataset.assert_called_once()
    land_raw.assert_called_once()  # Phase 1
    read_raw.assert_called_once()  # Phase 2
    load.assert_called_once()

    # The DataFrame loaded to Bronze must have ingestion_timestamp + string cols.
    loaded_df = load.call_args.args[1]
    assert "ingestion_timestamp" in loaded_df.columns
    assert all(isinstance(v, str) for v in loaded_df["municipio_codigo"])

    load_kwargs = load.call_args.kwargs
    assert load_kwargs["time_partitioning_field"] == "ingestion_timestamp"
    assert load_kwargs["clustering_fields"] == ["municipio_codigo", "ano", "variavel_codigo"]


def test_run_raw_basename_encodes_products_and_window(
    settings: Settings, sidra_df: pd.DataFrame
) -> None:
    """Phase 1 archives raw/ibge/pevs/products_<codes>_<from>_<to>."""
    settings.ibge_product_codes = "3405,3435"
    with (
        patch("embrapa_commodities.ibge.pipeline.fetch_sidra_dataframe", return_value=sidra_df),
        patch("embrapa_commodities.ibge.pipeline.storage.Client"),
        patch("embrapa_commodities.ibge.pipeline.bigquery.Client"),
        patch("embrapa_commodities.ibge.pipeline.ensure_dataset"),
        patch("embrapa_commodities.ibge.pipeline.land_raw") as land_raw,
        patch("embrapa_commodities.ibge.pipeline.read_raw") as read_raw,
        patch("embrapa_commodities.ibge.pipeline.load_dataframe"),
    ):
        _patch_phase2_df(read_raw, sidra_df)
        ibge_pipeline.run(settings)

    kwargs = land_raw.call_args.kwargs
    assert kwargs["source"] == "ibge"
    assert kwargs["dataset"] == ibge_pipeline.RAW_DATASET
    assert kwargs["basename"] == "products_3405_3435_2020_2020"


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
        patch("embrapa_commodities.ibge.pipeline.ensure_dataset"),
        patch("embrapa_commodities.ibge.pipeline.land_raw") as land_raw,
        patch("embrapa_commodities.ibge.pipeline.read_raw") as read_raw,
        patch("embrapa_commodities.ibge.pipeline.load_dataframe") as load,
    ):
        fetch.return_value = sidra_df
        _patch_phase2_df(read_raw, sidra_df)
        ibge_pipeline.run(settings, storage_client=storage_client, bq_client=bq_client)

    gcs_cls.assert_not_called()
    bq_cls.assert_not_called()
    assert land_raw.call_args.kwargs["storage_client"] is storage_client
    assert load.call_args.args[0] is bq_client


def test_run_from_raw_skips_fetch_and_rebuilds_bronze(
    settings: Settings, sidra_df: pd.DataFrame
) -> None:
    """--from-raw rebuilds Bronze from the archived raw without querying SIDRA."""
    with (
        patch("embrapa_commodities.ibge.pipeline.fetch_sidra_dataframe") as fetch,
        patch("embrapa_commodities.ibge.pipeline.storage.Client"),
        patch("embrapa_commodities.ibge.pipeline.bigquery.Client"),
        patch("embrapa_commodities.ibge.pipeline.ensure_dataset"),
        patch(
            "embrapa_commodities.ibge.pipeline.list_raw",
            return_value=["products_3405_2020_2020"],
        ),
        patch("embrapa_commodities.ibge.pipeline.read_raw") as read_raw,
        patch("embrapa_commodities.ibge.pipeline.load_dataframe") as load,
    ):
        _patch_phase2_df(read_raw, sidra_df)
        destination = ibge_pipeline.run(settings, from_raw=True)

    fetch.assert_not_called()  # no SIDRA query
    read_raw.assert_called_once()
    load.assert_called_once()
    assert destination.endswith(settings.bq_bronze_ibge_table)


# ─── empty fetch short-circuit ───────────────────────────────────────────────
def test_run_returns_empty_string_when_sidra_returns_no_rows(settings: Settings) -> None:
    """Empty fetch must NOT archive raw or load Bronze — only emit ingest_empty."""
    with (
        patch(
            "embrapa_commodities.ibge.pipeline.fetch_sidra_dataframe",
            return_value=pd.DataFrame(),
        ),
        patch("embrapa_commodities.ibge.pipeline.storage.Client"),
        patch("embrapa_commodities.ibge.pipeline.bigquery.Client"),
        patch("embrapa_commodities.ibge.pipeline.ensure_dataset"),
        patch("embrapa_commodities.ibge.pipeline.land_raw") as land_raw,
        patch("embrapa_commodities.ibge.pipeline.load_dataframe") as load,
    ):
        destination = ibge_pipeline.run(settings)

    assert destination == ""
    land_raw.assert_not_called()
    load.assert_not_called()


# ─── unset start year ────────────────────────────────────────────────────────
def test_run_raises_when_start_year_is_none(settings: Settings) -> None:
    settings.ibge_start_year = None
    with (
        patch("embrapa_commodities.ibge.pipeline.storage.Client"),
        patch("embrapa_commodities.ibge.pipeline.bigquery.Client"),
        patch("embrapa_commodities.ibge.pipeline.ensure_dataset"),
        pytest.raises(RuntimeError, match="IBGE_START_YEAR is empty"),
    ):
        ibge_pipeline.run(settings)


# ─── delta-by-default ────────────────────────────────────────────────────────
def test_run_delta_rewinds_start_to_recent_years(
    settings: Settings, sidra_df: pd.DataFrame
) -> None:
    """A routine run re-fetches only from (latest Bronze year − overlap), not 1986."""
    settings.ibge_start_year = 1986
    settings.ibge_end_year = 2024
    with (
        patch("embrapa_commodities.ibge.pipeline.fetch_sidra_dataframe") as fetch,
        patch("embrapa_commodities.ibge.pipeline.storage.Client"),
        patch("embrapa_commodities.ibge.pipeline.bigquery.Client"),
        patch("embrapa_commodities.ibge.pipeline.ensure_dataset"),
        patch("embrapa_commodities.ibge.pipeline.latest_reference_year", return_value=2023),
        patch("embrapa_commodities.ibge.pipeline.land_raw"),
        patch("embrapa_commodities.ibge.pipeline.read_raw") as read_raw,
        patch("embrapa_commodities.ibge.pipeline.load_dataframe"),
    ):
        fetch.return_value = sidra_df
        _patch_phase2_df(read_raw, sidra_df)
        ibge_pipeline.run(settings)  # delta is the default

    # overlap default = 1 → start = 2023 − 1 = 2022, NOT the configured 1986.
    assert fetch.call_args.kwargs["start_year"] == 2022
    assert fetch.call_args.kwargs["end_year"] == 2024


def test_run_full_bypasses_delta_and_uses_configured_window(
    settings: Settings, sidra_df: pd.DataFrame
) -> None:
    """--full ignores the Bronze lookup and re-fetches the whole configured window."""
    settings.ibge_start_year = 1986
    settings.ibge_end_year = 2024
    with (
        patch("embrapa_commodities.ibge.pipeline.fetch_sidra_dataframe") as fetch,
        patch("embrapa_commodities.ibge.pipeline.storage.Client"),
        patch("embrapa_commodities.ibge.pipeline.bigquery.Client"),
        patch("embrapa_commodities.ibge.pipeline.ensure_dataset"),
        patch("embrapa_commodities.ibge.pipeline.latest_reference_year") as latest,
        patch("embrapa_commodities.ibge.pipeline.land_raw"),
        patch("embrapa_commodities.ibge.pipeline.read_raw") as read_raw,
        patch("embrapa_commodities.ibge.pipeline.load_dataframe"),
    ):
        fetch.return_value = sidra_df
        _patch_phase2_df(read_raw, sidra_df)
        ibge_pipeline.run(settings, full=True)

    latest.assert_not_called()  # no Bronze lookup in full mode
    assert fetch.call_args.kwargs["start_year"] == 1986


def test_run_delta_noop_when_bronze_already_at_end_year(settings: Settings) -> None:
    """Bronze already holds IBGE_END_YEAR → clean no-op: no SIDRA fetch, no load,
    no inverted window. Regression for the start>end IndexError."""
    settings.ibge_start_year = 1986
    settings.ibge_end_year = 2024
    with (
        patch("embrapa_commodities.ibge.pipeline.fetch_sidra_dataframe") as fetch,
        patch("embrapa_commodities.ibge.pipeline.storage.Client"),
        patch("embrapa_commodities.ibge.pipeline.bigquery.Client"),
        patch("embrapa_commodities.ibge.pipeline.ensure_dataset"),
        # Bronze is already AT the configured end year (and would push start past end).
        patch("embrapa_commodities.ibge.pipeline.latest_reference_year", return_value=2024),
        patch("embrapa_commodities.ibge.pipeline.land_raw") as land_raw,
        patch("embrapa_commodities.ibge.pipeline.load_dataframe") as load,
    ):
        destination = ibge_pipeline.run(settings)  # delta default

    assert destination == ""
    fetch.assert_not_called()  # no SIDRA query at all
    land_raw.assert_not_called()
    load.assert_not_called()


def test_run_delta_noop_when_bronze_ahead_of_end_year(settings: Settings) -> None:
    """Bronze ahead of IBGE_END_YEAR (operator lowered it) must also no-op cleanly,
    never build start>end."""
    settings.ibge_start_year = 1986
    settings.ibge_end_year = 2020
    with (
        patch("embrapa_commodities.ibge.pipeline.fetch_sidra_dataframe") as fetch,
        patch("embrapa_commodities.ibge.pipeline.storage.Client"),
        patch("embrapa_commodities.ibge.pipeline.bigquery.Client"),
        patch("embrapa_commodities.ibge.pipeline.ensure_dataset"),
        patch("embrapa_commodities.ibge.pipeline.latest_reference_year", return_value=2024),
        patch("embrapa_commodities.ibge.pipeline.load_dataframe") as load,
    ):
        assert ibge_pipeline.run(settings) == ""
    fetch.assert_not_called()
    load.assert_not_called()


def test_delta_start_year_clamps_effective_start_to_end_year(settings: Settings) -> None:
    """When overlap would push the start beyond end_year but Bronze is just under
    end_year, the effective start is clamped to end_year (never inverted)."""
    settings.ibge_start_year = 1986
    settings.ibge_end_year = 2024
    settings.ibge_delta_overlap_years = 0
    with patch("embrapa_commodities.ibge.pipeline.latest_reference_year", return_value=2023):
        rewound = ibge_pipeline._delta_start_year(settings, MagicMock())
    assert rewound is not None
    # last_year - overlap = 2023, clamped <= end_year(2024) → 2023; window [2023, 2024] valid.
    assert rewound.ibge_start_year == 2023
    assert rewound.ibge_start_year <= rewound.ibge_end_year


def test_run_delta_cold_bronze_keeps_configured_window(
    settings: Settings, sidra_df: pd.DataFrame
) -> None:
    """When Bronze has no data yet (latest year is None), delta falls back to full."""
    settings.ibge_start_year = 1986
    settings.ibge_end_year = 2024
    with (
        patch("embrapa_commodities.ibge.pipeline.fetch_sidra_dataframe") as fetch,
        patch("embrapa_commodities.ibge.pipeline.storage.Client"),
        patch("embrapa_commodities.ibge.pipeline.bigquery.Client"),
        patch("embrapa_commodities.ibge.pipeline.ensure_dataset"),
        patch("embrapa_commodities.ibge.pipeline.latest_reference_year", return_value=None),
        patch("embrapa_commodities.ibge.pipeline.land_raw"),
        patch("embrapa_commodities.ibge.pipeline.read_raw") as read_raw,
        patch("embrapa_commodities.ibge.pipeline.load_dataframe"),
    ):
        fetch.return_value = sidra_df
        _patch_phase2_df(read_raw, sidra_df)
        ibge_pipeline.run(settings)

    assert fetch.call_args.kwargs["start_year"] == 1986


def test_run_from_raw_replays_all_archived_objects(
    settings: Settings, sidra_df: pd.DataFrame
) -> None:
    """--from-raw replays the whole delta trail (every archived object), appending each."""
    with (
        patch("embrapa_commodities.ibge.pipeline.fetch_sidra_dataframe") as fetch,
        patch("embrapa_commodities.ibge.pipeline.storage.Client"),
        patch("embrapa_commodities.ibge.pipeline.bigquery.Client"),
        patch("embrapa_commodities.ibge.pipeline.ensure_dataset"),
        patch(
            "embrapa_commodities.ibge.pipeline.list_raw",
            return_value=["products_3405_1986_2024", "products_3405_2023_2024"],
        ),
        patch("embrapa_commodities.ibge.pipeline.read_raw") as read_raw,
        patch("embrapa_commodities.ibge.pipeline.load_dataframe") as load,
    ):
        _patch_phase2_df(read_raw, sidra_df)
        ibge_pipeline.run(settings, from_raw=True)

    fetch.assert_not_called()
    assert read_raw.call_count == 2  # both archived objects replayed
    assert load.call_count == 2


def test_run_from_raw_orders_replay_by_fetched_at_not_basename(
    settings: Settings, sidra_df: pd.DataFrame
) -> None:
    """Replay must follow fetch recency (the stored fetched_at provenance), not
    lexical basename order: the newest extract is appended LAST so it wins
    Silver's ingestion_timestamp-desc dedup. Lexical order would let a stale
    overlapping archive resurrect old readings for the overlapping years."""
    fetched_at = {
        # Lexically FIRST, but the NEWEST extract (a recent --full re-pull).
        "products_3405_1986_2026": {"fetched_at": "2026-06-01T00:00:00Z"},
        # Lexically LAST, but an OLD ibge-batch backfill chunk.
        "products_3405_1991_1995": {"fetched_at": "2024-01-01T00:00:00Z"},
    }
    with (
        patch("embrapa_commodities.ibge.pipeline.storage.Client"),
        patch("embrapa_commodities.ibge.pipeline.bigquery.Client"),
        patch("embrapa_commodities.ibge.pipeline.ensure_dataset"),
        patch(
            "embrapa_commodities.ibge.pipeline.list_raw",
            return_value=sorted(fetched_at),  # list_raw returns lexical order
        ),
        patch(
            "embrapa_commodities.ibge.pipeline.raw_provenance",
            side_effect=lambda *_a, basename, **_kw: fetched_at[basename],
        ),
        patch("embrapa_commodities.ibge.pipeline.read_raw") as read_raw,
        patch("embrapa_commodities.ibge.pipeline.load_dataframe"),
    ):
        _patch_phase2_df(read_raw, sidra_df)
        ibge_pipeline.run(settings, from_raw=True)

    replayed = [call.kwargs["basename"] for call in read_raw.call_args_list]
    assert replayed == ["products_3405_1991_1995", "products_3405_1986_2026"]


def test_order_by_fetched_at_puts_unstamped_objects_first(settings: Settings) -> None:
    """Objects without fetched_at (pre-provenance archives) sort first, so any
    stamped (newer-infrastructure) extract outranks them in Silver dedup."""
    provenance = {
        "a_stamped": {"fetched_at": "2026-01-01T00:00:00Z"},
        "b_unstamped": {},
    }
    with patch(
        "embrapa_commodities.ibge.pipeline.raw_provenance",
        side_effect=lambda *_a, basename, **_kw: provenance[basename],
    ):
        ordered = ibge_pipeline._order_by_fetched_at(
            ["a_stamped", "b_unstamped"],
            storage_client=MagicMock(),
            settings=settings,
            source="ibge",
            dataset=ibge_pipeline.RAW_DATASET,
        )
    assert ordered == ["b_unstamped", "a_stamped"]


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
