"""Coverage tests for webapi.serializers — targets the currently-uncovered edge
paths: ``_int_or_none``/``_refresh_label``/``serialize_source_meta`` timestamp
branches, ``serialize_price_spread`` incompatible flag, the empty-df table page,
and the None worklist normalizations.

Pure functions, no BigQuery: synthetic DataFrames/dicts in, asserted shapes out.
Mirrors the fixture style of tests/test_webapi_serializers.py.
"""

from __future__ import annotations

import pandas as pd

from embrapa_dashboard.webapi import serializers as s


def test_int_or_none_non_numeric_string_returns_none():
    """``_int_or_none`` swallows a TypeError/ValueError from ``float()`` and returns
    None (lines 121-122) — a non-numeric string is the natural trigger. The None and
    NaN guards (the earlier branches) are exercised by serialize_source_meta tests."""
    assert s._int_or_none("not-a-number") is None  # float() raises ValueError
    assert s._int_or_none([1, 2]) is None  # float() raises TypeError
    # the happy + None + NaN guards still behave (regression around the new branch)
    assert s._int_or_none(7) == 7
    assert s._int_or_none(None) is None
    assert s._int_or_none(float("nan")) is None


def test_refresh_label_formats_brasilia_ptbr_stamp():
    """``_refresh_label`` (lines 129-137): a real UTC Gold timestamp → the pt-BR
    Brasília stamp 'DD mês YYYY · HH:MM BRT'. A naive timestamp is localized to UTC
    then converted to America/Sao_Paulo (UTC−3), so 12:30 UTC → 09:30 BRT."""
    label = s._refresh_label("2026-05-28T12:30:00")
    # 12:30 UTC localized then converted to Brasília (UTC−3) → 09:30, month 'mai'.
    assert label == "28 mai 2026 · 09:30 BRT"


def test_refresh_label_tz_aware_input_is_converted_not_double_localized():
    """A tz-aware timestamp must NOT be re-localized (the ``t.tzinfo is None`` guard on
    line 135) — it is only tz_convert-ed to Brasília. 03:00 UTC → 00:00 BRT, 1 Jan."""
    label = s._refresh_label(pd.Timestamp("2026-01-01T03:00:00", tz="UTC"))
    assert label == "01 jan 2026 · 00:00 BRT"


def test_refresh_label_unparseable_value_returns_none():
    """An unparseable value makes ``pd.Timestamp(ts)`` raise → the except branch
    (lines 131-132) returns None instead of crashing the meta serialization."""
    assert s._refresh_label("definitely not a date") is None


def test_refresh_label_none_short_circuits():
    """The early ``ts is None`` guard (the line just before 129) returns None without
    touching pandas."""
    assert s._refresh_label(None) is None


def test_serialize_source_meta_emits_iso_and_label_from_last_refresh():
    """When ``last_refresh`` is present, serialize_source_meta runs the timestamp block
    (lines 154-158): it computes ``lastRefresh`` as an ISO string and ``lastRefreshLabel``
    via ``_refresh_label``. Exercises the populated path the completeness tests skip."""
    out = s.serialize_source_meta(
        {
            "source": "ibge_pevs",
            "gold_table": "gold_pevs_production",
            "year_end": 2024,
            "last_refresh": "2026-05-28T12:30:00",
        }
    )
    # iso = ts.isoformat() — a real ISO string (not None)
    assert out["lastRefresh"] == pd.Timestamp("2026-05-28T12:30:00").isoformat()
    assert out["lastRefreshLabel"] == "28 mai 2026 · 09:30 BRT"


def test_serialize_source_meta_unparseable_last_refresh_yields_none_iso():
    """An unparseable ``last_refresh`` makes ``pd.Timestamp(last)`` raise → the except
    branch (line 158) sets ``iso = None``. ``lastRefreshLabel`` is likewise None."""
    out = s.serialize_source_meta(
        {"source": "x", "gold_table": "g", "last_refresh": "garbage-not-a-ts"}
    )
    assert out["lastRefresh"] is None
    assert out["lastRefreshLabel"] is None


