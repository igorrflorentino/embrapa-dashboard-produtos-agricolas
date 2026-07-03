"""Coverage tests for the UN Comtrade client + pipeline error/edge branches.

These exercise the un-covered failure paths the existing
``test_comtrade_client.py`` / ``test_comtrade_pipeline.py`` suites leave open:

client.py
  - ``_retry_after_seconds`` unparseable header → ``None`` (the ValueError arm)
  - ``list_hs6_codes`` non-200 HS reference → ``ComtradeTransientError``
  - ``fetch_chunk`` retryable non-429 status (503) → ``ComtradeTransientError``
  - ``fetch_chunk_adaptive`` rejects a multi-year list → ``ValueError``

pipeline.py
  - ``has_raw`` returns the raw_provenance-is-not-None boolean
  - ``ensure_destination`` builds the dataset + table FQN via ``ensure_dataset``
  - ``process_chunk`` empty Bronze load → ``ChunkOutcome(..., "skipped", "no rows")``

HTTP is fully mocked (offline); GCP clients are MagicMocks. Style copied from the
existing comtrade tests: ``responses`` + ``.__wrapped__`` to bypass the retry
policy for the client, ``patch.object`` for the pipeline.
"""

from __future__ import annotations

import re
from unittest.mock import MagicMock, patch

import pytest
import responses

from embrapa_dashboard.comtrade import client, pipeline
from embrapa_dashboard.config import Settings

BASE_URL = "https://comtradeapi.un.org/data/v1/get"
API_KEY = "secret-key-123"


@pytest.fixture(autouse=True)
def _no_throttle(monkeypatch: pytest.MonkeyPatch) -> None:
    """Zero the keyed-call throttle so the suite never sleeps between calls."""
    monkeypatch.setattr(client, "INTER_CALL_DELAY_S", 0.0)


@pytest.fixture
def settings() -> Settings:
    return Settings(
        gcp_project_id="test-project",
        gcs_bucket="test-bucket",
        comtrade_api_key="secret-key",
        comtrade_cmd_codes="0801:castanha,44:madeira_carvao",
        comtrade_flows="X,M,RX,RM",
        comtrade_reporters="all",
        comtrade_start_year=2022,
        comtrade_end_year=2023,
        _env_file=None,
    )  # type: ignore[call-arg]


# ─── client._retry_after_seconds — unparseable header → None (ValueError arm) ──
def test_retry_after_seconds_unparseable_returns_none() -> None:
    """A non-numeric Retry-After (the HTTP-date form APIM never sends, or junk)
    is unparseable → None, so the caller falls back to the daily-quota default."""
    assert client._retry_after_seconds("not-a-number") is None
    assert client._retry_after_seconds("Wed, 21 Oct 2025 07:28:00 GMT") is None


def test_retry_after_seconds_absent_returns_none() -> None:
    """An absent header short-circuits before the float() parse."""
    assert client._retry_after_seconds(None) is None


def test_retry_after_seconds_numeric_parses() -> None:
    """The happy path the ValueError arm guards: a plain delta-seconds value."""
    assert client._retry_after_seconds("2") == 2.0


# ─── client.list_hs6_codes — non-200 HS reference → ComtradeTransientError ─────
@responses.activate
def test_list_hs6_codes_raises_transient_on_5xx_status() -> None:
    """A non-200 status on the public HS reference is a transient fetch failure —
    it must be retried (here we bypass the retry policy via __wrapped__) rather
    than crash the whole run before any chunk executes."""
    responses.add(responses.GET, client.HS_REF_URL, status=503)
    with pytest.raises(client.ComtradeTransientError) as exc:
        client.list_hs6_codes.__wrapped__(["0801", "44"])  # type: ignore[attr-defined]
    assert "HS reference" in str(exc.value)


# ─── client.fetch_chunk — retryable non-429 status (503) → ComtradeTransientError
@responses.activate
def test_fetch_chunk_raises_transient_on_retryable_503() -> None:
    """A 503 (in RETRYABLE_STATUS_CODES, but not 429) on a keyed data call is a
    transient error: not the permanent ComtradeRequestError and not the quota
    error, so the shared retry policy re-attempts it."""
    assert 503 in client.core_http.RETRYABLE_STATUS_CODES  # guard the premise
    responses.add(responses.GET, re.compile(rf"{re.escape(BASE_URL)}/C/A/HS.*"), status=503)
    with pytest.raises(client.ComtradeTransientError) as exc:
        client.fetch_chunk.__wrapped__(  # type: ignore[attr-defined]
            BASE_URL, API_KEY, reporters=["76"], years=[2022], cmd_codes=["0801"], flows=["X"]
        )
    assert "HTTP 503" in str(exc.value)
    assert not isinstance(exc.value, client.ComtradeQuotaError)  # 503 is not quota


