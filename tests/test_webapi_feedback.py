"""Tests for the user-feedback channel: the serving writer + the /api/feedback route."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from embrapa_commodities.config import Settings
from embrapa_commodities.serving import feedback as fb
from embrapa_commodities.serving.feedback import FeedbackValidationError, record_feedback


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
    from embrapa_commodities.webapi import app as app_mod
    from embrapa_commodities.webapi import auth, routes

    cfg = _cfg(curation_dev_author=dev_author)
    monkeypatch.setattr(auth, "get_settings", lambda: cfg)
    monkeypatch.setattr(routes, "get_settings", lambda: cfg)
    monkeypatch.setattr(fb, "get_settings", lambda: cfg)
    if record is not None:
        monkeypatch.setattr(routes, "record_feedback", record)
    app = app_mod.create_app()
    app.config.update(TESTING=True)
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
