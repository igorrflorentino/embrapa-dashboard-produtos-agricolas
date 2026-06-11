"""Unit tests for the seam's market-nature aggregation (the #5 analytical core).

Pure-ish: the two gateway readers are monkeypatched with synthetic DataFrames,
so no BigQuery. Locks the curated-purpose contract — COMTRADE value summed by the
(customsCode × flowCode) → market mapping, with unclassified pairs dropped and the
``C00`` exclusion already handled upstream in the SQL builder.
"""

from __future__ import annotations

import pandas as pd
import pytest


def _seam():
    pytest.importorskip("flask_caching")
    from embrapa_commodities.webapi import seam

    return seam


def test_flow_market_worklist_builds_grid_with_summed_values(monkeypatch):
    seam = _seam()
    cpc = pd.DataFrame(
        [
            # same pair across two years → summed into one cell
            {"customs_code": "C04", "flow_code": "M", "reference_year": 2022, "value_usd": 1e9},
            {"customs_code": "C04", "flow_code": "M", "reference_year": 2023, "value_usd": 0.5e9},
            {"customs_code": "C03", "flow_code": "X", "reference_year": 2022, "value_usd": 3e9},
        ]
    )
    monkeypatch.setattr(seam.gateway, "fetch_comtrade_cpc_value", lambda codes=(): cpc)
    monkeypatch.setattr(seam.gateway, "fetch_current_flow_market", lambda: None)  # log absent → {}

    out = seam.flow_market_worklist()

    assert out["customs"] == ["C03", "C04"]  # sorted set of present codes
    assert {f["code"] for f in out["flows"]} == {"M", "X"}
    assert out["total"] == 2 and out["classified"] == 0  # nobody classified yet
    cells = {(c["customs_code"], c["flow_code"]): c["value_usd"] for c in out["cells"]}
    assert cells[("C04", "M")] == 1.5e9  # summed across 2022 + 2023
    assert cells[("C03", "X")] == 3e9
    assert out["cells"][0]["customs_code"] == "C03"  # cells sorted by value desc


def test_flow_market_worklist_carries_persisted_market(monkeypatch):
    seam = _seam()
    cpc = pd.DataFrame(
        [{"customs_code": "C04", "flow_code": "M", "reference_year": 2022, "value_usd": 1e9}]
    )
    fm = pd.DataFrame([{"customs_code": "C04", "flow_code": "M", "market": "processamento"}])
    monkeypatch.setattr(seam.gateway, "fetch_comtrade_cpc_value", lambda codes=(): cpc)
    monkeypatch.setattr(seam.gateway, "fetch_current_flow_market", lambda: fm)

    out = seam.flow_market_worklist()
    assert out["classified"] == 1
    assert out["cells"][0]["market"] == "processamento"


def test_market_nature_sums_value_by_curated_purpose(monkeypatch):
    seam = _seam()
    cpc = pd.DataFrame(
        [
            {"customs_code": "C04", "flow_code": "M", "reference_year": 2022, "value_usd": 1e9},
            {"customs_code": "C03", "flow_code": "X", "reference_year": 2022, "value_usd": 2e9},
            # unclassified pair → must be dropped from the analysis
            {"customs_code": "C99", "flow_code": "M", "reference_year": 2022, "value_usd": 5e9},
        ]
    )
    fm = pd.DataFrame(
        [
            {"customs_code": "C04", "flow_code": "M", "market": "processamento"},
            {"customs_code": "C03", "flow_code": "X", "market": "consumo"},
        ]
    )
    monkeypatch.setattr(seam.gateway, "fetch_comtrade_cpc_value", lambda codes=(): cpc)
    monkeypatch.setattr(seam.gateway, "fetch_current_flow_market", lambda: fm)

    out = seam.market_nature()

    assert out["years"] == [2022]
    row = out["series"][0]
    assert row["y"] == 2022
    assert row["consumo"] == 2.0  # 2e9 USD → US$ bi
    assert row["processamento"] == 1.0  # 1e9 USD → US$ bi (C99 unclassified excluded)
    assert out["latest"] == row
    assert out["n_classified"] == 2


def test_market_nature_empty_when_nothing_classified(monkeypatch):
    seam = _seam()
    cpc = pd.DataFrame(
        [{"customs_code": "C04", "flow_code": "M", "reference_year": 2022, "value_usd": 1e9}]
    )
    monkeypatch.setattr(seam.gateway, "fetch_comtrade_cpc_value", lambda codes=(): cpc)
    monkeypatch.setattr(seam.gateway, "fetch_current_flow_market", lambda: None)  # log absent

    out = seam.market_nature()
    assert out["years"] == [] and out["series"] == [] and out["latest"] == {}
    assert out["n_classified"] == 0


def test_market_nature_empty_for_commodity_without_comtrade_codes(monkeypatch):
    # A commodity scoped by the selector that has NO COMTRADE HS codes must return
    # empty — NOT silently fall through to the unscoped all-commodities total
    # (an empty codes tuple means "no filter" to fetch_comtrade_cpc_value).
    seam = _seam()
    monkeypatch.setattr(
        seam,
        "commodity_catalog",
        lambda: {"manicoba": {"comtrade": [], "comex": ["1"], "pevs": ["2"]}},
    )
    # Data + a classification both exist; the guard must still return empty here.
    cpc = pd.DataFrame(
        [{"customs_code": "C04", "flow_code": "M", "reference_year": 2022, "value_usd": 1e9}]
    )
    fm = pd.DataFrame([{"customs_code": "C04", "flow_code": "M", "market": "processamento"}])
    monkeypatch.setattr(seam.gateway, "fetch_comtrade_cpc_value", lambda codes=(): cpc)
    monkeypatch.setattr(seam.gateway, "fetch_current_flow_market", lambda: fm)

    out = seam.market_nature("manicoba")
    assert out["years"] == [] and out["series"] == [] and out["latest"] == {}
    assert out["n_classified"] == 1  # the mapping is still reported
