"""Tests for the dashboard's cause-inference heuristic.

Covers the data-driven ``_CAUSE_PATTERNS`` dispatch introduced when the
audit refactored ``_check_cause`` from a CC-12 string-dispatch chain into
a list of ``(checker, message)`` callable pairs.
"""

from __future__ import annotations

import pytest

from embrapa_commodities.dashboard.errors import (
    _FALLBACK_CAUSE,
    infer_cause,
)

# ── Synthetic exceptions ─────────────────────────────────────────────────


class _FakeNotFound(Exception):
    """Mimics ``google.cloud.exceptions.NotFound`` shape (class-name match)."""


class _FakeForbidden(Exception):
    """Mimics ``google.cloud.exceptions.Forbidden``."""


class _FakeBadRequest(Exception):
    """Mimics ``google.api_core.exceptions.BadRequest``."""


def _fake_google_exception(module: str = "google.api_core.exceptions") -> Exception:
    """Build an exception whose ``__module__`` is rooted under google.*.

    Used to test the ``_is_google_api_error`` matcher without depending on
    google-cloud-bigquery types at import time.
    """

    class _GoogleAPIError(Exception):
        pass

    _GoogleAPIError.__module__ = module
    return _GoogleAPIError("simulated google api failure")


# ── _is_notfound_or_404 ──────────────────────────────────────────────────


def test_infer_cause_matches_notfound_by_class_name() -> None:
    assert "não encontrada" in infer_cause(_FakeNotFound("table missing")).lower()


def test_infer_cause_matches_404_substring_in_message() -> None:
    # Plain Exception, but message contains "404" — must still match.
    assert "não encontrada" in infer_cause(Exception("HTTP 404 returned")).lower()


# ── _is_forbidden_or_403 ─────────────────────────────────────────────────


def test_infer_cause_matches_forbidden_by_class_name() -> None:
    assert "permissão" in infer_cause(_FakeForbidden("denied")).lower()


@pytest.mark.parametrize(
    "msg",
    ["403 Forbidden", "permission denied", "Access permission missing"],
)
def test_infer_cause_matches_forbidden_via_message(msg: str) -> None:
    assert "permissão" in infer_cause(Exception(msg)).lower()


# ── _is_badrequest_or_400 ────────────────────────────────────────────────


def test_infer_cause_matches_badrequest_by_class_name() -> None:
    assert "rejeitou" in infer_cause(_FakeBadRequest("schema mismatch")).lower()


def test_infer_cause_matches_400_substring_in_message() -> None:
    assert "rejeitou" in infer_cause(Exception("HTTP 400 invalid query")).lower()


# ── _is_key_or_attribute_error ───────────────────────────────────────────


def test_infer_cause_matches_keyerror() -> None:
    assert "DataFrame" in infer_cause(KeyError("missing_column"))


def test_infer_cause_matches_attributeerror() -> None:
    assert "DataFrame" in infer_cause(AttributeError("no such attr"))


def test_infer_cause_does_not_match_subclasses_of_keyerror() -> None:
    """Original semantics: ``type(exc).__name__ in {...}`` excludes subclasses."""

    class CustomKeyError(KeyError):
        pass

    # Should NOT match the key/attribute pattern — falls through to fallback
    # (or another pattern if the message matches). With an empty-ish message,
    # we expect fallback.
    assert infer_cause(CustomKeyError("")) == _FALLBACK_CAUSE


# ── _is_google_api_error ─────────────────────────────────────────────────


def test_infer_cause_matches_google_api_core_module() -> None:
    result = infer_cause(_fake_google_exception("google.api_core.exceptions"))
    assert "credenciais" in result.lower()


def test_infer_cause_matches_google_auth_module() -> None:
    result = infer_cause(_fake_google_exception("google.auth.exceptions"))
    assert "credenciais" in result.lower()


def test_infer_cause_does_not_match_unrelated_module() -> None:
    exc = _fake_google_exception("some.other.module")
    # No 404/403/400/KeyError/network match either → fallback.
    assert infer_cause(exc) == _FALLBACK_CAUSE


# ── _is_network_error ────────────────────────────────────────────────────


def test_infer_cause_matches_connection_error() -> None:
    assert "rede" in infer_cause(ConnectionError("refused")).lower()


def test_infer_cause_matches_timeout_error() -> None:
    assert "rede" in infer_cause(TimeoutError("read timed out")).lower()


# ── Fallback ─────────────────────────────────────────────────────────────


def test_infer_cause_falls_back_for_unknown_exception() -> None:
    assert infer_cause(Exception("totally unique error")) == _FALLBACK_CAUSE


def test_infer_cause_falls_back_for_runtime_error_with_clean_message() -> None:
    assert infer_cause(RuntimeError("oops")) == _FALLBACK_CAUSE


# ── Ordering: first match wins ───────────────────────────────────────────


def test_infer_cause_returns_first_matching_pattern_when_multiple_apply() -> None:
    """A NotFound-named exception that ALSO contains '403' in its message
    must hit the NotFound pattern first because _is_notfound_or_404 sits
    earlier in _CAUSE_PATTERNS than _is_forbidden_or_403."""
    exc = _FakeNotFound("403 also appears here")
    result = infer_cause(exc)
    assert "não encontrada" in result.lower()
    assert "permissão" not in result.lower()