def test_serialize_source_meta_nat_last_refresh_yields_none_iso():
    """A NaT ``last_refresh`` parses fine but ``pd.isna(ts)`` is True → ``iso = None``
    (line 156's NaT branch) without raising."""
    out = s.serialize_source_meta({"source": "x", "gold_table": "g", "last_refresh": pd.NaT})
    assert out["lastRefresh"] is None
    assert out["lastRefreshLabel"] is None


def test_serialize_price_spread_marks_incompatible():
    """serialize_price_spread sets ``incompatible: True`` only when the seam flags the
    basket as incompatible (line 617). The happy path omits the key entirely."""
    incompatible = s.serialize_price_spread({"unit": "US$/kg", "series": [], "incompatible": True})
    assert incompatible["incompatible"] is True
    assert incompatible["preview"] is False and incompatible["unit"] == "US$/kg"

    ok = s.serialize_price_spread({"unit": "US$/kg", "series": [{"y": 2024, "v": 1.0}]})
    assert "incompatible" not in ok
    assert ok["series"] == [{"y": 2024, "v": 1.0}]


def test_serialize_table_page_empty_df_keeps_schema_columns():
    """A present page whose ``df`` is EMPTY takes the ``_empty(df)`` branch (line 832):
    it keeps the page's schema columns but emits no rows (instead of deriving columns
    from ``df.columns``)."""
    page = {
        "columns": [
            {"name": "reference_year", "type": "INTEGER"},
            {"name": "product_code", "type": "STRING"},
        ],
        "df": pd.DataFrame(),  # empty result window
        "total": 0,
        "table": "gold_pevs_production",
        "label": "Gold · PEVS",
        "grain": "linha por (ano, UF, produto)",
    }
    out = s.serialize_table_page(page)
    assert out["columns"] == page["columns"]  # schema columns survive
    assert out["rows"] == []  # but no data rows
    assert out["total"] == 0 and out["table"] == "gold_pevs_production"
    assert out["label"] == "Gold · PEVS" and out["grain"] == "linha por (ano, UF, produto)"


def test_serialize_catalog_worklist_none_normalizes_to_empty():
    """``None`` (no catalog) → the empty-catalog shell (line 861), so the admin editor
    renders an honest empty state instead of crashing on a missing dict."""
    assert s.serialize_catalog_worklist(None) == {
        "entries": [],
        "total": 0,
        "by_agrupamento": [],
    }


def test_serialize_catalog_worklist_populated_passes_through():
    """A populated worklist rides through JSON-native, with ``total`` coerced to int."""
    out = s.serialize_catalog_worklist(
        {
            "entries": [{"code": "001", "name": "Castanha"}],
            "total": "5",  # str → int() coercion
            "by_agrupamento": [{"agrupamento": "Frutas", "count": 5}],
        }
    )
    assert out["entries"] == [{"code": "001", "name": "Castanha"}]
    assert out["total"] == 5 and isinstance(out["total"], int)
    assert out["by_agrupamento"] == [{"agrupamento": "Frutas", "count": 5}]


def test_serialize_orphan_worklist_none_normalizes_to_empty():
    """``None`` (no Descontinuados) → the empty orphan shell (line 873)."""
    assert s.serialize_orphan_worklist(None) == {"orphans": [], "total": 0}


def test_serialize_orphan_worklist_populated_passes_through():
    """A populated orphan worklist rides through, ``total`` coerced to int."""
    out = s.serialize_orphan_worklist(
        {"orphans": [{"code": "999", "flagged_at": "2026-06-01"}], "total": "1"}
    )
    assert out["orphans"] == [{"code": "999", "flagged_at": "2026-06-01"}]
    assert out["total"] == 1 and isinstance(out["total"], int)
