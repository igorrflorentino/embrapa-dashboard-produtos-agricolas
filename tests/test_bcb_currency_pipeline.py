"""Unit tests for the BCB currency Bronze pipeline.

Isolates the delta-branch logic: the 30-day overlap window, the month=1 rewind
edge case, and the `max(reference_date_str)` lookup against a mocked BigQuery.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from embrapa_commodities.bcb import currency as bcb_currency
from embrapa_commodities.config import Settings


@pytest.fixture
def settings() -> Settings:
    return Settings(
        gcp_project_id="test-project",
        gcs_bucket="test-bucket",
        bcb_start_year=1980,
        bcb_end_year=2026,
        bcb_currency_series="3694:USD,4393:EUR",
        _env_file=None,
    )  # type: ignore[call-arg]


# ─── _effective_start_year — month=1 boundary is the interesting case ────────
def test_effective_start_year_returns_configured_when_table_empty() -> None:
    bq = MagicMock()
    with patch(
        "embrapa_commodities.bcb.currency.latest_reference_date",
        return_value=None,
    ):
        result = bcb_currency._effective_start_year(bq, "proj.ds.tbl", "3694", 1980)

    assert result == 1980


def test_effective_start_year_stays_in_same_year_after_jan(settings: Settings) -> None:
    """A 30-day overlap from mid-year stays within the same calendar year."""
    bq = MagicMock()
    with patch(
        "embrapa_commodities.bcb.currency.latest_reference_date",
        return_value=date(2025, 6, 15),
    ):
        # month != 1, so delta_start = 2025 (no rewind across years).
        result = bcb_currency._effective_start_year(bq, "proj.ds.tbl", "3694", 1980)

    assert result == 2025


def test_effective_start_year_rewinds_to_previous_year_when_january(
    settings: Settings,
) -> None:
    """When last load is in January, rewinding 30 days crosses into December
    of the previous year — so we must fetch from year - 1."""
    bq = MagicMock()
    with patch(
        "embrapa_commodities.bcb.currency.latest_reference_date",
        return_value=date(2025, 1, 15),
    ):
        result = bcb_currency._effective_start_year(bq, "proj.ds.tbl", "3694", 1980)

    # month == 1 → rewind to 2024 so the previous-December tail is re-fetched.
    assert result == 2024


def test_effective_start_year_never_goes_below_configured_floor() -> None:
    bq = MagicMock()
    with patch(
        "embrapa_commodities.bcb.currency.latest_reference_date",
        return_value=date(1995, 1, 1),
    ):
        # configured 2010 > 1995-1, so the user floor wins.
        result = bcb_currency._effective_start_year(bq, "proj.ds.tbl", "3694", 2010)

    assert result == 2010


# ─── _extract: full=True short-circuits BQ lookup ────────────────────────────
def test_extract_full_mode_skips_latest_lookup(settings: Settings) -> None:
    bq = MagicMock()
    fake_series_df = pd.DataFrame({"data": ["01/01/2020"], "valor": ["5.20"]})
    with (
        patch("embrapa_commodities.bcb.currency.latest_reference_date") as latest,
        patch(
            "embrapa_commodities.bcb.currency.fetch_series", return_value=fake_series_df
        ) as fetch,
    ):
        df = bcb_currency._extract(settings, bq, "proj.ds.tbl", full=True)

    latest.assert_not_called()
    assert not df.empty
    # Each configured currency series uses configured start year.
    for call in fetch.call_args_list:
        assert call.args[1] == settings.bcb_start_year


def test_extract_delta_mode_picks_per_series_start(settings: Settings) -> None:
    """The 30-day overlap is applied independently per currency code."""
    bq = MagicMock()
    fake_series_df = pd.DataFrame({"data": ["01/01/2020"], "valor": ["5.20"]})
    with (
        patch(
            "embrapa_commodities.bcb.currency.latest_reference_date",
            side_effect=[date(2025, 6, 15), date(2025, 1, 5)],
        ),
        patch(
            "embrapa_commodities.bcb.currency.fetch_series", return_value=fake_series_df
        ) as fetch,
    ):
        bcb_currency._extract(settings, bq, "proj.ds.tbl", full=False)

    starts = {call.args[0]: call.args[1] for call in fetch.call_args_list}
    # 3694: June → no year rewind = 2025.  4393: January → rewinds to 2024.
    assert starts == {"3694": 2025, "4393": 2024}


def test_extract_delta_empty_returns_empty_df(settings: Settings) -> None:
    bq = MagicMock()
    with (
        patch(
            "embrapa_commodities.bcb.currency.latest_reference_date",
            return_value=date(2026, 1, 1),
        ),
        patch("embrapa_commodities.bcb.currency.fetch_series", return_value=pd.DataFrame()),
    ):
        df = bcb_currency._extract(settings, bq, "proj.ds.tbl", full=False)

    assert df.empty


def test_extract_full_empty_raises(settings: Settings) -> None:
    bq = MagicMock()
    with (
        patch("embrapa_commodities.bcb.currency.latest_reference_date"),
        patch("embrapa_commodities.bcb.currency.fetch_series", return_value=pd.DataFrame()),
        pytest.raises(RuntimeError, match="no currency data"),
    ):
        bcb_currency._extract(settings, bq, "proj.ds.tbl", full=True)


def test_extract_empty_series_config_raises(settings: Settings) -> None:
    settings.bcb_currency_series = "  "
    bq = MagicMock()
    with pytest.raises(RuntimeError, match="empty"):
        bcb_currency._extract(settings, bq, "proj.ds.tbl", full=True)


def test_extract_returns_currency_column_set(settings: Settings) -> None:
    """Output Bronze columns: series_code/currency/date/value/ts.

    Note: inflation uses series_name; currency uses currency. The Silver model
    relies on this column existing.
    """
    bq = MagicMock()
    fake_series_df = pd.DataFrame({"data": ["01/01/2020"], "valor": ["5.20"]})
    with (
        patch(
            "embrapa_commodities.bcb.currency.latest_reference_date",
            return_value=date(2025, 6, 1),
        ),
        patch("embrapa_commodities.bcb.currency.fetch_series", return_value=fake_series_df),
    ):
        df = bcb_currency._extract(settings, bq, "proj.ds.tbl", full=False)

    assert set(df.columns) == {
        "series_code",
        "currency",
        "reference_date_str",
        "value_str",
        "ingestion_timestamp",
    }
    assert set(df["currency"]) == {"USD", "EUR"}


# ─── run() — delta short-circuit + full happy path ───────────────────────────
def test_run_delta_short_circuits_with_no_new_data(settings: Settings) -> None:
    with (
        patch("embrapa_commodities.bcb.currency.bigquery.Client"),
        patch("embrapa_commodities.bcb.currency.latest_reference_date") as latest,
        patch("embrapa_commodities.bcb.currency.fetch_series", return_value=pd.DataFrame()),
        patch("embrapa_commodities.bcb.currency.storage.Client") as gcs_cls,
        patch("embrapa_commodities.bcb.currency.ensure_bucket") as ensure_bucket,
        patch("embrapa_commodities.bcb.currency.upload_dataframe_as_parquet") as upload,
        patch("embrapa_commodities.bcb.currency.load_dataframe") as load,
        patch("embrapa_commodities.bcb.currency.ensure_dataset"),
    ):
        latest.return_value = date(2026, 6, 1)
        destination = bcb_currency.run(settings, full=False)

    assert destination == ""
    gcs_cls.assert_not_called()
    ensure_bucket.assert_not_called()
    upload.assert_not_called()
    load.assert_not_called()


def test_run_full_passes_partition_and_cluster_keys(settings: Settings) -> None:
    fake_series_df = pd.DataFrame({"data": ["01/01/2020"], "valor": ["5.20"]})
    with (
        patch("embrapa_commodities.bcb.currency.bigquery.Client"),
        patch("embrapa_commodities.bcb.currency.storage.Client"),
        patch("embrapa_commodities.bcb.currency.ensure_bucket"),
        patch("embrapa_commodities.bcb.currency.ensure_dataset"),
        patch("embrapa_commodities.bcb.currency.upload_dataframe_as_parquet"),
        patch("embrapa_commodities.bcb.currency.load_dataframe") as load,
        patch("embrapa_commodities.bcb.currency.fetch_series", return_value=fake_series_df),
    ):
        bcb_currency.run(settings, full=True)

    load_kwargs = load.call_args.kwargs
    assert load_kwargs["time_partitioning_field"] == "ingestion_timestamp"
    assert load_kwargs["clustering_fields"] == ["series_code", "reference_date_str"]


def test_run_object_name_includes_currency_year_window(settings: Settings) -> None:
    fake_series_df = pd.DataFrame({"data": ["01/01/2020"], "valor": ["5.20"]})
    with (
        patch("embrapa_commodities.bcb.currency.bigquery.Client"),
        patch("embrapa_commodities.bcb.currency.storage.Client"),
        patch("embrapa_commodities.bcb.currency.ensure_bucket"),
        patch("embrapa_commodities.bcb.currency.ensure_dataset"),
        patch("embrapa_commodities.bcb.currency.upload_dataframe_as_parquet") as upload,
        patch("embrapa_commodities.bcb.currency.load_dataframe"),
        patch("embrapa_commodities.bcb.currency.fetch_series", return_value=fake_series_df),
    ):
        bcb_currency.run(settings, full=True)

    object_name = upload.call_args.args[2]
    assert object_name.startswith("landing/bcb/currency_series_raw/run=")
    assert "currency_1980_2026.parquet" in object_name
