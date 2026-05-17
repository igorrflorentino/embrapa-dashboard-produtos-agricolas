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
