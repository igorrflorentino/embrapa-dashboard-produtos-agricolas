"""Coverage tests for serving/feedback.py + serving/research_inputs.py.

Targets the currently-uncovered branches:
  * feedback.py:78         — over-length message rejected (FeedbackValidationError)
  * feedback.py:89-97      — ensure_feedback_log_table creates the dataset + table
  * feedback.py:245-246    — issue_url UPDATE fails → logged & swallowed (best-effort)
  * research_inputs.py:64        — _bq_client resolves a client when none is passed
  * research_inputs.py:103-108   — ensure_banco_metadata_table creates the override table

Reuses the codebase's mock/fixture patterns (mock.Mock() recording clients, the
``ensure_dataset`` monkeypatch self-heal stub) and the hermetic Settings helpers.
"""

from __future__ import annotations

from unittest import mock

import pytest

from embrapa_dashboard.serving import feedback as fb
from embrapa_dashboard.serving.feedback import FeedbackValidationError, record_feedback
from tests.test_serving import _isolated_settings


def _cfg(**over):
    over.setdefault("gcp_project_id", "test-project")
    return _isolated_settings(**over)


# ── feedback.py:78 — over-length message rejected ────────────────────────────────


def test_record_feedback_over_length_message_rejected():
    """A message longer than MAX_MESSAGE_LEN is rejected before any write (→ 400)."""
    too_long = "a" * (fb.MAX_MESSAGE_LEN + 1)
    with pytest.raises(FeedbackValidationError, match="excede"):
        record_feedback(
            category="bug",
            message=too_long,
            headers={"X-Goog-Authenticated-User-Email": "u@embrapa.br"},
        )


# ── feedback.py:89-97 — ensure_feedback_log_table body ───────────────────────────


def test_ensure_feedback_log_table_creates_table_with_schema(monkeypatch):
    """The auto-heal helper creates the dataset + a category-clustered table with
    the explicit FEEDBACK_LOG_SCHEMA, returns its FQN, and uses exists_ok=True."""
    seen = {}

    def _fake_ensure_dataset(bq, dataset, location):
        seen["dataset"] = dataset

    monkeypatch.setattr(fb, "ensure_dataset", _fake_ensure_dataset)
    client = mock.Mock()
    cfg = _cfg()

    fqn = fb.ensure_feedback_log_table(settings=cfg, client=client)

    assert fqn.endswith(".feedback_log")
    assert seen["dataset"] == f"{cfg.gcp_project_id}.{cfg.bq_research_inputs_dataset}"
    table_arg = client.create_table.call_args.args[0]
    assert table_arg.clustering_fields == ["category"]
    assert {f.name for f in table_arg.schema} == {f.name for f in fb.FEEDBACK_LOG_SCHEMA}
    assert client.create_table.call_args.kwargs["exists_ok"] is True


def test_ensure_feedback_log_table_resolves_client_when_none(monkeypatch):
    """When no client is passed, the helper resolves one via resolve_bq_client."""
    resolved = mock.Mock()
    monkeypatch.setattr(fb, "resolve_bq_client", lambda cfg: resolved)
    monkeypatch.setattr(fb, "ensure_dataset", lambda *a, **k: None)

    fb.ensure_feedback_log_table(settings=_cfg())

    resolved.create_table.assert_called_once()


# ── feedback.py:245-246 — issue_url stamp failure swallowed ──────────────────────


def test_record_feedback_issue_url_stamp_failure_is_swallowed(monkeypatch):
    """FB-1 best-effort: the issue exists but the issue_url UPDATE blows up — the
    failure is logged and swallowed, and record_feedback still returns the row
    (issue_url populated from the successful forward)."""
    monkeypatch.setattr(fb, "ensure_feedback_log_table", lambda cfg, bq: "t.r.feedback_log")
    monkeypatch.setattr(fb, "_forward_to_github", lambda *a, **k: "https://x/42")

    client = mock.Mock()
    # First query (INSERT) succeeds; second query (the issue_url UPDATE) raises.
    client.query.side_effect = [mock.Mock(), RuntimeError("update failed")]

    row = record_feedback(
        category="bug",
        message="msg",
        headers={"X-Goog-Authenticated-User-Email": "u@embrapa.br"},
        settings=_cfg(feedback_github_repo="o/r", feedback_github_token="t"),
        client=client,
    )

    # The forward succeeded so issue_url is still surfaced even though the stamp failed.
    assert row["issue_url"] == "https://x/42"
    assert client.query.call_count == 2  # INSERT, then the failing UPDATE


