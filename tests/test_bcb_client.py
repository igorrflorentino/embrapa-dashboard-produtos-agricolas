"""Tests for the BCB SGS client + discover.sample_bcb_series (HTTP fully mocked)."""

from __future__ import annotations

import re

import pytest
import responses

from embrapa_commodities import discover
from embrapa_commodities.bcb import client


@responses.activate
def test_fetch_series_returns_dataframe() -> None:
    payload = [
        {"data": "01/01/2020", "valor": "5.20"},
        {"data": "01/02/2020", "valor": "5.30"},
    ]
    responses.add(
        method=responses.GET,
        url=re.compile(r"https://api\.bcb\.gov\.br/dados/serie/bcdata\.sgs\.3694/dados.*"),
        json=payload,
        status=200,
    )

    df = client.fetch_series("3694", 2020, 2020)
    assert list(df.columns) == ["data", "valor"]
    assert len(df) == 2


@responses.activate
def test_fetch_series_returns_empty_on_no_data() -> None:
    responses.add(
        method=responses.GET,
        url=re.compile(r"https://api\.bcb\.gov\.br/dados/serie/bcdata\.sgs\.20542/dados.*"),
        json=[],
        status=200,
    )

    df = client.fetch_series("20542", 1900, 1900)
    assert df.empty
    assert list(df.columns) == ["data", "valor"]


@responses.activate
def test_fetch_series_raises_on_http_error() -> None:
    responses.add(
        method=responses.GET,
        url=re.compile(r"https://api\.bcb\.gov\.br/dados/serie/bcdata\.sgs\.999/dados.*"),
        status=500,
        body="internal error",
    )
    # tenacity will retry but ultimately re-raise
    with pytest.raises(client.BcbRequestError):
        client.fetch_series("999", 2020, 2020)


@responses.activate
def test_fetch_series_chunks_windows_larger_than_max() -> None:
    """A 25-year window should fan out into 3 HTTP calls of <= 10 years each."""
    payload = [{"data": "01/01/2020", "valor": "5.20"}]
    responses.add(
        method=responses.GET,
        url=re.compile(r"https://api\.bcb\.gov\.br/dados/serie/bcdata\.sgs\.3694/dados.*"),
        json=payload,
        status=200,
    )

    df = client.fetch_series("3694", 2000, 2024)

    # 25 years / 10 per request = 3 chunks (2000-2009, 2010-2019, 2020-2024).
    assert len(responses.calls) == 3
    assert len(df) == 3  # one row per chunk, since each mock returns 1 row


def test_fetch_window_delegates_to_core_drained(monkeypatch: pytest.MonkeyPatch) -> None:
    """``_fetch_window`` must call ``core_http.get_drained`` with the BCB-specific
    transient class, deadline, and a context that names the SGS series. Drain
    semantics themselves are covered in ``test_core_http.py``; this protects
    against accidentally rewiring the source-specific kwargs.
    """
    captured: dict[str, object] = {}

    class _FakeResponse:
        status_code = 200

        def json(self) -> list:
            return [{"data": "01/01/2020", "valor": "5.20"}]

        def close(self) -> None:
            pass

    def fake_get_drained(url: str, **kwargs: object) -> _FakeResponse:
        captured["url"] = url
        captured.update(kwargs)
        return _FakeResponse()

    monkeypatch.setattr(client.core_http, "get_drained", fake_get_drained)

    df = client._fetch_window.__wrapped__("433", 2020, 2020)  # type: ignore[attr-defined]
    assert len(df) == 1
    assert captured["transient_exc"] is client.BcbTransientError
    assert captured["total_deadline_s"] == client.REQUEST_TOTAL_DEADLINE_S
    assert captured["context"] == "SGS 433 2020-2020"


@responses.activate
def test_sample_bcb_series_returns_latest_observations() -> None:
    payload = [{"data": "01/05/2026", "valor": "5.10"}]
    responses.add(
        method=responses.GET,
        url=re.compile(r"https://api\.bcb\.gov\.br/dados/serie/bcdata\.sgs\.433/dados/ultimos/5.*"),
        json=payload,
        status=200,
    )
    sample = discover.sample_bcb_series("433", n=5)
    assert sample.code == "433"
    assert sample.sample == payload