# ─── client.fetch_chunk_adaptive — multi-year list rejected → ValueError ──────
def test_fetch_chunk_adaptive_rejects_multi_year_list() -> None:
    """The splitter divides reporters→flows→cmd_codes but NOT years, so a
    multi-year list would risk a FALSE 'un-splittable' truncation. The
    precondition check (un-stripped by ``python -O``) raises ValueError up front."""
    with pytest.raises(ValueError, match="single year"):
        client.fetch_chunk_adaptive(
            BASE_URL,
            API_KEY,
            reporters=["76"],
            years=[2022, 2023],
            cmd_codes=["0801"],
            flows=["X"],
        )


def test_fetch_chunk_adaptive_rejects_empty_year_list() -> None:
    """An empty year list is also not a single year → same guard."""
    with pytest.raises(ValueError, match="single year"):
        client.fetch_chunk_adaptive(
            BASE_URL, API_KEY, reporters=["76"], years=[], cmd_codes=["0801"], flows=["X"]
        )


# ─── pipeline.has_raw — boolean over raw_provenance ───────────────────────────
def test_has_raw_true_when_provenance_present(settings) -> None:
    with patch.object(pipeline, "raw_provenance", return_value={"source": "un-comtrade"}) as prov:
        assert pipeline.has_raw(settings, 2022, ["76"], storage_client=MagicMock()) is True
    prov.assert_called_once()
    assert prov.call_args.kwargs["basename"] == pipeline._basename(2022, ["76"])


def test_has_raw_false_when_provenance_absent(settings) -> None:
    with patch.object(pipeline, "raw_provenance", return_value=None):
        assert pipeline.has_raw(settings, 2022, ["76"], storage_client=MagicMock()) is False


# ─── pipeline.ensure_destination — dataset + table FQN via ensure_dataset ──────
def test_ensure_destination_builds_fqn_and_ensures_dataset(settings) -> None:
    bq_client = MagicMock()
    with patch.object(pipeline, "ensure_dataset") as ensure:
        table_fqn = pipeline.ensure_destination(settings, bq_client)
    expected_dataset = f"{settings.gcp_project_id}.{settings.bq_bronze_comtrade_dataset}"
    assert table_fqn == f"{expected_dataset}.{settings.bq_bronze_comtrade_flows_table}"
    ensure.assert_called_once_with(bq_client, expected_dataset, settings.bq_location)


# ─── pipeline.process_chunk — empty Bronze load → "no rows" skipped outcome ────
def test_process_chunk_no_rows_returns_skipped(settings) -> None:
    """When sync_raw (re)fetched and needs_bronze is True but bronze_one returns ''
    (an empty raw → no Bronze load), the chunk outcome is 'skipped: no rows'."""
    with (
        patch.object(pipeline, "sync_raw", return_value=True),
        patch.object(pipeline, "needs_bronze", return_value=True),
        patch.object(pipeline, "bronze_one", return_value=""),  # empty raw → no destination
        patch.object(pipeline, "mark_bronze_loaded") as mark,
    ):
        outcome = pipeline.process_chunk(
            settings,
            2022,
            ["76"],
            storage_client=MagicMock(),
            bq_client=MagicMock(),
            table_fqn="p.d.t",
        )
    assert outcome.status == "skipped"
    assert outcome.detail == "no rows"
    assert outcome.chunk_id == pipeline._basename(2022, ["76"])
    mark.assert_called_once()  # the marker is stamped even for a 0-row load


def test_process_chunk_loaded_returns_destination(settings) -> None:
    """Contrast path (same function, non-empty load) → 'loaded' with destination,
    pinning that the 'no rows' branch above is the only divergence."""
    with (
        patch.object(pipeline, "sync_raw", return_value=True),
        patch.object(pipeline, "needs_bronze", return_value=True),
        patch.object(pipeline, "bronze_one", return_value="p.d.t"),
        patch.object(pipeline, "mark_bronze_loaded"),
    ):
        outcome = pipeline.process_chunk(
            settings,
            2022,
            ["76"],
            storage_client=MagicMock(),
            bq_client=MagicMock(),
            table_fqn="p.d.t",
        )
    assert outcome.status == "loaded"
    assert outcome.destination == "p.d.t"


def test_process_chunk_from_raw_no_raw_returns_skipped(settings) -> None:
    """from_raw with no archived raw skips before any load (already-archived guard)."""
    with patch.object(pipeline, "has_raw", return_value=False):
        outcome = pipeline.process_chunk(
            settings,
            2022,
            ["76"],
            storage_client=MagicMock(),
            bq_client=MagicMock(),
            table_fqn="p.d.t",
            from_raw=True,
        )
    assert outcome.status == "skipped"
    assert outcome.detail == "already archived"