def test_record_feedback_dedupes_on_change_id(monkeypatch):
    """A retried submit reusing the SAME change_id echoes the STORED row — no second BigQuery
    INSERT and no second GitHub issue (idempotency: a timeout-then-retry can't duplicate)."""
    monkeypatch.setattr(fb, "ensure_feedback_log_table", lambda cfg, bq: "t.r.feedback_log")
    stored = {
        "feedback_id": "k1",
        "category": "bug",
        "message": "msg",
        "url": None,
        "view": None,
        "banco": None,
        "submitted_by": "u@embrapa.br",
        "issue_url": "https://x/1",
        "deduped": True,
    }
    monkeypatch.setattr(fb, "_stored_feedback", lambda bq, t, fid: stored if fid == "k1" else None)
    forwarded = []
    monkeypatch.setattr(fb, "_forward_to_github", lambda *a, **k: forwarded.append(1))

    client = mock.Mock()
    row = record_feedback(
        category="bug",
        message="msg",
        headers={"X-Goog-Authenticated-User-Email": "u@embrapa.br"},
        change_id="k1",
        settings=_cfg(),
        client=client,
    )

    assert row["deduped"] is True and row["feedback_id"] == "k1"
    assert client.query.call_count == 0  # no INSERT — the stored row is echoed
    assert forwarded == []  # no second GitHub issue


# ── research_inputs.py:64 — _bq_client ───────────────────────────────────────────


def test_bq_client_delegates_to_resolve_bq_client(monkeypatch):
    """_bq_client is a thin wrapper over resolve_bq_client(settings)."""
    from embrapa_dashboard.serving import research_inputs as ri

    resolved = mock.Mock()
    monkeypatch.setattr(ri, "resolve_bq_client", lambda settings: resolved)

    assert ri._bq_client(_cfg()) is resolved


def test_ensure_attribute_editors_table_resolves_client_via_bq_client(monkeypatch):
    """With no explicit client, ensure_attribute_editors_table goes through _bq_client (line 64)."""
    from embrapa_dashboard.serving import research_inputs as ri

    resolved = mock.Mock()
    monkeypatch.setattr(ri, "resolve_bq_client", lambda settings: resolved)
    monkeypatch.setattr(ri, "ensure_dataset", lambda *a, **k: None)

    fqn = ri.ensure_attribute_editors_table(settings=_cfg())

    assert fqn.endswith(".attribute_editors")
    resolved.create_table.assert_called_once()


# ── research_inputs.py:103-108 — ensure_banco_metadata_table body ────────────────


def test_ensure_banco_metadata_table_creates_with_explicit_schema(monkeypatch):
    """The operator-editable override table is auto-created with the explicit
    BANCO_METADATA_SCHEMA (never autodetected) and exists_ok=True."""
    from embrapa_dashboard.serving import research_inputs as ri

    seen = {}

    def _fake_ensure_dataset(bq, dataset, location):
        seen["dataset"] = dataset

    monkeypatch.setattr(ri, "ensure_dataset", _fake_ensure_dataset)
    client = mock.Mock()
    cfg = _cfg()

    fqn = ri.ensure_banco_metadata_table(settings=cfg, client=client)

    assert fqn.endswith(".banco_metadata")
    assert seen["dataset"] == f"{cfg.gcp_project_id}.{cfg.bq_research_inputs_dataset}"
    table_arg = client.create_table.call_args.args[0]
    assert {f.name for f in table_arg.schema} == {f.name for f in ri.BANCO_METADATA_SCHEMA}
    assert "banco_id" in {f.name for f in table_arg.schema}
    assert client.create_table.call_args.kwargs["exists_ok"] is True


