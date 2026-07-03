"""Tests for the user-feedback channel: the serving writer + the /api/feedback route."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from embrapa_dashboard.config import Settings
from embrapa_dashboard.serving import feedback as fb
from embrapa_dashboard.serving.feedback import FeedbackValidationError, record_feedback


def _cfg(**over):
    base = {
        "gcp_project_id": "test-project",
        "iap_audience": None,
        "curation_dev_author": None,
        "feedback_github_repo": None,
        "feedback_github_token": None,
    }
    base.update(over)
    return Settings(_env_file=None, **base)  # type: ignore[arg-type]


# ── writer (serving/feedback.py) ────────────────────────────────────────────────


def test_record_feedback_empty_message_rejected():
    """Validation runs before any identity/BigQuery work — an empty message 400s."""
    with pytest.raises(FeedbackValidationError):
        record_feedback(category="bug", message="   ", headers={})


def test_record_feedback_bad_category_rejected():
    with pytest.raises(FeedbackValidationError):
        record_feedback(
            category="spam",
            message="algo",
            headers={"X-Goog-Authenticated-User-Email": "u@embrapa.br"},
        )


def test_record_feedback_writes_row_and_captures_iap_author(monkeypatch):
    """Happy path: parameterized INSERT issued; author from the IAP header; GitHub
    not configured → issue_url None. BigQuery is a MagicMock (no network)."""
    monkeypatch.setattr(
        fb, "ensure_feedback_log_table", lambda cfg, bq: "t.research_inputs.feedback_log"
    )
    client = MagicMock()
    row = record_feedback(
        category="bug",
        message="O gráfico de valor está estranho",
        headers={"X-Goog-Authenticated-User-Email": "user@embrapa.br"},
        url="https://app/?v=value&b=ibge_pevs",
        view="value",
        banco="ibge_pevs",
        app_version="0.1.0",
        settings=_cfg(),
        client=client,
    )
    assert row["submitted_by"] == "user@embrapa.br"
    assert row["category"] == "bug"
    assert row["view"] == "value"
    assert row["issue_url"] is None
    assert row["feedback_id"]
    client.query.assert_called_once()


def test_forward_to_github_is_noop_without_config():
    """No repo/token configured → the forward is skipped (no requests import)."""
    assert (
        fb._forward_to_github(
            _cfg(),
            category="bug",
            message="x",
            submitted_by="u@embrapa.br",
            url=None,
            view_id=None,
            banco=None,
        )
        is None
    )


# ── route (/api/feedback) ───────────────────────────────────────────────────────


def _client(monkeypatch, *, dev_author="dev@embrapa.br", record=None):
    pytest.importorskip("flask")
    pytest.importorskip("flask_caching")
    from embrapa_dashboard.serving.cache import init_cache
    from embrapa_dashboard.webapi import app as app_mod
    from embrapa_dashboard.webapi import auth, routes

    cfg = _cfg(curation_dev_author=dev_author)
    monkeypatch.setattr(auth, "get_settings", lambda: cfg)
    monkeypatch.setattr(routes, "get_settings", lambda: cfg)
    monkeypatch.setattr(fb, "get_settings", lambda: cfg)
    if record is not None:
        monkeypatch.setattr(routes, "record_feedback", record)
    app = app_mod.create_app()
    app.config.update(TESTING=True)
    # create_app() boots a no-op NullCache when no .env / GCP_PROJECT_ID is present
    # (e.g. CI), which would make the cache-backed SEC-2 cooldown a silent no-op and
    # fail test_feedback_route_cooldown_returns_429. Rebind a real in-memory cache
    # from the test settings (cfg.cache_type defaults to SimpleCache) so the cooldown
    # is exercised deterministically, independent of the ambient environment.
    init_cache(app, settings=cfg)
    return app.test_client()


def test_feedback_route_success_echoes_row(monkeypatch):
    captured = {}

    def _fake_record(**kw):
        captured.update(kw)
        return {"feedback_id": "abc", "category": kw["category"], "submitted_by": "dev@embrapa.br"}

    client = _client(monkeypatch, record=_fake_record)
    resp = client.post(
        "/api/feedback", json={"category": "sugestao", "message": "Adicionem export"}
    )
    assert resp.status_code == 200
    assert resp.get_json()["submitted_by"] == "dev@embrapa.br"
    assert captured["category"] == "sugestao"
    assert captured["message"] == "Adicionem export"


def test_feedback_route_empty_message_is_400(monkeypatch):
    """The real writer validates before any write → the route maps it to 400."""
    client = _client(monkeypatch)
    resp = client.post("/api/feedback", json={"message": "   "})
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_feedback_route_without_identity_is_401(monkeypatch):
    """No IAP header + no dev fallback → MissingAuthorError → 401 (never writes)."""
    client = _client(monkeypatch, dev_author=None)
    resp = client.post("/api/feedback", json={"message": "mensagem válida"})
    assert resp.status_code == 401


def test_feedback_route_cooldown_returns_429(monkeypatch):
    """SEC-2: a rapid second submit from the same author is throttled (429)."""
    client = _client(monkeypatch, record=lambda **kw: {"feedback_id": "a", "category": "bug"})
    first = client.post("/api/feedback", json={"message": "primeiro"})
    second = client.post("/api/feedback", json={"message": "segundo"})
    assert first.status_code == 200
    assert second.status_code == 429


# ── GitHub forward: success path + sanitisation (audit TEST-1 + SEC-1 + FB-1) ────


class _FakeResp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def test_forward_to_github_creates_issue_and_returns_url(monkeypatch):
    """The success path: a configured token POSTs an issue and the html_url is returned."""
    import requests

    captured = {}

    def _fake_post(url, **kw):
        captured["url"] = url
        captured["json"] = kw.get("json")
        captured["headers"] = kw.get("headers")
        return _FakeResp({"html_url": "https://github.com/o/r/issues/7"})

    monkeypatch.setattr(requests, "post", _fake_post)
    url = fb._forward_to_github(
        _cfg(feedback_github_repo="o/r", feedback_github_token="t"),
        category="bug",
        message="o gráfico quebrou",
        submitted_by="u@embrapa.br",
        url="https://app/?v=value",
        view_id="value",
        banco="ibge_pevs",
    )
    assert url == "https://github.com/o/r/issues/7"
    assert captured["url"].endswith("/repos/o/r/issues")
    assert captured["json"]["labels"] == ["feedback", "bug"]
    assert captured["headers"]["Authorization"] == "Bearer t"


def test_forward_to_github_swallows_errors(monkeypatch):
    """A GitHub failure is logged and swallowed → None (never raised)."""
    import requests

    def _boom(*a, **k):
        raise requests.RequestException("502")

    monkeypatch.setattr(requests, "post", _boom)
    assert (
        fb._forward_to_github(
            _cfg(feedback_github_repo="o/r", feedback_github_token="t"),
            category="bug",
            message="x",
            submitted_by="u@e.br",
            url=None,
            view_id=None,
            banco=None,
        )
        is None
    )


def test_forward_to_github_fences_user_message(monkeypatch):
    """SEC-1: the user message is fenced, and triple-backtick breakout runs are neutralised."""
    import requests

    seen = {}

    def _fake_post(url, **kw):
        seen["body"] = kw["json"]["body"]
        return _FakeResp({"html_url": "https://x/1"})

    monkeypatch.setattr(requests, "post", _fake_post)
    fb._forward_to_github(
        _cfg(feedback_github_repo="o/r", feedback_github_token="t"),
        category="bug",
        message="oi ```rm -rf``` @maintainer",
        submitted_by="u@e.br",
        url=None,
        view_id=None,
        banco=None,
    )
    assert "```text" in seen["body"]  # the message is inside a code fence
    assert "```rm -rf```" not in seen["body"]  # the breakout fence was neutralised


def test_record_feedback_writes_then_stamps_issue_url(monkeypatch):
    """FB-1: with GitHub configured, the row is INSERTed first then UPDATEd with the
    issue_url — two DML calls (durable write before the forward)."""
    monkeypatch.setattr(fb, "ensure_feedback_log_table", lambda cfg, bq: "t.r.feedback_log")
    monkeypatch.setattr(fb, "_forward_to_github", lambda *a, **k: "https://x/9")
    client = MagicMock()
    row = record_feedback(
        category="bug",
        message="msg",
        headers={"X-Goog-Authenticated-User-Email": "u@embrapa.br"},
        settings=_cfg(feedback_github_repo="o/r", feedback_github_token="t"),
        client=client,
    )
    assert row["issue_url"] == "https://x/9"
    assert client.query.call_count == 2  # INSERT, then UPDATE issue_url
