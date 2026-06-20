"""Tests for the IBGE PPM Bronze pipeline (SIDRA + GCS + BQ all mocked).

PPM diverges from PEVS/PAM in being MULTI-TABLE: one ``run()`` ingests BOTH SIDRA
tables (3939 herd headcount + 74 animal production) into two Bronze tables, each in
its own raw-zone segment (``ppm_herd`` / ``ppm_animal``). These tests pin that
two-spec behaviour: the right table/classification/variables per spec, the per-table
raw isolation + basename, the per-table delta, and the --from-raw replay.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from embrapa_commodities.config import Settings
from embrapa_commodities.ibge import ppm_pipeline

P = "embrapa_commodities.ibge.ppm_pipeline"


@pytest.fixture
def settings() -> Settings:
    return Settings(
        gcp_project_id="test-project",
        gcs_bucket="test-bucket",
        ppm_start_year=2020,
        ppm_end_year=2020,
        ppm_herd_product_codes="2670",
        ppm_animal_product_codes="2682",
        _env_file=None,
    )  # type: ignore[call-arg]


@pytest.fixture
def sidra_df() -> pd.DataFrame:
    """Municipal SIDRA-shaped frame (generic — used for both PPM tables)."""
    return pd.DataFrame(
        {
            "municipio_codigo": ["1100015", "1100023"],
            "municipio": ["Alta Floresta D'Oeste", "Ariquemes"],
            "ano": ["2020", "2020"],
            "variavel_codigo": ["105", "105"],
            "unidade_de_medida": ["Cabeças", "Cabeças"],
            "valor": ["100", "200"],
        }
    )


# ─── run() ingests BOTH tables ───────────────────────────────────────────────
def test_run_loads_both_ppm_tables(settings: Settings, sidra_df: pd.DataFrame) -> None:
    """One run() fetches herd (3939/c79/v105) AND animal (74/c80/v106,215), loading
    both Bronze tables; the returned destination names both."""
    with (
        patch(f"{P}.fetch_sidra_dataframe") as fetch,
        patch(f"{P}.storage.Client"),
        patch(f"{P}.bigquery.Client"),
        patch(f"{P}.ensure_dataset"),
        patch(f"{P}.latest_reference_year", return_value=None),  # cold → full window
        patch(f"{P}.land_raw") as land_raw,
        patch(f"{P}.read_raw") as read_raw,
        patch(f"{P}.load_dataframe") as load,
    ):
        fetch.return_value = sidra_df
        read_raw.return_value = sidra_df.astype(str)
        destination = ppm_pipeline.run(settings)

    ds = f"{settings.gcp_project_id}.{settings.bq_bronze_ppm_dataset}"
    herd_dest = f"{ds}.{settings.bq_bronze_ppm_herd_table}"
    animal_dest = f"{ds}.{settings.bq_bronze_ppm_animal_table}"
    assert destination == f"{herd_dest}; {animal_dest}"

    assert fetch.call_count == 2
    herd_kwargs, animal_kwargs = (c.kwargs for c in fetch.call_args_list)
    assert herd_kwargs["table_id"] == "3939"
    assert herd_kwargs["classification"] == "79"
    assert herd_kwargs["products"] == ["2670"]
    assert herd_kwargs["variables"] == "105"
    assert herd_kwargs["geo_level"] == "n6"
    assert animal_kwargs["table_id"] == "74"
    assert animal_kwargs["classification"] == "80"
    assert animal_kwargs["products"] == ["2682"]
    assert animal_kwargs["variables"] == "106,215"  # quantity + value

    assert load.call_count == 2
    assert load.call_args.kwargs["clustering_fields"] == [
        "municipio_codigo",
        "ano",
        "variavel_codigo",
    ]
    assert land_raw.call_count == 2


def test_run_raw_segments_isolate_herd_from_animal(
    settings: Settings, sidra_df: pd.DataFrame
) -> None:
    """Herd archives under raw/ibge/ppm_herd/, animal under raw/ibge/ppm_animal/ —
    so a --from-raw replay of one never crosses into the other (or into PEVS/PAM)."""
    with (
        patch(f"{P}.fetch_sidra_dataframe", return_value=sidra_df),
        patch(f"{P}.storage.Client"),
        patch(f"{P}.bigquery.Client"),
        patch(f"{P}.ensure_dataset"),
        patch(f"{P}.latest_reference_year", return_value=None),
        patch(f"{P}.land_raw") as land_raw,
        patch(f"{P}.read_raw") as read_raw,
        patch(f"{P}.load_dataframe"),
    ):
        read_raw.return_value = sidra_df.astype(str)
        ppm_pipeline.run(settings)

    by_dataset = {c.kwargs["dataset"]: c.kwargs for c in land_raw.call_args_list}
    assert set(by_dataset) == {"ppm_herd", "ppm_animal"}
    assert by_dataset["ppm_herd"]["source"] == "ibge"
    assert by_dataset["ppm_herd"]["basename"] == "herd_products_2670_2020_2020"
    assert by_dataset["ppm_animal"]["basename"] == "animal_products_2682_2020_2020"


# ─── empty fetch / guards ────────────────────────────────────────────────────
def test_run_returns_empty_when_both_tables_have_no_rows(settings: Settings) -> None:
    with (
        patch(f"{P}.fetch_sidra_dataframe", return_value=pd.DataFrame()),
        patch(f"{P}.storage.Client"),
        patch(f"{P}.bigquery.Client"),
        patch(f"{P}.ensure_dataset"),
        patch(f"{P}.latest_reference_year", return_value=None),
        patch(f"{P}.land_raw") as land_raw,
        patch(f"{P}.load_dataframe") as load,
    ):
        destination = ppm_pipeline.run(settings)

    assert destination == ""
    land_raw.assert_not_called()
    load.assert_not_called()


def test_run_raises_when_start_year_is_none(settings: Settings) -> None:
    settings.ppm_start_year = None
    with (
        patch(f"{P}.storage.Client"),
        patch(f"{P}.bigquery.Client"),
        patch(f"{P}.ensure_dataset"),
        patch(f"{P}.latest_reference_year", return_value=None),
        pytest.raises(RuntimeError, match="PPM_START_YEAR is empty"),
    ):
        ppm_pipeline.run(settings)


# ─── delta-by-default (per table, on ppm_end_year) ───────────────────────────
def test_run_delta_rewinds_start_to_recent_years(
    settings: Settings, sidra_df: pd.DataFrame
) -> None:
    settings.ppm_start_year = 2010
    settings.ppm_end_year = 2024
    with (
        patch(f"{P}.fetch_sidra_dataframe") as fetch,
        patch(f"{P}.storage.Client"),
        patch(f"{P}.bigquery.Client"),
        patch(f"{P}.ensure_dataset"),
        patch(f"{P}.latest_reference_year", return_value=2023),
        patch(f"{P}.land_raw"),
        patch(f"{P}.read_raw") as read_raw,
        patch(f"{P}.load_dataframe"),
    ):
        fetch.return_value = sidra_df
        read_raw.return_value = sidra_df.astype(str)
        ppm_pipeline.run(settings)

    # overlap default = 1 → start = 2023 − 1 = 2022 for BOTH tables, not 2010.
    for call in fetch.call_args_list:
        assert call.kwargs["start_year"] == 2022
        assert call.kwargs["end_year"] == 2024


def test_run_full_bypasses_delta(settings: Settings, sidra_df: pd.DataFrame) -> None:
    settings.ppm_start_year = 2010
    settings.ppm_end_year = 2024
    with (
        patch(f"{P}.fetch_sidra_dataframe") as fetch,
        patch(f"{P}.storage.Client"),
        patch(f"{P}.bigquery.Client"),
        patch(f"{P}.ensure_dataset"),
        patch(f"{P}.latest_reference_year") as latest,
        patch(f"{P}.land_raw"),
        patch(f"{P}.read_raw") as read_raw,
        patch(f"{P}.load_dataframe"),
    ):
        fetch.return_value = sidra_df
        read_raw.return_value = sidra_df.astype(str)
        ppm_pipeline.run(settings, full=True)

    latest.assert_not_called()
    assert all(c.kwargs["start_year"] == 2010 for c in fetch.call_args_list)


def test_run_delta_noop_when_both_tables_at_end_year(settings: Settings) -> None:
    settings.ppm_start_year = 2010
    settings.ppm_end_year = 2024
    with (
        patch(f"{P}.fetch_sidra_dataframe") as fetch,
        patch(f"{P}.storage.Client"),
        patch(f"{P}.bigquery.Client"),
        patch(f"{P}.ensure_dataset"),
        patch(f"{P}.latest_reference_year", return_value=2024),
        patch(f"{P}.land_raw") as land_raw,
        patch(f"{P}.load_dataframe") as load,
    ):
        destination = ppm_pipeline.run(settings)

    assert destination == ""
    fetch.assert_not_called()
    land_raw.assert_not_called()
    load.assert_not_called()


def test_delta_start_year_returns_clamped_int(settings: Settings) -> None:
    settings.ppm_start_year = 2010
    settings.ppm_end_year = 2024
    settings.ppm_delta_overlap_years = 0
    spec = ppm_pipeline._specs(settings)[0]
    with patch(f"{P}.latest_reference_year", return_value=2023):
        start = ppm_pipeline._delta_start_year(settings, spec, MagicMock())
    assert start == 2023
    assert start <= settings.ppm_end_year


# ─── --from-raw replay (per spec) ────────────────────────────────────────────
def test_run_from_raw_replays_each_table(settings: Settings, sidra_df: pd.DataFrame) -> None:
    with (
        patch(f"{P}.fetch_sidra_dataframe") as fetch,
        patch(f"{P}.storage.Client"),
        patch(f"{P}.bigquery.Client"),
        patch(f"{P}.ensure_dataset"),
        patch(f"{P}.list_raw", return_value=["herd_products_2670_2020_2020"]),
        patch(f"{P}.read_raw") as read_raw,
        patch(f"{P}.load_dataframe") as load,
    ):
        read_raw.return_value = sidra_df.astype(str)
        ppm_pipeline.run(settings, from_raw=True)

    fetch.assert_not_called()
    # list_raw is queried once per spec (herd + animal) → both replay their archive.
    assert read_raw.call_count == 2
    assert load.call_count == 2
