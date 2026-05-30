"""Smoke tests for the BCB inflation/currency Bronze pipelines (GCP + HTTP mocked)."""

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
def settings() -> Settings:
    return Settings(
        gcp_project_id="test-project",
        gcs_bucket="test-bucket",
        bcb_start_year=2020,
        bcb_end_year=2020,
        bcb_inflation_series="433:IPCA",
        bcb_currency_series="3694:USD",
    )  # type: ignore[call-arg]


@responses.activate
def test_inflation_full_run_uploads_and_loads(settings: Settings) -> None:
    """`full=True` skips the latest_reference_date lookup and re-fetches the window."""
    responses.add(
        responses.GET,
        re.compile(r"https://api\.bcb\.gov\.br/dados/serie/bcdata\.sgs\.433/dados.*"),
        json=[{"data": "01/01/2020", "valor": "0.21"}],
        status=200,
    )

    with (
        patch("embrapa_commodities.bcb.series.bigquery.Client") as bq,
        patch("embrapa_commodities.bcb.series.storage.Client") as gcs,
        patch("embrapa_commodities.core.bronze.ensure_bucket"),
        patch("embrapa_commodities.core.bronze.upload_dataframe_as_parquet") as upload,
        patch("embrapa_commodities.core.bronze.load_dataframe") as load,
        patch("embrapa_commodities.bcb.series.ensure_dataset"),
    ):
        destination = bcb_inflation.run(settings, full=True)

    assert destination.endswith(settings.bq_bronze_bcb_inflation_table)
    upload.assert_called_once()
    load.assert_called_once()
    # The DataFrame passed to load must have the bronze columns we expect.
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
    """If BCB returns 0 rows in delta mode, the pipeline skips GCS/BQ entirely."""
    responses.add(
        responses.GET,
        re.compile(r"https://api\.bcb\.gov\.br/dados/serie/bcdata\.sgs\.433/dados.*"),
        json=[],
        status=200,
    )

    with (
        patch("embrapa_commodities.bcb.series.bigquery.Client"),
        patch("embrapa_commodities.bcb.series.latest_reference_date") as latest,
        patch("embrapa_commodities.bcb.series.storage.Client") as gcs,
        patch("embrapa_commodities.core.bronze.ensure_bucket") as ensure_bucket,
        patch("embrapa_commodities.core.bronze.upload_dataframe_as_parquet") as upload,
        patch("embrapa_commodities.core.bronze.load_dataframe") as load,
        patch("embrapa_commodities.bcb.series.ensure_dataset"),
    ):
        latest.return_value = date(2020, 12, 1)
        destination = bcb_inflation.run(settings, full=False)

    assert destination == ""
    gcs.assert_not_called()
    ensure_bucket.assert_not_called()
    upload.assert_not_called()
    load.assert_not_called()


@responses.activate
def test_currency_full_run_uploads_and_loads(settings: Settings) -> None:
    responses.add(
        responses.GET,
        re.compile(r"https://api\.bcb\.gov\.br/dados/serie/bcdata\.sgs\.3694/dados.*"),
        json=[{"data": "01/01/2020", "valor": "5.20"}],
        status=200,
    )

    with (
        patch("embrapa_commodities.bcb.series.bigquery.Client"),
        patch("embrapa_commodities.bcb.series.storage.Client"),
        patch("embrapa_commodities.core.bronze.ensure_bucket"),
        patch("embrapa_commodities.core.bronze.upload_dataframe_as_parquet") as upload,
        patch("embrapa_commodities.core.bronze.load_dataframe") as load,
        patch("embrapa_commodities.bcb.series.ensure_dataset"),
    ):
        destination = bcb_currency.run(settings, full=True)

    assert destination.endswith(settings.bq_bronze_bcb_currency_table)
    upload.assert_called_once()
    load.assert_called_once()
    loaded_df = load.call_args.args[1]
    assert "currency" in loaded_df.columns


def test_inflation_empty_series_raises(settings: Settings) -> None:
    settings.bcb_inflation_series = "  "

    with (
        patch("embrapa_commodities.bcb.series.bigquery.Client"),
        patch("embrapa_commodities.bcb.series.ensure_dataset"),
        pytest.raises(RuntimeError, match="empty"),
    ):
        bcb_inflation.run(settings, full=True)
