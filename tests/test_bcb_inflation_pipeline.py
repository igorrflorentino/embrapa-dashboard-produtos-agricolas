"""Unit tests for the BCB inflation Bronze pipeline.

The integration-flavoured smoke test lives in tests/test_bcb_pipeline.py.
This file isolates the delta-branch logic: `_effective_start_year`, the
12-month overlap, and the `max(reference_date_str)` lookup behaviour.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from embrapa_commodities.bcb import inflation as bcb_inflation
from embrapa_commodities.config import Settings


@pytest.fixture
def settings() -> Settings:
    return Settings(
        gcp_project_id="test-project",
        gcs_bucket="test-bucket",
        bcb_start_year=1980,
        bcb_end_year=2026,
        bcb_inflation_series="433:IPCA,189:IGPM",
        _env_file=None,
    )  # type: ignore[call-arg]


# ─── DELTA_OVERLAP_MONTHS constant — regression guard ────────────────────────
def test_delta_overlap_is_twelve_months() -> None:
    """CLAUDE.md documents a 12-month overlap to absorb BCB revisions. Don't drift."""
    assert bcb_inflation.DELTA_OVERLAP_MONTHS == 12


# ─── _effective_start_year ───────────────────────────────────────────────────
def test_effective_start_year_returns_configured_when_table_empty() -> None:
    """No prior data ⇒ no rewind: start exactly where the user configured."""
    bq = MagicMock()
    with patch(
        "embrapa_commodities.bcb.inflation.latest_reference_date",
        return_value=None,
    ) as latest:
        result = bcb_inflation._effective_start_year(bq, "proj.ds.tbl", "433", 1980)

    latest.assert_called_once_with(bq, "proj.ds.tbl", "433")
    assert result == 1980


def test_effective_start_year_rewinds_one_year_when_data_exists() -> None:
    """With a 12-month overlap, last_loaded.year - 1 must be the rewind anchor."""
    bq = MagicMock()
    with patch(
        "embrapa_commodities.bcb.inflation.latest_reference_date",
        return_value=date(2025, 6, 1),
    ):
        result = bcb_inflation._effective_start_year(bq, "proj.ds.tbl", "433", 1980)

    # 12-month overlap: rewind = 2025 - (12 // 12) = 2024.
    # max(1980, 2024) = 2024.
    assert result == 2024


def test_effective_start_year_never_goes_below_configured_start() -> None:
    """If the user set BCB_START_YEAR after the last load, configured wins."""
    bq = MagicMock()
    with patch(
        "embrapa_commodities.bcb.inflation.latest_reference_date",
        return_value=date(1995, 6, 1),
    ):
        # configured 2010 > 1995-1 rewind, so we honour the user's floor.
        result = bcb_inflation._effective_start_year(bq, "proj.ds.tbl", "433", 2010)

    assert result == 2010


def test_effective_start_year_passes_series_code_through() -> None:
    """latest_reference_date must be queried for the specific series, not all of them."""
    bq = MagicMock()
    with patch(
        "embrapa_commodities.bcb.inflation.latest_reference_date",
        return_value=date(2025, 1, 1),
    ) as latest:
        bcb_inflation._effective_start_year(bq, "proj.ds.tbl", "189", 1980)

    assert latest.call_args.args == (bq, "proj.ds.tbl", "189")


# ─── _extract: full=True short-circuits the BQ lookup ────────────────────────
def test_extract_full_mode_does_not_query_bigquery(settings: Settings) -> None:
    """`--full` must not call latest_reference_date — that's the whole point of the flag."""
    bq = MagicMock()
    fake_series_df = pd.DataFrame({"data": ["01/01/2020"], "valor": ["0.21"]})
    with (
        patch("embrapa_commodities.bcb.inflation.latest_reference_date") as latest,
        patch(
            "embrapa_commodities.bcb.inflation.fetch_series", return_value=fake_series_df
        ) as fetch,
    ):
        df = bcb_inflation._extract(settings, bq, "proj.ds.tbl", full=True)

    latest.assert_not_called()
    assert not df.empty
    # Each configured series is fetched from configured start.
    series_codes_requested = [call.args[0] for call in fetch.call_args_list]
    assert set(series_codes_requested) == {"433", "189"}
    # Full mode always uses settings.bcb_start_year as the start year.
    for call in fetch.call_args_list:
        assert call.args[1] == settings.bcb_start_year


def test_extract_delta_mode_uses_effective_start_per_series(settings: Settings) -> None:
    """Delta mode: each series independently anchors on its own last load."""
    bq = MagicMock()
    fake_series_df = pd.DataFrame({"data": ["01/01/2020"], "valor": ["0.21"]})
    with (
        patch(
            "embrapa_commodities.bcb.inflation.latest_reference_date",
            side_effect=[date(2025, 6, 1), date(2023, 3, 1)],
        ) as latest,
        patch(
            "embrapa_commodities.bcb.inflation.fetch_series", return_value=fake_series_df
        ) as fetch,
    ):
        bcb_inflation._extract(settings, bq, "proj.ds.tbl", full=False)

    assert latest.call_count == 2
    # Each series got its own start year: 2025-1=2024 for 433; 2023-1=2022 for 189.
    starts = {call.args[0]: call.args[1] for call in fetch.call_args_list}
    assert starts == {"433": 2024, "189": 2022}


