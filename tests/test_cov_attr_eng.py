"""Coverage tests for the FROZEN Engenharia de Atributos feature.

Targets the currently-uncovered branches in the seam readers
(``webapi/seam_attribute_engineering.py``) and the serving writers
(``serving/attribute_engineering.py``):

  * seam: the empty-DataFrame degrade paths of ``curator_emails`` /
    ``_current_code_levels`` (and the latter's success row-mapping), the
    commodity-scope ``continue`` in ``_value_added_codes_by_level``, the
    empty-value ``continue`` in ``_value_added_accumulate``, and the
    None/empty short-circuit of ``_market_nature_accumulate``.
  * serving: the over-length ``market`` validation raise, and the full
    ``record_flow_market`` insert path with cache invalidation (which exercises
    ``invalidate_flow_market_cache``'s success branch under an app-bound cache).

The gateway readers are monkeypatched with synthetic DataFrames and the BQ
client is a ``mock.Mock`` — no live warehouse. Reuses the house patterns
(``pytest.importorskip('flask_caching')``, the SimpleCache app binding, the IAP
email header).
"""

from __future__ import annotations

from unittest import mock

import pandas as pd
import pytest

from embrapa_commodities.serving import iap


def _curation():
    pytest.importorskip("flask_caching")
    from embrapa_commodities.webapi import seam_attribute_engineering

    return seam_attribute_engineering


def _writer():
    pytest.importorskip("flask_caching")
    from embrapa_commodities.serving import attribute_engineering

    return attribute_engineering


def _bind_simplecache():
    """Bind the shared serving cache to a fresh Flask app (SimpleCache)."""
    from flask import Flask

    from embrapa_commodities.serving.cache import cache

    app = Flask(__name__)
    cache.init_app(app, config={"CACHE_TYPE": "SimpleCache", "CACHE_DEFAULT_TIMEOUT": 300})
    return app, cache


def _settings():
    from embrapa_commodities.config import Settings

    return Settings(_env_file=None, gcp_project_id="test-project")  # type: ignore[call-arg]


# ── seam line 64: curator_emails returns empty set on an empty DataFrame ────────


def test_curator_emails_empty_when_table_empty(monkeypatch):
    seam = _curation()
    # The allowlist table EXISTS (no NotFound) but holds no rows → empty set, which
    # makes routes fall back to "any IAP-authenticated caller may curate".
    monkeypatch.setattr(seam.gateway, "fetch_curators", lambda: pd.DataFrame())
    assert seam.curator_emails() == set()


def test_curator_emails_empty_when_none(monkeypatch):
    seam = _curation()
    monkeypatch.setattr(seam.gateway, "fetch_curators", lambda: None)
    assert seam.curator_emails() == set()


# ── seam lines 78-80: _current_code_levels empty + success row mapping ──────────


def test_current_code_levels_empty_when_view_empty(monkeypatch):
    seam = _curation()
    # The SCD2 view exists (no NotFound) but is empty → {} (worklist still renders).
    monkeypatch.setattr(
        seam.gateway, "fetch_current_code_industrialization", lambda: pd.DataFrame()
    )
    assert seam._current_code_levels() == {}


def test_current_code_levels_maps_rows_to_levels(monkeypatch):
    seam = _curation()
    df = pd.DataFrame(
        [
            {"source": "mdic_comex", "code": "0801", "industrialization_level": "processada"},
            {"source": "ibge_pevs", "code": 5, "industrialization_level": "bruta"},
        ]
    )
    monkeypatch.setattr(seam.gateway, "fetch_current_code_industrialization", lambda: df)
    out = seam._current_code_levels()
    # Codes are stringified (note ibge_pevs code 5 -> "5").
    assert out == {("mdic_comex", "0801"): "processada", ("ibge_pevs", "5"): "bruta"}


# ── seam line 173: _value_added_codes_by_level skips out-of-scope codes ─────────


