"""Tests for ``embrapa_dashboard.core.http`` — the shared HTTP primitives.

Covers the two helpers extracted from the IBGE and BCB clients in D1:

* ``http_retry_policy`` — a tenacity ``@retry`` factory.
* ``get_drained`` — GET with manual body drain under a wall-clock deadline.

The slow-byte deadline test that used to live in ``test_ibge_client.py``
(``test_http_get_aborts_on_total_request_deadline``) was migrated here
because ``time.monotonic()`` is now called inside ``core.http``, so the
patch must target ``core_http.time`` rather than ``client.time``.
"""

from __future__ import annotations

import re

import pytest
import requests
import responses

from embrapa_dashboard.core import SourceTransientError
from embrapa_dashboard.core import http as core_http


class _FakeTransient(SourceTransientError):
    """Stand-in for a source-specific transient class in these tests."""


class _FakeFatal(Exception):
    """A non-retryable exception — should propagate after a single attempt."""


# ---------------------------------------------------------------------------
# http_retry_policy
# ---------------------------------------------------------------------------


def test_retry_policy_retries_on_transient_exc() -> None:
    """A transient_exc raise on the first call should retry and then succeed."""
    calls = {"n": 0}

    @core_http.http_retry_policy(transient_exc=_FakeTransient, deadline_s=10.0, max_attempts=3)
    def flaky() -> str:
        calls["n"] += 1
        if calls["n"] < 2:
            raise _FakeTransient("not yet")
        return "ok"

    assert flaky() == "ok"
    assert calls["n"] == 2


def test_retry_policy_retries_on_requests_exception() -> None:
    """``requests.RequestException`` is always retryable, by contract."""
    calls = {"n": 0}

    @core_http.http_retry_policy(transient_exc=_FakeTransient, deadline_s=10.0, max_attempts=3)
    def flaky() -> str:
        calls["n"] += 1
        if calls["n"] < 2:
            raise requests.ConnectionError("boom")
        return "ok"

    assert flaky() == "ok"
    assert calls["n"] == 2


def test_retry_policy_does_not_retry_on_unrelated_exception() -> None:
    """Anything that's neither RequestException nor transient_exc should propagate."""
    calls = {"n": 0}

    @core_http.http_retry_policy(transient_exc=_FakeTransient, deadline_s=10.0, max_attempts=5)
    def always_fatal() -> None:
        calls["n"] += 1
        raise _FakeFatal("nope")

    with pytest.raises(_FakeFatal):
        always_fatal()
    assert calls["n"] == 1


def test_retry_policy_stops_after_max_attempts() -> None:
    """After ``max_attempts`` re-raises the last transient_exc."""
    calls = {"n": 0}

    @core_http.http_retry_policy(transient_exc=_FakeTransient, deadline_s=60.0, max_attempts=3)
    def always_transient() -> None:
        calls["n"] += 1
        raise _FakeTransient("still failing")

    with pytest.raises(_FakeTransient):
        always_transient()
    assert calls["n"] == 3


def test_retry_policy_calls_before_sleep_hook() -> None:
    """The ``before_sleep`` callback receives a RetryCallState per retry."""
    sleeps: list[int] = []

    def hook(retry_state) -> None:  # type: ignore[no-untyped-def]
        sleeps.append(retry_state.attempt_number)

    @core_http.http_retry_policy(
        transient_exc=_FakeTransient,
        deadline_s=10.0,
        max_attempts=3,
        before_sleep=hook,
    )
    def flaky() -> str:
        if len(sleeps) < 2:
            raise _FakeTransient("retry")
        return "ok"

    assert flaky() == "ok"
    # ``before_sleep`` fires once per retry (so attempts 1 and 2 here; the
    # 3rd attempt succeeds without sleeping).
    assert sleeps == [1, 2]


# ---------------------------------------------------------------------------
# get_drained
# ---------------------------------------------------------------------------


@responses.activate
def test_get_drained_returns_response_with_body_in_memory() -> None:
    """Happy path: ``.json()`` and ``.text`` work without re-reading the network."""
    payload = [{"data": "01/01/2020", "valor": "5.20"}]
    responses.add(
        method=responses.GET,
        url=re.compile(r"https://example\.test/.*"),
        json=payload,
        status=200,
    )

    response = core_http.get_drained(
        "https://example.test/data",
        total_deadline_s=10.0,
        transient_exc=_FakeTransient,
    )
    # Both .json() and .text must work — protects the invariant that
    # _content AND _content_consumed are both set.
    assert response.json() == payload
    assert "5.20" in response.text


@responses.activate
def test_get_drained_passes_through_non_200_without_raising() -> None:
    """Status-code semantics are caller-owned. ``get_drained`` returns 500 as-is."""
    responses.add(
        method=responses.GET,
        url=re.compile(r"https://example\.test/.*"),
        body="server error",
        status=500,
    )

    response = core_http.get_drained(
        "https://example.test/data",
        total_deadline_s=10.0,
        transient_exc=_FakeTransient,
    )
    assert response.status_code == 500
    assert response.text == "server error"


