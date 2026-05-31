"""Tests for the UN Comtrade keyed JSON client (HTTP fully mocked, offline).

Pins the live-validated contract (2026-05-30): keyed GET to ``/C/A/HS`` with
comma-list query params, the subscription key carried **only** in the
``Ocp-Apim-Subscription-Key`` header (never the URL/log), ``partnerCode`` omitted
so every partner returns, and a string-typed frame reindexed to BRONZE_COLUMNS.
"""

from __future__ import annotations

import re

import pytest
import responses

from embrapa_commodities.comtrade import client

BASE_URL = "https://comtradeapi.un.org/data/v1/get"
API_KEY = "secret-key-123"

# A trimmed two-row API payload (only some of the ~50 fields present, to exercise
# the reindex that fills missing BRONZE_COLUMNS with NA).
DATA_PAYLOAD = {
    "data": [
        {
            "refYear": 2022,
            "period": 2022,
            "reporterCode": 76,
            "flowCode": "X",
            "partnerCode": 0,
            "cmdCode": "0801",
            "qty": 1234,
            "netWgt": 1230,
            "primaryValue": 98765,
        },
        {
            "refYear": 2022,
            "period": 2022,
            "reporterCode": 76,
            "flowCode": "M",
            "partnerCode": 842,
            "cmdCode": "44",
            "qtyUnitCode": -1,  # chapter-44 imports often omit quantity
            "qty": None,
            "primaryValue": 4321,
        },
    ]
}

REPORTERS_PAYLOAD = {
    "results": [
        {"reporterCode": "76", "text": "Brazil", "isGroup": False},
        {"reporterCode": "842", "text": "USA", "isGroup": False},
        {"reporterCode": "0", "text": "World", "isGroup": True},  # aggregate → dropped
        {"reporterCode": "841", "text": "USA (before 1981)", "isGroup": False},
    ]
}


# ─── list_reporters ──────────────────────────────────────────────────────────
@responses.activate
def test_list_reporters_excludes_groups() -> None:
    responses.add(responses.GET, client.REPORTERS_REF_URL, json=REPORTERS_PAYLOAD, status=200)
    codes = client.list_reporters()
    assert codes == ["76", "842", "841"]  # group code 0 dropped, all stringified


@responses.activate
def test_list_reporters_raises_transient_on_5xx() -> None:
    responses.add(responses.GET, client.REPORTERS_REF_URL, status=503)
    with pytest.raises(client.ComtradeTransientError):
        client.list_reporters()


# ─── fetch_chunk ─────────────────────────────────────────────────────────────
@responses.activate
def test_fetch_chunk_returns_string_frame_reindexed_to_bronze_columns() -> None:
    responses.add(
        responses.GET, re.compile(rf"{re.escape(BASE_URL)}/C/A/HS.*"), json=DATA_PAYLOAD, status=200
    )
    df = client.fetch_chunk(
        BASE_URL,
        API_KEY,
        reporters=["76"],
        years=[2022],
        cmd_codes=["0801", "44"],
        flows=["X", "M"],
    )
    assert list(df.columns) == client.BRONZE_COLUMNS
    assert len(df) == 2
    assert df["primaryValue"].tolist() == ["98765", "4321"]
    # Columns absent from the sparse payload are present as NA, not missing.
    assert "customsCode" in df.columns
    assert df["customsCode"].isna().all()
    assert str(df["primaryValue"].dtype) == "string"


@responses.activate
def test_fetch_chunk_sends_key_in_header_only_never_in_url() -> None:
    responses.add(
        responses.GET, re.compile(rf"{re.escape(BASE_URL)}/C/A/HS.*"), json=DATA_PAYLOAD, status=200
    )
    client.fetch_chunk(
        BASE_URL, API_KEY, reporters=["76", "842"], years=[2022], cmd_codes=["0801"], flows=["X"]
    )
    req = responses.calls[0].request
    assert req.headers["Ocp-Apim-Subscription-Key"] == API_KEY
    assert API_KEY not in req.url  # secret never leaks into the URL/logs


@responses.activate
def test_fetch_chunk_builds_comma_lists_and_omits_partner_code() -> None:
    responses.add(
        responses.GET, re.compile(rf"{re.escape(BASE_URL)}/C/A/HS.*"), json=DATA_PAYLOAD, status=200
    )
    client.fetch_chunk(
        BASE_URL,
        API_KEY,
        reporters=["76", "842"],
        years=[2022, 2023],
        cmd_codes=["0801", "44"],
        flows=["X", "M"],
    )
    url = responses.calls[0].request.url
    assert "reporterCode=76,842" in url
    assert "period=2022,2023" in url
    assert "cmdCode=0801,44" in url
    assert "flowCode=X,M" in url
    assert "partnerCode" not in url  # omitted → every partner (bilateral matrix)


@responses.activate
def test_fetch_chunk_empty_data_returns_empty_bronze_frame() -> None:
    responses.add(
        responses.GET, re.compile(rf"{re.escape(BASE_URL)}/C/A/HS.*"), json={"data": []}, status=200
    )
    df = client.fetch_chunk(
        BASE_URL, API_KEY, reporters=["76"], years=[2022], cmd_codes=["0801"], flows=["X"]
    )
    assert df.empty
    assert list(df.columns) == client.BRONZE_COLUMNS


@responses.activate
def test_fetch_chunk_raises_permanent_on_400() -> None:
    responses.add(responses.GET, re.compile(rf"{re.escape(BASE_URL)}/C/A/HS.*"), status=400)
    with pytest.raises(client.ComtradeRequestError) as exc:
        client.fetch_chunk.__wrapped__(  # type: ignore[attr-defined]
            BASE_URL, API_KEY, reporters=["76"], years=[2022], cmd_codes=["0801"], flows=["X"]
        )
    assert not isinstance(exc.value, client.ComtradeTransientError)  # 400 not retried


@responses.activate
def test_fetch_chunk_raises_transient_on_429() -> None:
    responses.add(responses.GET, re.compile(rf"{re.escape(BASE_URL)}/C/A/HS.*"), status=429)
    with pytest.raises(client.ComtradeTransientError):  # rate limit → retryable
        client.fetch_chunk.__wrapped__(  # type: ignore[attr-defined]
            BASE_URL, API_KEY, reporters=["76"], years=[2022], cmd_codes=["0801"], flows=["X"]
        )
