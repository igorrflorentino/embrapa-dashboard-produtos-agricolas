"""Coverage for the first-class commodity-GROUPS registry (serving/commodity_groups.py):
create (new / duplicate), rename (re-tags the group's members), and delete (tombstone,
rejected while the group still has members). The BQ helpers are monkeypatched so the CRUD
logic is exercised without a live warehouse."""

from types import SimpleNamespace
from unittest import mock

import pytest
from google.api_core.exceptions import NotFound

from embrapa_commodities.config import Settings
from embrapa_commodities.serving import iap

pytest.importorskip("flask_caching")

_HEADERS = {iap.IAP_EMAIL_HEADER: "accounts.google.com:alice@embrapa.br"}


def _settings() -> Settings:
    return Settings(gcp_project_id="test-project")


def _patch_common(monkeypatch, cg, current):
    """Stub the table-ensure + current-groups read + insert; return the captured inserts."""
    monkeypatch.setattr(cg, "ensure_commodity_group_log_table", lambda *a, **k: "grp")
    monkeypatch.setattr(cg, "_current_groups", lambda bq, t: dict(current))
    inserted = []
    monkeypatch.setattr(
        cg,
        "_insert_group_row",
        lambda bq, t, gid, name, active, by, cid: inserted.append(
            {"gid": gid, "name": name, "active": active}
        ),
    )
    return inserted


def test_record_group_creates_new(monkeypatch):
    from embrapa_commodities.serving import commodity_groups as cg

    inserted = _patch_common(monkeypatch, cg, {})
    out = cg.record_group(
        "Madeira", _HEADERS, settings=_settings(), client=mock.Mock(), invalidate_cache=False
    )
    assert out["group_id"] == "madeira" and out["group_name"] == "Madeira"
    assert out["active"] is True and out["edited_by"] == "alice@embrapa.br"
    assert inserted == [{"gid": "madeira", "name": "Madeira", "active": True}]


def test_record_group_rejects_duplicate(monkeypatch):
    from embrapa_commodities.serving import commodity_groups as cg

    _patch_common(monkeypatch, cg, {"madeira": "Madeira"})
    with pytest.raises(ValueError):  # slug 'madeira' already active
        cg.record_group(
            "Madeira", _HEADERS, settings=_settings(), client=mock.Mock(), invalidate_cache=False
        )


def test_record_group_rejects_blank_name(monkeypatch):
    from embrapa_commodities.serving import commodity_groups as cg

    with pytest.raises(ValueError):
        cg.record_group("   ", _HEADERS, settings=_settings(), client=mock.Mock())


def test_record_group_rename_retags_members(monkeypatch):
    from embrapa_commodities.serving import commodity_groups as cg
    from embrapa_commodities.serving import curation

    inserted = _patch_common(monkeypatch, cg, {"madeira": "Madeira"})
    member = SimpleNamespace(
        codigo_commodity="4403",
        banco="comex",
        descricao_commodity=None,
        ciclo_de_vida="Fazer Ingestão e deixar disponível",
        code_prefix="4403",
    )
    monkeypatch.setattr(cg, "_active_member_rows", lambda bq, t, gid: [member])
    retagged = []

    def _capture(*a, **k):
        retagged.append((k.get("commodity_id"), k.get("agrupamento")))
        return {"ok": True}

    monkeypatch.setattr(curation, "record_commodity_catalog", _capture)
    out = cg.record_group(
        "Madeira Nova",
        _HEADERS,
        group_id="madeira",
        settings=_settings(),
        client=mock.Mock(),
        invalidate_cache=False,
    )
    assert out["group_name"] == "Madeira Nova"
    assert inserted[0]["name"] == "Madeira Nova"
    # The member was re-tagged with the new name, keeping the same group_id.
    assert retagged == [("madeira", "Madeira Nova")]


def test_record_group_rename_missing_raises(monkeypatch):
    from embrapa_commodities.serving import commodity_groups as cg

    _patch_common(monkeypatch, cg, {})
    with pytest.raises(ValueError):  # group_id doesn't exist → nothing to rename
        cg.record_group(
            "X",
            _HEADERS,
            group_id="nope",
            settings=_settings(),
            client=mock.Mock(),
            invalidate_cache=False,
        )


def test_delete_group_rejects_with_members(monkeypatch):
    from embrapa_commodities.serving import commodity_groups as cg

    _patch_common(monkeypatch, cg, {"madeira": "Madeira"})
    monkeypatch.setattr(
        cg, "_active_member_rows", lambda bq, t, gid: [SimpleNamespace(codigo_commodity="4403")]
    )
    with pytest.raises(ValueError):  # non-empty → must reassign/remove members first
        cg.delete_group(
            "madeira", _HEADERS, settings=_settings(), client=mock.Mock(), invalidate_cache=False
        )


def test_delete_group_tombstones_when_empty(monkeypatch):
    from embrapa_commodities.serving import commodity_groups as cg

    inserted = _patch_common(monkeypatch, cg, {"madeira": "Madeira"})
    monkeypatch.setattr(cg, "_active_member_rows", lambda bq, t, gid: [])
    out = cg.delete_group(
        "madeira", _HEADERS, settings=_settings(), client=mock.Mock(), invalidate_cache=False
    )
    assert out["active"] is False and out["group_id"] == "madeira"
    assert inserted == [{"gid": "madeira", "name": "Madeira", "active": False}]