@responses.activate
def test_get_drained_aborts_on_total_request_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A slow-byte response that exceeds the deadline must raise transient_exc.

    Migrated from ``test_ibge_client.test_http_get_aborts_on_total_request_deadline``
    — the implementation now lives in ``core.http`` so the patch targets
    ``core_http.time`` instead of ``client.time``.
    """
    responses.add(
        method=responses.GET,
        url=re.compile(r"https://example\.test/.*"),
        body=b"x" * (200 * 1024),  # 200 KiB so iter_content actually iterates
        status=200,
        content_type="application/json",
    )

    # Force the deadline to fire on the very first iter_content chunk: each
    # time.monotonic() call jumps 100s, deadline is 0.0.
    counter = [0.0]

    def fake_monotonic() -> float:
        counter[0] += 100.0
        return counter[0]

    monkeypatch.setattr(core_http.time, "monotonic", fake_monotonic)

    with pytest.raises(_FakeTransient, match="slow-byte hang"):
        core_http.get_drained(
            "https://example.test/data",
            total_deadline_s=0.0,
            transient_exc=_FakeTransient,
            context="example.test",
        )


@responses.activate
def test_get_drained_closes_response_on_slow_byte_abort(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """On slow-byte abort, the underlying Response is closed before the raise."""
    responses.add(
        method=responses.GET,
        url=re.compile(r"https://example\.test/.*"),
        body=b"x" * (200 * 1024),
        status=200,
    )

    closed: list[bool] = []
    real_response_close = requests.Response.close

    def spy_close(self: requests.Response) -> None:
        closed.append(True)
        real_response_close(self)

    monkeypatch.setattr(requests.Response, "close", spy_close)

    counter = [0.0]

    def fake_monotonic() -> float:
        counter[0] += 100.0
        return counter[0]

    monkeypatch.setattr(core_http.time, "monotonic", fake_monotonic)

    with pytest.raises(_FakeTransient):
        core_http.get_drained(
            "https://example.test/data",
            total_deadline_s=0.0,
            transient_exc=_FakeTransient,
        )
    assert closed, "Response.close() should have been invoked on failure"


@responses.activate
def test_get_drained_does_not_share_default_headers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Mutating DEFAULT_HEADERS after a request must not affect subsequent requests."""
    seen_headers: list[dict[str, str]] = []

    def callback(request):  # type: ignore[no-untyped-def]
        seen_headers.append(dict(request.headers))
        return (200, {}, b"{}")

    responses.add_callback(
        method=responses.GET,
        url=re.compile(r"https://example\.test/.*"),
        callback=callback,
    )

    core_http.get_drained(
        "https://example.test/first",
        total_deadline_s=10.0,
        transient_exc=_FakeTransient,
    )
    # Sneak a mutation in — pre-D1 a shared dict would leak this into call #2.
    core_http.DEFAULT_HEADERS["X-Poisoned"] = "yes"
    try:
        core_http.get_drained(
            "https://example.test/second",
            total_deadline_s=10.0,
            transient_exc=_FakeTransient,
        )
    finally:
        del core_http.DEFAULT_HEADERS["X-Poisoned"]

    # The first call must not have seen the future mutation (obviously),
    # and the second call must include the mutated header — confirming the
    # copy is made AT CALL TIME, not at module import.
    assert "X-Poisoned" not in seen_headers[0]
    assert seen_headers[1].get("X-Poisoned") == "yes"


@responses.activate
def test_get_drained_respects_explicit_empty_headers() -> None:
    """``headers={}`` means 'send no custom headers', NOT 'fall back to defaults'.

    The sentinel for "use DEFAULT_HEADERS" is ``None``; an explicit empty dict
    must be honoured. A truthiness guard (``if headers``) would wrongly collapse
    ``{}`` into the defaults — this pins the ``is not None`` check.
    """
    seen_headers: list[dict[str, str]] = []

    def callback(request):  # type: ignore[no-untyped-def]
        seen_headers.append(dict(request.headers))
        return (200, {}, b"{}")

    responses.add_callback(
        method=responses.GET,
        url=re.compile(r"https://example\.test/.*"),
        callback=callback,
    )

    core_http.get_drained(
        "https://example.test/x",
        total_deadline_s=10.0,
        transient_exc=_FakeTransient,
        headers={},
    )
    # With the defaults bypassed, neither our custom User-Agent nor
    # Connection: close should be present (requests' own defaults apply).
    assert "embrapa-dashboard" not in seen_headers[0].get("User-Agent", "")
    assert seen_headers[0].get("Connection") != "close"


@responses.activate
def test_get_drained_default_headers_include_connection_close() -> None:
    """``Connection: close`` is part of the slow-byte abort contract."""
    seen_headers: list[dict[str, str]] = []

    def callback(request):  # type: ignore[no-untyped-def]
        seen_headers.append(dict(request.headers))
        return (200, {}, b"{}")

    responses.add_callback(
        method=responses.GET,
        url=re.compile(r"https://example\.test/.*"),
        callback=callback,
    )

    core_http.get_drained(
        "https://example.test/x",
        total_deadline_s=10.0,
        transient_exc=_FakeTransient,
    )
    assert seen_headers[0].get("Connection") == "close"
    assert "embrapa-dashboard" in seen_headers[0].get("User-Agent", "")
