"""Smoke tests for the BCB inflation/currency two-phase pipelines (GCP + HTTP mocked).

Phase 1 fetches SGS and archives the verbatim window to raw; Phase 2 stamps
ingestion_timestamp and loads Bronze. The raw GCS round-trip is mocked (land_raw
captures the frame, read_raw returns it) — the real round-trip is covered in
test_core_raw.py.
"""

from __future__ import annotations

import re
from datetime import date
from unittest.mock import patch

import pytest
import responses

from embrapa_commodities.bcb import currency as bcb_currency
from embrapa_commodities.bcb import inflation as bcb_inflation
from embrapa_commodities.config import Settings


@pytest.fixture
def settings(settings_factory) -> Settings:
    # _env_file=None (via settings_factory) keeps the start/end year and series
    # from being overridden by the developer's repo-root .env (hermetic window).
    return settings_factory(
        gcp_project_id="test-project",
        gcs_bucket="test-bucket",
        bcb_start_year=2020,
        bcb_end_year=2020,
        bcb_inflation_series="433:IPCA",
        bcb_currency_series="3694:USD",
    )


class _RawRoundTrip:
    """land_raw captures the verbatim frame; read_raw replays it (Phase 1→2)."""

    def __init__(self) -> None:
        self.df = None

    def land(self, df, **_kwargs) -> str:
        self.df = df
        return "gs://test/raw"

    def read(self, *_args, **_kwargs):
        return self.df.copy()


@responses.activate
def test_inflation_full_run_archives_raw_then_loads(settings: Settings) -> None:
    """full=True re-fetches the window → land_raw (Phase 1) → load Bronze (Phase 2)."""
    responses.add(
        responses.GET,
        re.compile(r"https://api\.bcb\.gov\.br/dados/serie/bcdata\.sgs\.433/dados.*"),
        json=[{"data": "01/01/2020", "valor": "0.21"}],
        status=200,
    )
    rt = _RawRoundTrip()
    with (
        patch("embrapa_commodities.gcp.clients.bigquery.Client") as bq,
        patch("embrapa_commodities.gcp.clients.storage.Client") as gcs,
        patch("embrapa_commodities.bcb.series.ensure_dataset"),
        patch("embrapa_commodities.bcb.series.land_raw", side_effect=rt.land) as land,
        patch("embrapa_commodities.bcb.series.read_raw", side_effect=rt.read),
        patch("embrapa_commodities.bcb.series.load_dataframe") as load,
    ):
        destination = bcb_inflation.run(settings, full=True)

    assert destination.endswith(settings.bq_bronze_bcb_inflation_table)
    land.assert_called_once()
    load.assert_called_once()
    # Raw is verbatim (no ingestion_timestamp); Bronze adds it in Phase 2.
    assert "ingestion_timestamp" not in land.call_args.args[0].columns
    loaded_df = load.call_args.args[1]
    assert set(loaded_df.columns) >= {
        "series_code",
        "series_name",
        "reference_date_str",
        "value_str",
        "ingestion_timestamp",
    }
    bq.assert_called()
    gcs.assert_called()


@responses.activate
def test_inflation_delta_short_circuits_when_no_new_data(settings: Settings) -> None:
    """0 rows in delta mode → no raw archive, no Bronze load."""
    responses.add(
        responses.GET,
        re.compile(r"https://api\.bcb\.gov\.br/dados/serie/bcdata\.sgs\.433/dados.*"),
        json=[],
        status=200,
    )
    with (
        patch("embrapa_commodities.gcp.clients.bigquery.Client"),
        patch("embrapa_commodities.gcp.clients.storage.Client"),
        patch("embrapa_commodities.bcb.series.latest_reference_date") as latest,
        patch("embrapa_commodities.bcb.series.ensure_dataset"),
        patch("embrapa_commodities.bcb.series.land_raw") as land,
        patch("embrapa_commodities.bcb.series.load_dataframe") as load,
    ):
        latest.return_value = date(2020, 12, 1)
        destination = bcb_inflation.run(settings, full=False)

    assert destination == ""
    land.assert_not_called()
    load.assert_not_called()


@responses.activate
def test_currency_full_run_archives_raw_then_loads(settings: Settings) -> None:
    responses.add(
        responses.GET,
        re.compile(r"https://api\.bcb\.gov\.br/dados/serie/bcdata\.sgs\.3694/dados.*"),
        json=[{"data": "01/01/2020", "valor": "5.20"}],
        status=200,
    )
    rt = _RawRoundTrip()
    with (
        patch("embrapa_commodities.gcp.clients.bigquery.Client"),
        patch("embrapa_commodities.gcp.clients.storage.Client"),
        patch("embrapa_commodities.bcb.series.ensure_dataset"),
        patch("embrapa_commodities.bcb.series.land_raw", side_effect=rt.land),
        patch("embrapa_commodities.bcb.series.read_raw", side_effect=rt.read),
        patch("embrapa_commodities.bcb.series.load_dataframe") as load,
    ):
        destination = bcb_currency.run(settings, full=True)

    assert destination.endswith(settings.bq_bronze_bcb_currency_table)
    load.assert_called_once()
    assert "currency" in load.call_args.args[1].columns


def test_inflation_empty_series_raises(settings: Settings) -> None:
    settings.bcb_inflation_series = "  "
    with (
        patch("embrapa_commodities.gcp.clients.bigquery.Client"),
        patch("embrapa_commodities.gcp.clients.storage.Client"),
        patch("embrapa_commodities.bcb.series.ensure_dataset"),
        pytest.raises(RuntimeError, match="empty"),
    ):
        bcb_inflation.run(settings, full=True)
