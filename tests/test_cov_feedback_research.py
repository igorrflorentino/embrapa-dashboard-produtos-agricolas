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
    with pytest.raises(FeedbackValidationError, match="exceeds"):
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


# ── research_inputs.py:64 — _bq_client ───────────────────────────────────────────


def test_bq_client_delegates_to_resolve_bq_client(monkeypatch):
    """_bq_client is a thin wrapper over resolve_bq_client(settings)."""
    from embrapa_dashboard.serving import research_inputs as ri

    resolved = mock.Mock()
    monkeypatch.setattr(ri, "resolve_bq_client", lambda settings: resolved)

    assert ri._bq_client(_cfg()) is resolved


def test_ensure_curators_table_resolves_client_via_bq_client(monkeypatch):
    """With no explicit client, ensure_curators_table goes through _bq_client (line 64)."""
    from embrapa_dashboard.serving import research_inputs as ri

    resolved = mock.Mock()
    monkeypatch.setattr(ri, "resolve_bq_client", lambda settings: resolved)
    monkeypatch.setattr(ri, "ensure_dataset", lambda *a, **k: None)

    fqn = ri.ensure_curators_table(settings=_cfg())

    assert fqn.endswith(".curators")
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
