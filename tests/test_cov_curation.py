"""Coverage tests for serving/curation.py — the editable commodity-catalog writer.

Targets the currently-uncovered branches: the catalog-editors ensure helper, the
ciclo_de_vida over-length + invalid-enum ValueErrors, the agrupamento /
descricao_commodity over-length ValueErrors, the ``_current_prefixes`` NotFound
fall-through, the change_id dedup short-circuits on both record + remove, and the
cache-invalidation paths.

Mirrors the fixture/mock style of tests/test_serving.py: ``pytest.importorskip``
on flask-caching, ``mock.Mock()`` recording-stub BigQuery clients, ``monkeypatch``
of ``ensure_dataset`` / ``_current_prefixes`` / ``_change_id_seen``, the IAP email
header, and the shared ``_isolated_settings`` / ``_bind_simplecache`` helpers.
"""

from __future__ import annotations

from unittest import mock

import pytest
from google.api_core.exceptions import NotFound

from embrapa_dashboard.serving import iap
from tests.test_serving import _bind_simplecache, _isolated_settings


def _settings():
    return _isolated_settings(gcp_project_id="test-project")


_HEADERS = {iap.IAP_EMAIL_HEADER: "accounts.google.com:alice@embrapa.br"}


# ── ensure_catalog_editors_table (lines 119-124) ──────────────────────────────


def test_ensure_catalog_editors_table_creates_with_explicit_schema(monkeypatch):
    pytest.importorskip("flask_caching")
    from embrapa_dashboard.serving import curation

    monkeypatch.setattr(curation, "ensure_dataset", lambda *a, **k: None)
    client = mock.Mock()
    fqn = curation.ensure_catalog_editors_table(settings=_settings(), client=client)

    assert fqn.endswith(".catalog_editors")
    table_arg = client.create_table.call_args.args[0]
    assert {f.name for f in table_arg.schema} >= {"resource", "email", "added_by", "added_at"}
    # exists_ok keeps it idempotent.
    assert client.create_table.call_args.kwargs.get("exists_ok") is True


# ── _validate_catalog_edit: ciclo_de_vida guards (lines 151, 153) ─────────────


def test_validate_catalog_edit_rejects_overlong_ciclo():
    from embrapa_dashboard.serving import curation
    from embrapa_dashboard.serving.research_inputs import MAX_STAGE_LEN

    with pytest.raises(ValueError, match="ciclo_de_vida excede"):
        curation._validate_catalog_edit("4403", "un_comtrade", "x" * (MAX_STAGE_LEN + 1))


def test_validate_catalog_edit_rejects_invalid_ciclo_enum():
    from embrapa_dashboard.serving import curation

    # A non-empty value that is not one of the two F7 ciclo-de-vida literals → reject,
    # keeping the UI dropdown + dbt visibility gate in lockstep.
    with pytest.raises(ValueError, match="inválido"):
        curation._validate_catalog_edit("4403", "un_comtrade", "Talvez disponível")


# ── _is_active_entry: NotFound fall-through (log table absent) ────────────────


def test_is_active_entry_false_when_table_absent():
    from embrapa_dashboard.serving import curation

    client = mock.Mock()
    client.query.side_effect = NotFound("table does not exist yet")
    # No log table yet → the entry can't be active → False.
    assert curation._is_active_entry(client, "proj.ds.tbl", "4403", "un_comtrade") is False


# ── record_commodity_catalog: over-length text guards (lines 241, 243) ────────


def test_record_commodity_catalog_rejects_overlong_agrupamento(monkeypatch):
    pytest.importorskip("flask_caching")
    from embrapa_dashboard.serving import curation
    from embrapa_dashboard.serving.research_inputs import MAX_NOTE_LEN

    monkeypatch.setattr(curation, "ensure_dataset", lambda *a, **k: None)
    with pytest.raises(ValueError, match="agrupamento excede"):
        curation.record_commodity_catalog(
            "4403",
            "un_comtrade",
            _HEADERS,
            agrupamento="a" * (MAX_NOTE_LEN + 1),
            settings=_settings(),
            client=mock.Mock(),
            invalidate_cache=False,
        )


def test_record_commodity_catalog_rejects_overlong_descricao(monkeypatch):
    pytest.importorskip("flask_caching")
    from embrapa_dashboard.serving import curation
    from embrapa_dashboard.serving.research_inputs import MAX_NOTE_LEN

    monkeypatch.setattr(curation, "ensure_dataset", lambda *a, **k: None)
    with pytest.raises(ValueError, match="descricao_commodity excede"):
        curation.record_commodity_catalog(
            "4403",
            "un_comtrade",
            _HEADERS,
            agrupamento="Madeira",
            descricao_commodity="d" * (MAX_NOTE_LEN + 1),
            settings=_settings(),
            client=mock.Mock(),
            invalidate_cache=False,
        )


# ── record_commodity_catalog: change_id dedup short-circuit (lines 257-260) ───


