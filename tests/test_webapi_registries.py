"""Unit tests for ``webapi/registries.py`` — the banco/view/filter reference data
and its pure lookup helpers.

The registry is Python reference/parity data for the seam (the frontend
``ui/{bancos,views,filtersSchema}.js`` copies are authoritative for what the UI
renders). The helpers are trivial dict lookups over static data — low risk, but
they encode real contracts: a view's capability gate (``view_applies_to`` /
``bancos_supporting``), the per-banco currency, and the safe PEVS fallbacks. These
tests pin those branches AND the cross-structure parity (every ``provides`` /
``requires`` capability is a declared ``CAPABILITY``; every ``FILTER_SCHEMAS`` table
matches its ``Banco.table``) so a typo'd capability or a drifted schema table fails
here rather than silently disabling a perspective in production.
"""

from __future__ import annotations

import pytest

from embrapa_commodities.webapi import registries as reg

# ── banco_by_id / visible_bancos / canon_currency_for ─────────────────────────


def test_banco_by_id_resolves_a_known_banco():
    b = reg.banco_by_id("mdic_comex")
    assert b.id == "mdic_comex"
    assert b.table == "gold_comex_flows"


def test_banco_by_id_falls_back_to_pevs_for_an_unknown_id():
    # The fallback is BANCOS[0] (PEVS) — a missing banco never returns None, so the
    # seam always has a valid banco to read capabilities/columns from.
    assert reg.banco_by_id("does_not_exist").id == reg.BANCOS[0].id == "ibge_pevs"


def test_visible_bancos_returns_only_visible_entries():
    visible = reg.visible_bancos()
    assert all(b.visible for b in visible)
    # All five shipped bancos are visible today (no banco is backend-hidden).
    assert {b.id for b in visible} == {b.id for b in reg.BANCOS if b.visible}
    assert len(visible) == 5


@pytest.mark.parametrize(
    ("banco_id", "expected"),
    [
        ("ibge_pevs", "BRL"),
        ("mdic_comex", "USD"),
        ("un_comtrade", "USD"),
        ("ibge_pam", "BRL"),
        ("does_not_exist", "BRL"),  # unknown → PEVS fallback → BRL
    ],
)
def test_canon_currency_for(banco_id, expected):
    assert reg.canon_currency_for(banco_id) == expected


# ── view_by_id / view_label / is_view_live ────────────────────────────────────


def test_view_by_id_attaches_group_context():
    v = reg.view_by_id("overview")
    assert v is not None
    assert v.id == "overview"
    # VIEW_BY_ID rebuilds each View with its group id/label attached.
    assert v.group_id == "aggregate"
    assert v.group_label == "Análise agregada"


def test_view_by_id_unknown_is_none():
    assert reg.view_by_id("no_such_view") is None


def test_view_label_known_and_fallback():
    assert reg.view_label("overview") == "Visão geral"
    # An unknown view echoes the id rather than crashing — keeps the UI labelable.
    assert reg.view_label("no_such_view") == "no_such_view"


def test_is_view_live():
    assert reg.is_view_live("overview") is True
    # Unknown view is not live (the bool guards `v and v.status == 'live'`).
    assert reg.is_view_live("no_such_view") is False


# ── view_applies_to (the capability gate) ─────────────────────────────────────


def test_view_with_no_requirements_applies_to_any_banco():
    applies, missing = reg.view_applies_to("overview", "ibge_pevs")
    assert applies is True
    assert missing == []


def test_unknown_view_applies_by_default():
    # An unrecognised view is treated as universally applicable (no gate to fail).
    assert reg.view_applies_to("no_such_view", "ibge_pevs") == (True, [])


def test_cross_banco_view_always_applies():
    # Cross-source perspectives operate across bancos → apply regardless of one
    # banco's capabilities.
    assert reg.view_applies_to("cross_source", "ibge_pevs") == (True, [])


def test_view_does_not_apply_when_a_required_capability_is_missing():
    # PEVS provides (product, geo, quality) — NOT flow → flows_territorial is gated.
    applies, missing = reg.view_applies_to("flows_territorial", "ibge_pevs")
    assert applies is False
    assert missing == ["flow"]


