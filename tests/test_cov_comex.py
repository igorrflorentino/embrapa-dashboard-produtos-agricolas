"""Coverage top-up for the Comex client + pipeline error/edge branches.

Targets the uncovered tails the existing ``test_comex_client.py`` /
``test_comex_pipeline.py`` suites don't reach: the ``_unlink_quietly`` atexit
helper, the ``_head_retry_url`` unknown-flow fallback, the ``_download_to_disk``
slow-byte hang INSIDE the body loop, the ``head_source`` permanent-error branch,
and the pipeline ``has_raw`` / ``mark_bronze_loaded`` / ``ensure_destination``
helpers. Same patterns as the existing suites: ``__wrapped__`` strips the
tenacity retry so a single attempt is observed, ``responses`` mocks HTTP, and
``patch.object`` mocks the GCP layer.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import responses

from embrapa_dashboard.comex import client, pipeline
from embrapa_dashboard.config import Settings


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


# ─── _unlink_quietly (atexit temp-PEM cleanup) ───────────────────────────────
def test_unlink_quietly_removes_existing_file(tmp_path: Path) -> None:
    target = tmp_path / "comex_ca_tmp.pem"
    target.write_text("PEM", encoding="ascii")
    client._unlink_quietly(str(target))
    assert not target.exists()  # deleted


def test_unlink_quietly_swallows_missing_file(tmp_path: Path) -> None:
    """A second call (or a file already gone) raises OSError under the hood; the
    helper must suppress it silently so the atexit handler never crashes."""
    missing = tmp_path / "already_gone.pem"
    assert not missing.exists()
    client._unlink_quietly(str(missing))  # must not raise


# ─── _head_retry_url (unknown-flow fallback) ─────────────────────────────────
def test_head_retry_url_rebuilds_file_url_for_known_flow() -> None:
    url = client._head_retry_url(("https://host/ncm", "export", 2023), {})
    assert url == "https://host/ncm/EXP_2023.csv"


def test_head_retry_url_falls_back_to_base_on_unknown_flow() -> None:
    """An unknown flow makes ``file_url`` raise KeyError on FILE_PREFIX; the
    helper falls back to the base URL instead of propagating (line 136-137)."""
    url = client._head_retry_url(("https://host/ncm", "not_a_flow", 2023), {})
    assert url == "https://host/ncm"


def test_head_retry_url_falls_back_when_args_missing() -> None:
    # No flow/year in args or kwargs → base_url '?' default, FILE_PREFIX['?']
    # raises KeyError → base-URL fallback.
    url = client._head_retry_url((), {})
    assert url == "?"


# ─── _download_to_disk slow-byte hang INSIDE the body loop (line 212) ─────────
def test_download_to_disk_slow_byte_hang_inside_body_loop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The wall-clock deadline must also fire MID-STREAM: after the status check
    passes (200) and the first chunk arrives, a monotonic tick past the deadline
    aborts the iteration with a transient (the slow-byte-hang branch, line 212)."""
    # 1) deadline compute, 2) pre-status check (still in budget), 3) inside the
    # loop on the first chunk (now past the budget → raise).
    ticks = iter([0.0, 1.0, client.DOWNLOAD_DEADLINE_S + 1.0])
    monkeypatch.setattr(client.time, "monotonic", lambda: next(ticks))

    class _Resp:
        status_code = 200

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def iter_content(self, chunk_size):
            return iter([b"first-chunk", b"second-chunk"])

    monkeypatch.setattr(client.requests, "get", lambda url, **kw: _Resp())
    with pytest.raises(client.ComexTransientError) as exc:
        client._download_to_disk.__wrapped__(  # type: ignore[attr-defined]
            "https://host/EXP_2023.csv", str(tmp_path / "out.csv")
        )
    assert "slow-byte hang" in str(exc.value)


# ─── head_source permanent error on non-retryable status (line 251) ───────────
@responses.activate
def test_head_source_raises_permanent_on_404() -> None:
    """A 404 (HEAD) is NOT in RETRYABLE_STATUS_CODES, so head_source raises the
    permanent ComexRequestError (not the transient subclass) — line 251."""
    responses.add(responses.HEAD, "https://h/ncm/EXP_2099.csv", status=404)
    with pytest.raises(client.ComexRequestError) as exc:
        client.head_source.__wrapped__("https://h/ncm", "export", 2099)  # type: ignore[attr-defined]
    assert not isinstance(exc.value, client.ComexTransientError)  # permanent
    assert "404" in str(exc.value)


# ─── pipeline.has_raw (line 227) ─────────────────────────────────────────────
def test_has_raw_true_when_provenance_present(settings) -> None:
    with patch.object(pipeline, "raw_provenance", return_value={"source_etag": "v1"}) as prov:
        assert pipeline.has_raw(settings, "export", 2023, storage_client=MagicMock()) is True
    assert prov.call_args.kwargs["basename"] == "EXP_2023"


def test_has_raw_false_when_no_provenance(settings) -> None:
    with patch.object(pipeline, "raw_provenance", return_value=None):
        assert pipeline.has_raw(settings, "import", 2020, storage_client=MagicMock()) is False


# ─── pipeline.mark_bronze_loaded (line 272) ──────────────────────────────────
def test_mark_bronze_loaded_stamps_raw_object(settings) -> None:
    sc = MagicMock()
    with patch.object(pipeline, "mark_raw_bronze_loaded") as mark:
        pipeline.mark_bronze_loaded(settings, "export", 2021, storage_client=sc)
    mark.assert_called_once()
    kwargs = mark.call_args.kwargs
    assert kwargs["source"] == "comex"
    assert kwargs["dataset"] == pipeline.RAW_DATASET
    assert kwargs["basename"] == "EXP_2021"


# ─── pipeline.ensure_destination (lines 283-285) ─────────────────────────────
def test_ensure_destination_creates_dataset_and_returns_fqn(settings) -> None:
    bq = MagicMock()
    with patch.object(pipeline, "ensure_dataset") as ensure:
        fqn = pipeline.ensure_destination(settings, bq)
    expected_dataset = f"{settings.gcp_project_id}.{settings.bq_bronze_comex_dataset}"
    ensure.assert_called_once_with(bq, expected_dataset, settings.bq_location)
    assert fqn == f"{expected_dataset}.{settings.bq_bronze_comex_flows_table}"