def test_record_commodity_catalog_dedupes_on_seen_change_id(monkeypatch):
    pytest.importorskip("flask_caching")
    from embrapa_dashboard.serving import curation

    monkeypatch.setattr(curation, "ensure_dataset", lambda *a, **k: None)
    monkeypatch.setattr(curation, "_assert_code_exists", lambda *a, **k: None)
    # A client-supplied change_id already present in the log → the write is a no-op.
    monkeypatch.setattr(curation, "_change_id_seen", lambda *a, **k: True)
    client = mock.Mock()
    client.query.return_value.result.return_value = []

    rec = curation.record_commodity_catalog(
        "4403",
        "un_comtrade",
        _HEADERS,
        agrupamento="Madeira",
        change_id="retry-key-1",
        settings=_settings(),
        client=client,
        invalidate_cache=False,
    )

    assert rec["deduped"] is True
    assert rec["active"] is True
    assert "code_prefix" not in rec
    assert rec["change_id"] == "retry-key-1"
    # No INSERT was issued on the dedup path — the existence gate is monkeypatched away,
    # so query() was never called for an insert.
    insert_calls = [c for c in client.query.call_args_list if "insert into" in c.args[0].lower()]
    assert insert_calls == []


# ── record_commodity_catalog: cache invalidation on save (line 291) ───────────


def test_record_commodity_catalog_invalidates_cache_on_save(monkeypatch):
    pytest.importorskip("flask_caching")
    from embrapa_dashboard.serving import curation

    monkeypatch.setattr(curation, "ensure_dataset", lambda *a, **k: None)
    monkeypatch.setattr(curation, "_assert_code_exists", lambda *a, **k: None)
    client = mock.Mock()
    client.query.return_value.result.return_value = []

    seen = {"called": False}

    def _spy():
        seen["called"] = True

    monkeypatch.setattr(curation, "invalidate_commodity_catalog_cache", _spy)

    rec = curation.record_commodity_catalog(
        "4403",
        "un_comtrade",
        _HEADERS,
        agrupamento="Madeira",
        settings=_settings(),
        client=client,
        invalidate_cache=True,
    )
    assert rec["deduped"] is False
    assert seen["called"] is True


# ── remove_commodity_catalog: change_id dedup short-circuit (line 333) ────────


def test_remove_commodity_catalog_dedupes_on_seen_change_id(monkeypatch):
    pytest.importorskip("flask_caching")
    from embrapa_dashboard.serving import curation

    monkeypatch.setattr(curation, "ensure_dataset", lambda *a, **k: None)
    monkeypatch.setattr(curation, "_change_id_seen", lambda *a, **k: True)
    client = mock.Mock()
    client.query.return_value.result.return_value = []

    rec = curation.remove_commodity_catalog(
        "4403",
        "un_comtrade",
        _HEADERS,
        change_id="retry-remove-1",
        settings=_settings(),
        client=client,
        invalidate_cache=False,
    )

    assert rec["deduped"] is True
    assert rec["active"] is False
    assert rec["change_id"] == "retry-remove-1"
    # The dedup path echoes the codigo as the prefix and never inserts a tombstone.
    insert_calls = [c for c in client.query.call_args_list if "insert into" in c.args[0].lower()]
    assert insert_calls == []


# ── remove_commodity_catalog: cache invalidation on tombstone (line 374) ──────


def test_remove_commodity_catalog_invalidates_cache_on_tombstone(monkeypatch):
    pytest.importorskip("flask_caching")
    from embrapa_dashboard.serving import curation

    monkeypatch.setattr(curation, "ensure_dataset", lambda *a, **k: None)
    monkeypatch.setattr(curation, "_is_active_entry", lambda *a, **k: True)
    client = mock.Mock()
    client.query.return_value.result.return_value = []

    seen = {"called": False}
    monkeypatch.setattr(
        curation,
        "invalidate_commodity_catalog_cache",
        lambda: seen.__setitem__("called", True),
    )

    rec = curation.remove_commodity_catalog(
        "4403",
        "un_comtrade",
        _HEADERS,
        settings=_settings(),
        client=client,
        invalidate_cache=True,
    )
    assert rec["active"] is False
    assert seen["called"] is True


# ── invalidate_commodity_catalog_cache: the real body (lines 467-468) ─────────


def test_invalidate_commodity_catalog_cache_drops_memoized():
    pytest.importorskip("flask_caching")
    from embrapa_dashboard.serving import curation

    app, _cache = _bind_simplecache()
    with app.app_context():
        # cache is bound to a live SimpleCache backend → delete_memoized succeeds,
        # exercising the happy path (not the except branch).
        curation.invalidate_commodity_catalog_cache()


def test_invalidate_commodity_catalog_cache_swallows_unbound_backend(monkeypatch):
    """When the cache is unbound / backend down, ``delete_memoized`` raises and the
    helper logs a warning instead of propagating (best-effort invalidation)."""
    pytest.importorskip("flask_caching")
    from embrapa_dashboard.serving import curation

    def _boom(*_a, **_k):
        raise RuntimeError("cache backend unbound")

    monkeypatch.setattr(curation.cache, "delete_memoized", _boom)
    # Must not raise.
    curation.invalidate_commodity_catalog_cache()