def test_view_applies_when_the_banco_provides_the_capability():
    # COMEX provides flow → the same view applies with no missing caps.
    assert reg.view_applies_to("flows_territorial", "mdic_comex") == (True, [])


def test_yield_view_gates_pevs_but_not_pam():
    # 'yield' (produtividade) is a PAM-only capability.
    assert reg.view_applies_to("productivity", "ibge_pevs") == (False, ["yield"])
    assert reg.view_applies_to("productivity", "ibge_pam") == (True, [])


# ── bancos_supporting ─────────────────────────────────────────────────────────


def test_bancos_supporting_lists_only_capable_visible_bancos():
    ids = {b.id for b in reg.bancos_supporting("flows_territorial")}  # requires flow
    assert "mdic_comex" in ids
    assert "un_comtrade" in ids
    assert "ibge_pevs" not in ids  # no flow capability
    assert "ibge_pam" not in ids


def test_bancos_supporting_a_yield_view_is_pam_only():
    assert {b.id for b in reg.bancos_supporting("productivity")} == {"ibge_pam"}


def test_bancos_supporting_unknown_view_is_empty():
    assert reg.bancos_supporting("no_such_view") == []


# ── missing_caps_label ────────────────────────────────────────────────────────


def test_missing_caps_label_uses_capability_labels_joined():
    label = reg.missing_caps_label(["flow", "partner"])
    assert reg.CAPABILITIES["flow"]["label"] in label
    assert reg.CAPABILITIES["partner"]["label"] in label
    assert " · " in label  # the two labels are joined with a middot separator


def test_missing_caps_label_falls_back_to_the_raw_code():
    # An unknown capability code echoes itself (no KeyError).
    assert reg.missing_caps_label(["mystery_cap"]) == "mystery_cap"


def test_missing_caps_label_empty_is_empty_string():
    assert reg.missing_caps_label([]) == ""


# ── filter_schema_for ─────────────────────────────────────────────────────────


def test_filter_schema_for_known_banco():
    schema = reg.filter_schema_for("mdic_comex")
    assert schema["table"] == "gold_comex_flows"
    assert any(d["id"] == "fluxo" for d in schema["dims"])


def test_filter_schema_for_unknown_falls_back_to_pevs():
    # A banco without a dedicated schema (e.g. PAM) degrades to the PEVS schema.
    assert reg.filter_schema_for("ibge_pam") == reg.FILTER_SCHEMAS["ibge_pevs"]
    assert reg.filter_schema_for("does_not_exist") == reg.FILTER_SCHEMAS["ibge_pevs"]


# ── structural parity contracts ───────────────────────────────────────────────


def test_every_banco_provides_only_declared_capabilities():
    """A banco's ``provides`` must reference declared CAPABILITIES — a typo would
    silently make a view's gate unsatisfiable for that banco."""
    for b in reg.BANCOS:
        unknown = set(b.provides) - set(reg.CAPABILITIES)
        assert not unknown, f"{b.id} provides undeclared capability(ies): {unknown}"


def test_every_view_requires_only_declared_capabilities():
    for v in reg.VIEW_BY_ID.values():
        unknown = set(v.requires) - set(reg.CAPABILITIES)
        assert not unknown, f"view {v.id} requires undeclared capability(ies): {unknown}"


def test_filter_schema_tables_match_their_banco_table():
    """Each FILTER_SCHEMAS entry's ``table`` must match the banco's registered Gold
    table — a drift would point the FilterMenu's column hints at the wrong table."""
    for banco_id, schema in reg.FILTER_SCHEMAS.items():
        assert schema["table"] == reg.banco_by_id(banco_id).table


def test_filter_schema_dims_use_declared_tiers():
    for schema in reg.FILTER_SCHEMAS.values():
        for dim in schema["dims"]:
            assert dim["tier"] in reg.TIER_LABEL


def test_banco_ids_are_unique():
    ids = [b.id for b in reg.BANCOS]
    assert len(ids) == len(set(ids))
