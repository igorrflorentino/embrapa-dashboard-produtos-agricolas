"""Coverage tests for the IBGE SIDRA client error/retry/edge branches.

Targets the currently-uncovered lines in ``embrapa_dashboard.ibge.client``:
- ``_emit_retry`` tenacity before_sleep hook (227-235)
- ``_http_get_once`` non-limit status handling (267-270)
- ``_fetch_block`` re-raise on single-year cell-limit (367)
- ``_fetch_by_state_parallel`` generic-exception log+re-raise (443-445)
- ``fetch_sidra_dataframe`` short-payload skip (492) + no-rows empty frame (504-511)

HTTP is fully mocked (monkeypatch ``core_http.get_drained`` / module helpers),
matching the style of ``tests/test_ibge_client.py``.
"""

from __future__ import annotations

import pytest

from embrapa_dashboard.ibge import client


# ─── _emit_retry tenacity before_sleep hook (227-235) ────────────────────────
class _FakeOutcome:
    def __init__(self, exc: Exception | None) -> None:
        self._exc = exc

    def exception(self) -> Exception | None:
        return self._exc


class _FakeRetryState:
    def __init__(self, exc: Exception | None, attempt_number: int = 2) -> None:
        self.outcome = _FakeOutcome(exc)
        self.attempt_number = attempt_number


