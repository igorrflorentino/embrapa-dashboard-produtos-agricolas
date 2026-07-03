"""Tests for the IBGE PAM Bronze pipeline (SIDRA + GCS + BQ all mocked).

PAM reuses PEVS's generic SIDRA client + Bronze schema but reads its OWN pam_*
settings and writes its OWN Bronze table / raw-zone segment. These tests pin
that isolation (RAW_DATASET='pam', bronze_pam target, pam_* window) so a future
edit can't accidentally point PAM at the PEVS objects.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from embrapa_dashboard.config import Settings
from embrapa_dashboard.ibge import pam_pipeline


@pytest.fixture
def settings() -> Settings:
    return Settings(
        gcp_project_id="test-project",
        gcs_bucket="test-bucket",
        pam_start_year=2020,
        pam_end_year=2020,
        pam_product_codes="40124",
        _env_file=None,
    )  # type: ignore[call-arg]


@pytest.fixture
def sidra_df() -> pd.DataFrame:
    """PAM-shaped DataFrame mimicking `fetch_sidra_dataframe` output (table 5457)."""
    return pd.DataFrame(
        {
            "municipio_codigo": ["1100015", "1100023"],
            "municipio": ["Alta Floresta D'Oeste", "Ariquemes"],
            "ano": ["2020", "2020"],
            "variavel_codigo": ["214", "214"],
            "variavel": ["Quantidade produzida", "Quantidade produzida"],
            "produto_das_lavouras_codigo": ["40124", "40124"],
            "produto_das_lavouras": ["Soja (em grão)", "Soja (em grão)"],
            "unidade_de_medida": ["Toneladas", "Toneladas"],
            "valor": ["100", "200"],
        }
    )


def _patch_phase2_df(read_raw, sidra_df: pd.DataFrame) -> None:
    read_raw.return_value = sidra_df.astype(str)


# ─── run() — two-phase happy path, PAM target isolation ──────────────────────
def test_run_loads_to_pam_bronze_with_pam_query(settings: Settings, sidra_df: pd.DataFrame) -> None:
    """SIDRA fetch (table 5457 / c782) → land_raw → read_raw → BQ load to bronze_pam."""
    with (
        patch("embrapa_dashboard.ibge.pam_pipeline.fetch_sidra_dataframe") as fetch,
        patch("embrapa_dashboard.ibge.pam_pipeline.storage.Client"),
        patch("embrapa_dashboard.ibge.pam_pipeline.bigquery.Client"),
        patch("embrapa_dashboard.ibge.pam_pipeline.ensure_dataset"),
        patch("embrapa_dashboard.ibge.pam_pipeline.land_raw") as land_raw,
        patch("embrapa_dashboard.ibge.pam_pipeline.read_raw") as read_raw,
        patch("embrapa_dashboard.ibge.pam_pipeline.load_dataframe") as load,
    ):
        fetch.return_value = sidra_df
        _patch_phase2_df(read_raw, sidra_df)
        destination = pam_pipeline.run(settings)

    expected_destination = (
        f"{settings.gcp_project_id}.{settings.bq_bronze_pam_dataset}.{settings.bq_bronze_pam_table}"
    )
    assert destination == expected_destination

    fetch_kwargs = fetch.call_args.kwargs
    assert fetch_kwargs["table_id"] == "5457"
    assert fetch_kwargs["classification"] == "782"
    assert fetch_kwargs["products"] == ["40124"]
    assert fetch_kwargs["geo_level"] == "n6"

    load_kwargs = load.call_args.kwargs
    assert load_kwargs["time_partitioning_field"] == "ingestion_timestamp"
    assert load_kwargs["clustering_fields"] == ["municipio_codigo", "ano", "variavel_codigo"]
    land_raw.assert_called_once()


def test_run_raw_basename_and_dataset_isolate_from_pevs(
    settings: Settings, sidra_df: pd.DataFrame
) -> None:
    """Phase 1 archives under raw/ibge/pam/ (NOT pevs) so --from-raw never crosses sources."""
    settings.pam_product_codes = "40124,40122"
    with (
        patch("embrapa_dashboard.ibge.pam_pipeline.fetch_sidra_dataframe", return_value=sidra_df),
        patch("embrapa_dashboard.ibge.pam_pipeline.storage.Client"),
        patch("embrapa_dashboard.ibge.pam_pipeline.bigquery.Client"),
        patch("embrapa_dashboard.ibge.pam_pipeline.ensure_dataset"),
        patch("embrapa_dashboard.ibge.pam_pipeline.land_raw") as land_raw,
        patch("embrapa_dashboard.ibge.pam_pipeline.read_raw") as read_raw,
        patch("embrapa_dashboard.ibge.pam_pipeline.load_dataframe"),
    ):
        _patch_phase2_df(read_raw, sidra_df)
        pam_pipeline.run(settings)

    kwargs = land_raw.call_args.kwargs
    assert kwargs["source"] == "ibge"
    assert kwargs["dataset"] == "pam"
    assert pam_pipeline.RAW_DATASET == "pam"
    assert kwargs["basename"] == "products_40124_40122_2020_2020"


# ─── empty fetch short-circuit ───────────────────────────────────────────────
def test_run_returns_empty_string_when_sidra_returns_no_rows(settings: Settings) -> None:
    with (
        patch(
            "embrapa_dashboard.ibge.pam_pipeline.fetch_sidra_dataframe",
            return_value=pd.DataFrame(),
        ),
        patch("embrapa_dashboard.ibge.pam_pipeline.storage.Client"),
        patch("embrapa_dashboard.ibge.pam_pipeline.bigquery.Client"),
        patch("embrapa_dashboard.ibge.pam_pipeline.ensure_dataset"),
        patch("embrapa_dashboard.ibge.pam_pipeline.land_raw") as land_raw,
        patch("embrapa_dashboard.ibge.pam_pipeline.load_dataframe") as load,
    ):
        destination = pam_pipeline.run(settings)

    assert destination == ""
    land_raw.assert_not_called()
    load.assert_not_called()


def test_run_raises_when_start_year_is_none(settings: Settings) -> None:
    settings.pam_start_year = None
    with (
        patch("embrapa_dashboard.ibge.pam_pipeline.storage.Client"),
        patch("embrapa_dashboard.ibge.pam_pipeline.bigquery.Client"),
        patch("embrapa_dashboard.ibge.pam_pipeline.ensure_dataset"),
        pytest.raises(RuntimeError, match="PAM_START_YEAR is empty"),
    ):
        pam_pipeline.run(settings)


# ─── delta-by-default (on pam_end_year) ──────────────────────────────────────
def test_run_delta_rewinds_start_to_recent_years(
    settings: Settings, sidra_df: pd.DataFrame
) -> None:
    settings.pam_start_year = 2010
    settings.pam_end_year = 2024
    with (
        patch("embrapa_dashboard.ibge.pam_pipeline.fetch_sidra_dataframe") as fetch,
        patch("embrapa_dashboard.ibge.pam_pipeline.storage.Client"),
        patch("embrapa_dashboard.ibge.pam_pipeline.bigquery.Client"),
        patch("embrapa_dashboard.ibge.pam_pipeline.ensure_dataset"),
        patch("embrapa_dashboard.ibge.pam_pipeline.latest_reference_year", return_value=2023),
        patch("embrapa_dashboard.ibge.pam_pipeline.land_raw"),
        patch("embrapa_dashboard.ibge.pam_pipeline.read_raw") as read_raw,
        patch("embrapa_dashboard.ibge.pam_pipeline.load_dataframe"),
    ):
        fetch.return_value = sidra_df
        _patch_phase2_df(read_raw, sidra_df)
        pam_pipeline.run(settings)

    # overlap default = 1 → start = 2023 − 1 = 2022, NOT the configured 2010.
    assert fetch.call_args.kwargs["start_year"] == 2022
    assert fetch.call_args.kwargs["end_year"] == 2024


def test_run_full_bypasses_delta(settings: Settings, sidra_df: pd.DataFrame) -> None:
    settings.pam_start_year = 2010
    settings.pam_end_year = 2024
    with (
        patch("embrapa_dashboard.ibge.pam_pipeline.fetch_sidra_dataframe") as fetch,
        patch("embrapa_dashboard.ibge.pam_pipeline.storage.Client"),
        patch("embrapa_dashboard.ibge.pam_pipeline.bigquery.Client"),
        patch("embrapa_dashboard.ibge.pam_pipeline.ensure_dataset"),
        patch("embrapa_dashboard.ibge.pam_pipeline.latest_reference_year") as latest,
        patch("embrapa_dashboard.ibge.pam_pipeline.land_raw"),
        patch("embrapa_dashboard.ibge.pam_pipeline.read_raw") as read_raw,
        patch("embrapa_dashboard.ibge.pam_pipeline.load_dataframe"),
    ):
        fetch.return_value = sidra_df
        _patch_phase2_df(read_raw, sidra_df)
        pam_pipeline.run(settings, full=True)

    latest.assert_not_called()
    assert fetch.call_args.kwargs["start_year"] == 2010


def test_run_delta_noop_when_bronze_already_at_end_year(settings: Settings) -> None:
    settings.pam_start_year = 2010
    settings.pam_end_year = 2024
    with (
        patch("embrapa_dashboard.ibge.pam_pipeline.fetch_sidra_dataframe") as fetch,
        patch("embrapa_dashboard.ibge.pam_pipeline.storage.Client"),
        patch("embrapa_dashboard.ibge.pam_pipeline.bigquery.Client"),
        patch("embrapa_dashboard.ibge.pam_pipeline.ensure_dataset"),
        patch("embrapa_dashboard.ibge.pam_pipeline.latest_reference_year", return_value=2024),
        patch("embrapa_dashboard.ibge.pam_pipeline.land_raw") as land_raw,
        patch("embrapa_dashboard.ibge.pam_pipeline.load_dataframe") as load,
    ):
        destination = pam_pipeline.run(settings)

    assert destination == ""
    fetch.assert_not_called()
    land_raw.assert_not_called()
    load.assert_not_called()


def test_delta_start_year_clamps_effective_start_to_end_year(settings: Settings) -> None:
    settings.pam_start_year = 2010
    settings.pam_end_year = 2024
    settings.pam_delta_overlap_years = 0
    with patch("embrapa_dashboard.ibge.pam_pipeline.latest_reference_year", return_value=2023):
        rewound = pam_pipeline._delta_start_year(settings, MagicMock())
    assert rewound is not None
    assert rewound.pam_start_year == 2023
    assert rewound.pam_start_year <= rewound.pam_end_year


def test_run_from_raw_replays_archived_objects(settings: Settings, sidra_df: pd.DataFrame) -> None:
    with (
        patch("embrapa_dashboard.ibge.pam_pipeline.fetch_sidra_dataframe") as fetch,
        patch("embrapa_dashboard.ibge.pam_pipeline.storage.Client"),
        patch("embrapa_dashboard.ibge.pam_pipeline.bigquery.Client"),
        patch("embrapa_dashboard.ibge.pam_pipeline.ensure_dataset"),
        patch(
            "embrapa_dashboard.ibge.pam_pipeline.list_raw",
            return_value=["products_40124_2010_2024", "products_40124_2023_2024"],
        ),
        patch("embrapa_dashboard.ibge.pam_pipeline.read_raw") as read_raw,
        patch("embrapa_dashboard.ibge.pam_pipeline.load_dataframe") as load,
    ):
        _patch_phase2_df(read_raw, sidra_df)
        pam_pipeline.run(settings, from_raw=True)

    fetch.assert_not_called()
    assert read_raw.call_count == 2
    assert load.call_count == 2


def test_run_from_raw_orders_replay_by_fetched_at_not_basename(
    settings: Settings, sidra_df: pd.DataFrame
) -> None:
    """Like PEVS, PAM --from-raw must replay oldest-fetch-first (stored fetched_at
    provenance), not in lexical basename order, so the newest extract wins
    Silver's ingestion_timestamp-desc dedup."""
    fetched_at = {
        # Lexically FIRST, but the NEWEST extract.
        "products_40124_2010_2026": {"fetched_at": "2026-06-01T00:00:00Z"},
        # Lexically LAST, but an OLD backfill chunk.
        "products_40124_2023_2024": {"fetched_at": "2024-01-01T00:00:00Z"},
    }
    with (
        patch("embrapa_dashboard.ibge.pam_pipeline.storage.Client"),
        patch("embrapa_dashboard.ibge.pam_pipeline.bigquery.Client"),
        patch("embrapa_dashboard.ibge.pam_pipeline.ensure_dataset"),
        patch(
            "embrapa_dashboard.ibge.pam_pipeline.list_raw",
            return_value=sorted(fetched_at),  # list_raw returns lexical order
        ),
        # _order_by_fetched_at lives in (and reads provenance via) ibge.pipeline.
        patch(
            "embrapa_dashboard.ibge.pipeline.raw_provenance",
            side_effect=lambda *_a, basename, **_kw: fetched_at[basename],
        ),
        patch("embrapa_dashboard.ibge.pam_pipeline.read_raw") as read_raw,
        patch("embrapa_dashboard.ibge.pam_pipeline.load_dataframe"),
    ):
        _patch_phase2_df(read_raw, sidra_df)
        pam_pipeline.run(settings, from_raw=True)

    replayed = [call.kwargs["basename"] for call in read_raw.call_args_list]
    assert replayed == ["products_40124_2023_2024", "products_40124_2010_2026"]
