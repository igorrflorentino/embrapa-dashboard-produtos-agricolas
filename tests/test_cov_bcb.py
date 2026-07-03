"""Coverage tests for bcb/client.py + bcb/series.py error/edge branches.

Targets the few uncovered lines:
  client.py:120  — non-retryable, non-404 HTTP status raises BcbRequestError.
  client.py:146  — fetch_series chunking where every chunk is empty.
  series.py:235-238 — run(from_raw=True) with no archived raw → returns "".

HTTP is fully mocked (``responses``) for the client; the pipeline mocks the
GCP clients + raw-archive helpers, mirroring test_bcb_client.py /
test_bcb_series.py.
"""

from __future__ import annotations

import re
from datetime import date
from unittest.mock import patch

import pytest
import responses

from embrapa_dashboard.bcb import client
from embrapa_dashboard.bcb import series as bcb_series
from embrapa_dashboard.bcb.inflation import SPEC as INFLATION_SPEC
from embrapa_dashboard.config import Settings


@pytest.fixture
def settings() -> Settings:
    return Settings(
        gcp_project_id="test-project",
        gcs_bucket="test-bucket",
        bcb_start_year=1980,
        bcb_end_year=2026,
        bcb_inflation_series="433:IPCA,189:IGPM,190:IGPDI",
        bcb_currency_series="3694:USD,4393:EUR",
        _env_file=None,
    )  # type: ignore[call-arg]


# ─── client.py:120 — non-retryable, non-404 HTTP error ───────────────────────
@responses.activate
def test_fetch_series_raises_on_non_retryable_status() -> None:
    """A 400 is neither 404 (mapped to empty) nor in RETRYABLE_STATUS_CODES, so
    _fetch_window must raise the non-retryable BcbRequestError (and NOT the
    transient subclass, so tenacity does not retry it)."""
    assert 400 not in client.core_http.RETRYABLE_STATUS_CODES
    responses.add(
        method=responses.GET,
        url=re.compile(r"https://api\.bcb\.gov\.br/dados/serie/bcdata\.sgs\.433/dados.*"),
        status=400,
        body="bad request",
    )

    with pytest.raises(client.BcbRequestError) as excinfo:
        client.fetch_series("433", 2020, 2020)

    # The non-retryable branch raises the base class, not the transient subclass.
    assert not isinstance(excinfo.value, client.BcbTransientError)
    assert "HTTP 400" in str(excinfo.value)
    # Non-retryable ⇒ exactly one HTTP call (no tenacity retries).
    assert len(responses.calls) == 1


# ─── client.py:146 — chunked fetch where every chunk comes back empty ────────
@responses.activate
def test_fetch_series_chunked_all_empty_returns_empty_df() -> None:
    """A window wider than MAX_YEARS_PER_REQUEST fans out into chunks; if every
    chunk 404s (no data), no frames accumulate and fetch_series returns the
    canonical empty DataFrame (the `if not frames` guard)."""
    responses.add(
        method=responses.GET,
        url=re.compile(r"https://api\.bcb\.gov\.br/dados/serie/bcdata\.sgs\.21619/dados.*"),
        status=404,
        body="Not found",
    )

    # 25-year window → 3 chunks, all empty.
    df = client.fetch_series("21619", 2000, 2024)

    assert df.empty
    assert list(df.columns) == ["data", "valor"]
    assert len(responses.calls) == 3


# ─── series.py:235-238 — run(from_raw=True) with no archived raw ─────────────
def test_run_from_raw_with_no_archive_returns_empty(settings) -> None:
    """``--from-raw`` reads the archived raw trail; when ``list_raw`` finds none,
    run logs and short-circuits with "" without ever fetching SGS or writing
    Bronze."""
    with (
        patch("embrapa_dashboard.gcp.clients.bigquery.Client"),
        patch("embrapa_dashboard.gcp.clients.storage.Client"),
        patch("embrapa_dashboard.bcb.series.ensure_dataset"),
        patch("embrapa_dashboard.bcb.series.list_raw", return_value=[]) as list_raw,
        patch("embrapa_dashboard.bcb.series.fetch_series") as fetch,
        patch("embrapa_dashboard.bcb.series.read_raw") as read,
        patch("embrapa_dashboard.bcb.series.load_dataframe") as load,
    ):
        destination = bcb_series.run(INFLATION_SPEC, settings, full=False, from_raw=True)

    assert destination == ""
    # from_raw path inspected the archive...
    list_raw.assert_called_once()
    assert list_raw.call_args.kwargs["dataset"] == INFLATION_SPEC.kind
    # ...and never fetched SGS nor touched Bronze.
    fetch.assert_not_called()
    read.assert_not_called()
    load.assert_not_called()


def test_run_from_raw_with_archive_replays_trail(settings) -> None:
    """Counter-case proving the empty-archive short-circuit is the only reason
    test above returns "": with a non-empty trail, run replays each basename
    through bronze_from_raw and returns the destination FQN."""
    captured: dict = {}

    def fake_read(*_a, **_kw):
        import pandas as pd

        return pd.DataFrame(
            {
                "series_code": ["433"],
                "series_name": ["IPCA"],
                "reference_date_str": ["01/01/2020"],
                "value_str": ["1.23"],
            }
        )

    def fake_load(_bq, _df, destination, *_a, **_kw):
        captured["destination"] = destination

    with (
        patch("embrapa_dashboard.gcp.clients.bigquery.Client"),
        patch("embrapa_dashboard.gcp.clients.storage.Client"),
        patch("embrapa_dashboard.bcb.series.ensure_dataset"),
        patch(
            "embrapa_dashboard.bcb.series.list_raw",
            return_value=["20200101T000000Z_2020_2020"],
        ),
        patch("embrapa_dashboard.bcb.series.read_raw", side_effect=fake_read),
        patch("embrapa_dashboard.bcb.series.load_dataframe", side_effect=fake_load),
    ):
        destination = bcb_series.run(INFLATION_SPEC, settings, full=False, from_raw=True)

    assert destination != ""
    assert destination == captured["destination"]
    assert destination.endswith(INFLATION_SPEC.table(settings))


# ─── extra branch: delta lookup uses the spec overlap year ───────────────────
def test_effective_start_year_uses_overlap_rule(settings) -> None:
    """When prior data exists, the start is max(configured, overlap_year(last)).
    Inflation rewinds a calendar year, so a mid-2025 last load yields 2024."""
    import unittest.mock as um

    bq = um.MagicMock()
    with patch(
        "embrapa_dashboard.bcb.series.latest_reference_date",
        return_value=date(2025, 6, 1),
    ):
        result = bcb_series.effective_start_year(INFLATION_SPEC, bq, "proj.ds.tbl", "433", 1980)
    assert result == 2024