def test_value_added_codes_by_level_drops_out_of_scope_code(monkeypatch):
    seam = _curation()
    from embrapa_commodities.webapi import seam_base

    # Two classified COMEX codes; the commodity scope only includes "A" → "B" is
    # dropped via the `scope is not None and code not in scope` continue (line 173).
    monkeypatch.setattr(
        seam,
        "_current_code_levels",
        lambda: {("mdic_comex", "A"): "bruta", ("mdic_comex", "B"): "bruta"},
    )
    monkeypatch.setattr(seam_base, "_codes", lambda cid, src: ["A"])  # scope = {"A"}

    by_level = seam._value_added_codes_by_level("castanha")
    assert by_level["bruta"] == ["A"]  # "B" excluded by the scope filter
    assert by_level["processada"] == []


# ── seam line 196: _value_added_accumulate skips a level whose value is empty ────


def test_value_added_accumulate_skips_level_with_empty_value(monkeypatch):
    seam = _curation()
    from embrapa_commodities.webapi import seam_base

    calls = []

    def fake_xyear(metric, codes, uf_codes=()):
        calls.append(metric)
        # exp_value returns empty → the level is skipped at line 196 BEFORE the
        # exp_weight query ever runs (so no exp_weight call is recorded).
        return {}

    monkeypatch.setattr(seam_base, "_xyear", fake_xyear)

    acc, n = seam._value_added_accumulate({"bruta": ["A"], "processada": []})
    assert acc == {} and n == 0
    # Only the value query ran; the `continue` short-circuited the weight query.
    assert calls == ["mdic_comex:exp_value"]


def test_value_added_returns_empty_when_value_query_empty(monkeypatch):
    """End-to-end: value_added surfaces an empty series when the export-value
    reader yields nothing for the classified level (the line-196 path)."""
    seam = _curation()
    from embrapa_commodities.webapi import seam_base

    monkeypatch.setattr(seam, "_current_code_levels", lambda: {("mdic_comex", "A"): "bruta"})
    monkeypatch.setattr(seam_base, "_xyear", lambda metric, codes, uf_codes=(): {})
    out = seam.value_added()
    assert out == {"series": [], "n_codes": 0}


# ── seam line 352: _market_nature_accumulate short-circuits on None/empty ───────


def test_market_nature_accumulate_empty_on_none():
    seam = _curation()
    assert seam._market_nature_accumulate(None, {("C04", "M"): "processamento"}) == {}


def test_market_nature_accumulate_empty_on_empty_df():
    seam = _curation()
    assert seam._market_nature_accumulate(pd.DataFrame(), {}) == {}


# ── writer line 311: _validate_flow_market_edit rejects an over-length market ────


def test_validate_flow_market_edit_rejects_long_market():
    curation = _writer()
    too_long = "x" * (curation.MAX_STAGE_LEN + 1)
    with pytest.raises(ValueError, match="market excede"):
        curation._validate_flow_market_edit("4000", "X", too_long)


# ── writer lines 296 + 337-338: full insert path invalidates the bound cache ────


def test_record_flow_market_inserts_and_invalidates_cache(monkeypatch):
    """A fresh edit (no client change_id → no dedupe probe) runs the INSERT and,
    with invalidate_cache=True under an app-bound cache, exercises
    ``invalidate_flow_market_cache``'s success branch (delete_memoized)."""
    curation = _writer()

    # Self-heal is a no-op (we don't create real tables).
    monkeypatch.setattr(curation, "ensure_flow_market_log_table", lambda *a, **k: None)
    client = mock.Mock()
    client.query.return_value.result.return_value = None
    headers = {iap.IAP_EMAIL_HEADER: "accounts.google.com:alice@embrapa.br"}

    app, cache = _bind_simplecache()
    with app.app_context():
        # Prime the memoized reader so delete_memoized has a live entry to bump.
        cache.clear()
        record = curation.record_flow_market(
            "4000",
            "X",
            "consumo",
            headers,
            settings=_settings(),
            client=client,
            invalidate_cache=True,  # drives line 296 -> invalidate_flow_market_cache (337-338)
        )

    assert record["deduped"] is False
    assert record["customs_code"] == "4000"
    assert record["flow_code"] == "X"
    assert record["market"] == "consumo"
    assert record["edited_by"] == "alice@embrapa.br"
    # No client change_id → only the INSERT ran (no dedupe SELECT probe).
    assert client.query.call_count == 1
    assert "insert into" in client.query.call_args.args[0].lower()