def test_extract_delta_empty_returns_empty_df_not_error(settings: Settings) -> None:
    """Delta mode with zero new rows is a no-op, not a failure."""
    bq = MagicMock()
    with (
        patch(
            "embrapa_commodities.bcb.inflation.latest_reference_date",
            return_value=date(2025, 12, 1),
        ),
        patch(
            "embrapa_commodities.bcb.inflation.fetch_series",
            return_value=pd.DataFrame(),
        ),
    ):
        df = bcb_inflation._extract(settings, bq, "proj.ds.tbl", full=False)

    assert df.empty


def test_extract_full_empty_raises(settings: Settings) -> None:
    """Full mode with zero rows is a real problem — fail loudly."""
    bq = MagicMock()
    with (
        patch("embrapa_commodities.bcb.inflation.latest_reference_date"),
        patch(
            "embrapa_commodities.bcb.inflation.fetch_series",
            return_value=pd.DataFrame(),
        ),
        pytest.raises(RuntimeError, match="no inflation data"),
    ):
        bcb_inflation._extract(settings, bq, "proj.ds.tbl", full=True)


def test_extract_empty_series_config_raises(settings: Settings) -> None:
    settings.bcb_inflation_series = "  "
    bq = MagicMock()
    with pytest.raises(RuntimeError, match="empty"):
        bcb_inflation._extract(settings, bq, "proj.ds.tbl", full=True)


def test_extract_returns_canonical_column_set(settings: Settings) -> None:
    """Output must conform to the Bronze schema (series_code/name/date/value/ts)."""
    bq = MagicMock()
    fake_series_df = pd.DataFrame({"data": ["01/01/2020"], "valor": ["0.21"]})
    with (
        patch(
            "embrapa_commodities.bcb.inflation.latest_reference_date",
            return_value=date(2025, 1, 1),
        ),
        patch("embrapa_commodities.bcb.inflation.fetch_series", return_value=fake_series_df),
    ):
        df = bcb_inflation._extract(settings, bq, "proj.ds.tbl", full=False)

    assert set(df.columns) == {
        "series_code",
        "series_name",
        "reference_date_str",
        "value_str",
        "ingestion_timestamp",
    }
    # Series-name labels propagate from the config map.
    assert set(df["series_name"]) == {"IPCA", "IGPM"}


# ─── run() — delta branch end-to-end with all sinks mocked ───────────────────
def test_run_delta_short_circuits_with_no_new_data(settings: Settings) -> None:
    """When _extract returns empty, run() must NOT touch GCS or load_dataframe."""
    with (
        patch("embrapa_commodities.bcb.inflation.bigquery.Client"),
        patch("embrapa_commodities.bcb.inflation.latest_reference_date") as latest,
        patch(
            "embrapa_commodities.bcb.inflation.fetch_series",
            return_value=pd.DataFrame(),
        ),
        patch("embrapa_commodities.bcb.inflation.storage.Client") as gcs_cls,
        patch("embrapa_commodities.bcb.inflation.ensure_bucket") as ensure_bucket,
        patch("embrapa_commodities.bcb.inflation.upload_dataframe_as_parquet") as upload,
        patch("embrapa_commodities.bcb.inflation.load_dataframe") as load,
        patch("embrapa_commodities.bcb.inflation.ensure_dataset"),
    ):
        latest.return_value = date(2026, 1, 1)
        destination = bcb_inflation.run(settings, full=False)

    assert destination == ""
    gcs_cls.assert_not_called()
    ensure_bucket.assert_not_called()
    upload.assert_not_called()
    load.assert_not_called()


def test_run_full_passes_partition_and_cluster_keys(settings: Settings) -> None:
    fake_series_df = pd.DataFrame({"data": ["01/01/2020"], "valor": ["0.21"]})
    with (
        patch("embrapa_commodities.bcb.inflation.bigquery.Client"),
        patch("embrapa_commodities.bcb.inflation.storage.Client"),
        patch("embrapa_commodities.bcb.inflation.ensure_bucket"),
        patch("embrapa_commodities.bcb.inflation.ensure_dataset"),
        patch("embrapa_commodities.bcb.inflation.upload_dataframe_as_parquet"),
        patch("embrapa_commodities.bcb.inflation.load_dataframe") as load,
        patch("embrapa_commodities.bcb.inflation.fetch_series", return_value=fake_series_df),
    ):
        bcb_inflation.run(settings, full=True)

    load_kwargs = load.call_args.kwargs
    assert load_kwargs["time_partitioning_field"] == "ingestion_timestamp"
    assert load_kwargs["clustering_fields"] == ["series_code", "reference_date_str"]


def test_run_object_name_includes_inflation_year_window(settings: Settings) -> None:
    """GCS path: landing/bcb/<table>/run=<ts>/inflation_<from>_<to>.parquet."""
    fake_series_df = pd.DataFrame({"data": ["01/01/2020"], "valor": ["0.21"]})
    with (
        patch("embrapa_commodities.bcb.inflation.bigquery.Client"),
        patch("embrapa_commodities.bcb.inflation.storage.Client"),
        patch("embrapa_commodities.bcb.inflation.ensure_bucket"),
        patch("embrapa_commodities.bcb.inflation.ensure_dataset"),
        patch("embrapa_commodities.bcb.inflation.upload_dataframe_as_parquet") as upload,
        patch("embrapa_commodities.bcb.inflation.load_dataframe"),
        patch("embrapa_commodities.bcb.inflation.fetch_series", return_value=fake_series_df),
    ):
        bcb_inflation.run(settings, full=True)

    object_name = upload.call_args.args[2]
    assert (
        object_name.startswith("landing/bcb/inflation_series_raw/run=")
        and "inflation_1980_2026.parquet" in object_name
    )