def test_ensure_banco_metadata_table_resolves_client_when_none(monkeypatch):
    """No client passed → resolved through _bq_client/resolve_bq_client."""
    from embrapa_dashboard.serving import research_inputs as ri

    resolved = mock.Mock()
    monkeypatch.setattr(ri, "resolve_bq_client", lambda settings: resolved)
    monkeypatch.setattr(ri, "ensure_dataset", lambda *a, **k: None)

    fb_fqn = ri.ensure_banco_metadata_table(settings=_cfg())

    assert fb_fqn.endswith(".banco_metadata")
    resolved.create_table.assert_called_once()


def test_stored_feedback_echoes_row_and_none_when_absent():
    """_stored_feedback maps a persisted row to the echo dict (view_id → view, deduped=True),
    and returns None when the key isn't found."""
    row = {
        "feedback_id": "k1",
        "category": "bug",
        "message": "m",
        "url": None,
        "view_id": "overview",
        "banco": "ibge_pevs",
        "submitted_by": "u@embrapa.br",
        "issue_url": "https://x/1",
    }
    client = mock.Mock()
    client.query.return_value.result.return_value = [row]
    out = fb._stored_feedback(client, "t.r.feedback_log", "k1")
    assert out["feedback_id"] == "k1" and out["view"] == "overview"
    assert out["issue_url"] == "https://x/1" and out["deduped"] is True

    client.query.return_value.result.return_value = []
    assert fb._stored_feedback(client, "t.r.feedback_log", "absent") is None


# ── ensure_no_change_id_conflict: the shared idempotency-replay guard ──────────


def test_ensure_no_change_id_conflict_noop_when_stored_none():
    """A vanished stored row (None) is not a conflict — the caller then echoes the request."""
    from embrapa_dashboard.serving.research_inputs import ensure_no_change_id_conflict

    ensure_no_change_id_conflict(None, {"codigo_produto": "1"}, ("codigo_produto",), entity="x")


def test_ensure_no_change_id_conflict_noop_when_key_matches():
    """Same natural key (differing only on a mutable attribute) is a benign no-op."""
    from embrapa_dashboard.serving.research_inputs import ensure_no_change_id_conflict

    stored = {"codigo_produto": "1", "banco": "pevs", "active": True, "agrupamento": "A"}
    incoming = {"codigo_produto": "1", "banco": "pevs", "active": True, "agrupamento": "B"}
    ensure_no_change_id_conflict(
        stored, incoming, ("codigo_produto", "banco", "active"), entity="x"
    )


def test_ensure_no_change_id_conflict_raises_on_key_mismatch():
    """A differing natural-key field → ChangeIdConflictError with a pt-BR, entity-named reason."""
    from embrapa_dashboard.serving.research_inputs import (
        ChangeIdConflictError,
        ensure_no_change_id_conflict,
    )

    stored = {"codigo_produto": "1", "banco": "pevs", "active": True}
    incoming = {"codigo_produto": "2", "banco": "pevs", "active": True}
    with pytest.raises(ChangeIdConflictError, match="produto"):
        ensure_no_change_id_conflict(
            stored, incoming, ("codigo_produto", "banco", "active"), entity="produto"
        )


# ── change_id length caps (C9a — a client idempotency key is otherwise unbounded) ──


def test_resolve_change_id_rejects_overlong_key():
    """_resolve_change_id caps a client-supplied change_id (all catalog/agrupamento writers
    plumb through it); a normal key and an absent one still pass."""
    from embrapa_dashboard.serving.research_inputs import MAX_CHANGE_ID_LEN, _resolve_change_id

    with pytest.raises(ValueError, match="change_id"):
        _resolve_change_id("x" * (MAX_CHANGE_ID_LEN + 1))
    assert _resolve_change_id("k1") == ("k1", True)
    assert _resolve_change_id(None)[1] is False


def test_record_feedback_rejects_overlong_change_id():
    """The feedback change_id doubles as the stored feedback_id — capped before any write."""
    from embrapa_dashboard.serving.feedback import MAX_CHANGE_ID_LEN

    with pytest.raises(FeedbackValidationError, match="change_id"):
        record_feedback(
            category="bug",
            message="m",
            headers={"X-Goog-Authenticated-User-Email": "u@embrapa.br"},
            change_id="x" * (MAX_CHANGE_ID_LEN + 1),
            settings=_cfg(),
        )