def test_delete_group_missing_raises(monkeypatch):
    from embrapa_commodities.serving import commodity_groups as cg

    _patch_common(monkeypatch, cg, {})
    with pytest.raises(ValueError):
        cg.delete_group(
            "nope", _HEADERS, settings=_settings(), client=mock.Mock(), invalidate_cache=False
        )


# ── Full-path tests that exercise the REAL BQ-query helpers via a mock client ──────


def _q(rows):
    """A mock query job whose .result() yields ``rows``."""
    job = mock.Mock()
    job.result.return_value = rows
    return job


def test_ensure_group_log_table_creates_with_schema(monkeypatch):
    from embrapa_commodities.serving import commodity_groups as cg

    monkeypatch.setattr(cg, "ensure_dataset", lambda *a, **k: None)
    client = mock.Mock()
    fqn = cg.ensure_commodity_group_log_table(settings=_settings(), client=client)
    assert fqn.endswith("commodity_group_log")
    tbl = client.create_table.call_args.args[0]
    assert [f.name for f in tbl.schema] == [
        "group_id",
        "group_name",
        "active",
        "edited_by",
        "edited_at",
        "change_id",
    ]
    assert tbl.clustering_fields == ["group_id"]


def test_record_group_create_runs_real_helpers(monkeypatch):
    from embrapa_commodities.serving import commodity_groups as cg

    monkeypatch.setattr(cg, "ensure_dataset", lambda *a, **k: None)
    client = mock.Mock()
    client.query.return_value.result.return_value = []  # _current_groups empty, then INSERT
    # invalidate_cache=True also exercises invalidate_group_cache (cache unbound → caught).
    out = cg.record_group("Madeira", _HEADERS, settings=_settings(), client=client)
    assert out["group_id"] == "madeira" and out["active"] is True
    sql = client.query.call_args.args[0].lower()  # the LAST call = the INSERT
    assert "insert into" in sql and "current_timestamp()" in sql


def test_record_group_dedupes_supplied_change_id(monkeypatch):
    from embrapa_commodities.serving import commodity_groups as cg

    monkeypatch.setattr(cg, "ensure_dataset", lambda *a, **k: None)
    monkeypatch.setattr(cg, "_change_id_seen", lambda *a, **k: True)
    client = mock.Mock()
    client.query.return_value.result.return_value = []  # _current_groups empty
    out = cg.record_group(
        "Madeira",
        _HEADERS,
        change_id="k1",
        settings=_settings(),
        client=client,
        invalidate_cache=False,
    )
    assert out["deduped"] is True


def test_record_group_rename_runs_real_member_read(monkeypatch):
    from embrapa_commodities.serving import commodity_groups as cg
    from embrapa_commodities.serving import curation

    monkeypatch.setattr(cg, "ensure_dataset", lambda *a, **k: None)
    grp = SimpleNamespace(group_id="madeira", group_name="Madeira")
    member = SimpleNamespace(
        codigo_commodity="4403",
        banco="comex",
        descricao_commodity=None,
        ciclo_de_vida="Fazer Ingestão e deixar disponível",
        code_prefix="4403",
    )
    client = mock.Mock()
    # 1) _current_groups → the group; 2) INSERT rename row; 3) _active_member_rows → member.
    client.query.side_effect = [_q([grp]), _q([]), _q([member])]
    retagged = []
    monkeypatch.setattr(
        curation, "record_commodity_catalog", lambda *a, **k: retagged.append(k.get("agrupamento"))
    )
    out = cg.record_group(
        "Madeira Nova",
        _HEADERS,
        group_id="madeira",
        settings=_settings(),
        client=client,
        invalidate_cache=False,
    )
    assert out["group_name"] == "Madeira Nova"
    assert retagged == ["Madeira Nova"]


def test_delete_group_empty_runs_real_helpers(monkeypatch):
    from embrapa_commodities.serving import commodity_groups as cg

    monkeypatch.setattr(cg, "ensure_dataset", lambda *a, **k: None)
    grp = SimpleNamespace(group_id="madeira", group_name="Madeira")
    client = mock.Mock()
    # 1) _current_groups → group; 2) _active_member_rows → empty; 3) INSERT tombstone.
    client.query.side_effect = [_q([grp]), _q([]), _q([])]
    out = cg.delete_group("madeira", _HEADERS, settings=_settings(), client=client)
    assert out["active"] is False
    sql = client.query.call_args.args[0].lower()
    assert "insert into" in sql


def test_current_groups_and_members_empty_on_not_found():
    from embrapa_commodities.serving import commodity_groups as cg

    client = mock.Mock()
    client.query.side_effect = NotFound("absent")
    assert cg._current_groups(client, "t") == {}
    assert cg._active_member_rows(client, "t", "madeira") == []


def test_record_group_rejects_unsluggable_name(monkeypatch):
    from embrapa_commodities.serving import commodity_groups as cg

    _patch_common(monkeypatch, cg, {})
    with pytest.raises(ValueError):  # '###' slugs to '' → cannot mint a group_id
        cg.record_group(
            "###", _HEADERS, settings=_settings(), client=mock.Mock(), invalidate_cache=False
        )