def test_emit_retry_emits_event_with_state_and_reason(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The before_sleep hook emits a structured `retry` event carrying the
    contextvar's UF, the attempt number and a truncated reason."""
    events: list[tuple[str, dict]] = []
    monkeypatch.setattr(
        client.observability, "emit", lambda event, **fields: events.append((event, fields))
    )
    token = client._current_state.set("BA")
    try:
        client._emit_retry(_FakeRetryState(RuntimeError("boom"), attempt_number=3))
    finally:
        client._current_state.reset(token)

    assert len(events) == 1
    name, fields = events[0]
    assert name == "retry"
    assert fields["state"] == "BA"
    assert fields["attempt"] == 3
    assert fields["reason"] == "boom"


def test_emit_retry_handles_missing_outcome(monkeypatch: pytest.MonkeyPatch) -> None:
    """When there is no outcome/exception, the reason falls back to '?'."""
    events: list[tuple[str, dict]] = []
    monkeypatch.setattr(
        client.observability, "emit", lambda event, **fields: events.append((event, fields))
    )

    class _NoOutcome:
        outcome = None
        attempt_number = 1

    client._emit_retry(_NoOutcome())
    assert len(events) == 1
    assert events[0][1]["reason"] == "?"


# ─── _http_get_once non-limit status handling (267-270) ──────────────────────
class _FakeResponse:
    def __init__(self, status_code: int, text: str = "") -> None:
        self.status_code = status_code
        self.text = text
        self.closed = False

    def close(self) -> None:
        self.closed = True


def _patch_get_drained(monkeypatch: pytest.MonkeyPatch, response: _FakeResponse) -> None:
    monkeypatch.setattr(client.core_http, "get_drained", lambda url, **kwargs: response)


def test_http_get_once_non_retryable_4xx_raises_request_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A 400 whose body is NOT a cell-limit message, and whose status is not in
    RETRYABLE_STATUS_CODES, raises the base SidraRequestError (line 270)."""
    resp = _FakeResponse(400, text="Bad request: unknown table")
    _patch_get_drained(monkeypatch, resp)
    with pytest.raises(client.SidraRequestError) as ei:
        client._http_get_once("https://apisidra.ibge.gov.br/values/t/289/p/2020")
    # Not the transient subclass — a plain non-retryable error.
    assert not isinstance(ei.value, client.SidraTransientError)
    assert "HTTP 400" in str(ei.value)
    assert resp.closed  # the BaseException guard released the socket


def test_http_get_once_404_raises_request_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """A 404 (not 400/403, not retryable) goes straight to SidraRequestError (267, 270)."""
    resp = _FakeResponse(404, text="Not found")
    _patch_get_drained(monkeypatch, resp)
    with pytest.raises(client.SidraRequestError):
        client._http_get_once("https://apisidra.ibge.gov.br/values/t/289/p/2020")
    assert resp.closed


def test_http_get_once_retryable_status_raises_transient(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A 503 (in RETRYABLE_STATUS_CODES) raises the retryable SidraTransientError (268-269)."""
    resp = _FakeResponse(503, text="Service Unavailable")
    _patch_get_drained(monkeypatch, resp)
    with pytest.raises(client.SidraTransientError) as ei:
        client._http_get_once("https://apisidra.ibge.gov.br/values/t/289/p/2020")
    assert "HTTP 503" in str(ei.value)
    assert resp.closed


def test_http_get_once_403_cell_limit_raises_limit_exceeded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A 403 whose body mentions 'limite'/'valores' is the cell-limit branch (265-266)."""
    resp = _FakeResponse(403, text="Limite de valores excedido")
    _patch_get_drained(monkeypatch, resp)
    with pytest.raises(client.SidraLimitExceeded):
        client._http_get_once("https://apisidra.ibge.gov.br/values/t/289/p/2020")
    assert resp.closed


# ─── _fetch_block re-raise on single-year cell-limit (367) ───────────────────
def test_fetch_block_reraises_limit_on_single_year(monkeypatch: pytest.MonkeyPatch) -> None:
    """When the period is already a single year, a SidraLimitExceeded cannot be
    halved further, so it propagates to the caller (line 367)."""

    def boom(url, *, total_deadline_s, retry_budget_s):  # type: ignore[no-untyped-def]
        raise client.SidraLimitExceeded("limite de valores excedido")

    monkeypatch.setattr(client, "_http_get", boom)
    with pytest.raises(client.SidraLimitExceeded):
        client._fetch_block("289", [2020], "n3", "all", "193", ["3405"], variables="all")


# ─── _fetch_by_state_parallel generic-exception log+re-raise (443-445) ───────
def test_fetch_by_state_parallel_reraises_generic_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A non-limit failure inside a state worker is logged and re-raised
    (the generic `except Exception` branch, lines 443-445)."""

    def boom(*_a, **_k):
        raise RuntimeError("network down")

    # Patch the per-state worker so every future raises a generic error.
    monkeypatch.setattr(client, "_fetch_one_state", boom)
    with pytest.raises(RuntimeError, match="network down"):
        client._fetch_by_state_parallel("289", [2020], "193", ["3405"])


# ─── fetch_sidra_dataframe short-payload skip (492) + no-rows path (504-511) ──
def test_fetch_sidra_dataframe_skips_short_payloads_returns_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every state replies OK but with header-only / empty payloads (len < 2):
    the loop `continue`s past each (line 492), no frames accumulate, and the
    no-rows warning + empty-frame return fire (lines 504-511)."""
    warnings: list[str] = []
    monkeypatch.setattr(
        client.logger, "warning", lambda msg, *a, **k: warnings.append(msg % a if a else msg)
    )
    # A header-only payload (len 1) and an empty payload (len 0) both get skipped.
    monkeypatch.setattr(
        client,
        "_fetch_by_state_parallel",
        lambda *_a, **_k: [[{"V": "Valor"}], []],
    )

    df = client.fetch_sidra_dataframe(
        table_id="289",
        start_year=2024,
        end_year=2025,
        classification="193",
        products=["3405"],
        geo_level="n6",
    )
    assert df.empty
    # The "no rows" warning (504-511) fired with the table id interpolated.
    assert any("no rows" in w for w in warnings)


def test_fetch_sidra_dataframe_skips_short_payload_keeps_valid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A mix of one too-short payload (skipped at 492) and one valid payload still
    returns the valid rows — proves `continue` skips only the empty one."""
    valid_payload = [
        {"MC": "Município (Código)", "V": "Valor"},
        {"MC": "1100015", "V": "10"},
    ]
    monkeypatch.setattr(
        client,
        "_fetch_by_state_parallel",
        lambda *_a, **_k: [[], valid_payload],  # first is empty → skipped, second kept
    )

    df = client.fetch_sidra_dataframe(
        table_id="289",
        start_year=2024,
        end_year=2024,
        classification="193",
        products=["3405"],
        geo_level="n6",
    )
    assert len(df) == 1
    # Header row promoted to columns, then cleaned to ASCII snake_case.
    assert "municipio_codigo" in df.columns
    assert "valor" in df.columns
