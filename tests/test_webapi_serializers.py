"""Unit tests for webapi serializers — seam output → contracts.js shapes.

Pure functions, no BigQuery: synthetic DataFrames/dicts in, asserted shapes out.
Locks the magnitude contract (productTS.v in millions, overviewTS.v in billions,
mass quantity ÷1e3, volume ÷1e6) and the pt-BR→en family rename the views need.
"""

from __future__ import annotations

import pandas as pd

from embrapa_commodities.webapi import serializers as s


def test_serialize_snapshot_shapes_and_scales():
    snap = {
        "products": pd.DataFrame(
            [
                {
                    "code": "001",
                    "name": "Castanha",
                    "unit": "t",
                    "unit_native": "kg",
                    "family": "massa",
                },
                {
                    "code": "777",
                    "name": "Madeira",
                    "unit": "m3",
                    "unit_native": "m3",
                    "family": "volume",
                },
            ]
        ),
        "product_ts": pd.DataFrame(
            [
                # mass: 2_000_000_000 R$ → 2000 mi; 5_000_000 t → 5000 mil t
                {
                    "code": "001",
                    "reference_year": 2020,
                    "total_value": 2_000_000_000,
                    "total_qty_native": 5_000_000,
                    "family": "massa",
                },
                # volume: 6_000_000 m³ → 6 mi m³
                {
                    "code": "777",
                    "reference_year": 2020,
                    "total_value": 1_000_000,
                    "total_qty_native": 6_000_000,
                    "family": "volume",
                },
            ]
        ),
        "overview_ts": pd.DataFrame(
            [
                {
                    "reference_year": 2020,
                    "total_value": 3_000_000_000,
                    "q_mass": 5_000_000,
                    "q_vol": 6_000_000,
                }
            ]
        ),
        "uf_data": pd.DataFrame(
            [
                {
                    "state_acronym": "PA",
                    "state_name": "Pará",
                    "region": "Norte",
                    "region_abbrev": "N",
                    "total_value": 1_500_000,
                }
            ]
        ),
        "quality": pd.DataFrame(
            [{"source": "ibge_pevs", "data_quality_flag": "OK", "n_rows": 42, "share": 0.8}]
        ),
        "value_label": "Valor real (IPCA) — R$",
    }
    out = s.serialize_snapshot(snap)

    assert {p["code"] for p in out["products"]} == {"001", "777"}
    assert out["products"][0]["family"] == "mass"  # massa→mass for the views

    # productTS: grouped by code, v in millions, q per-family scaled
    mass = out["productTS"]["001"][0]
    assert mass == {"y": 2020, "v": 2000.0, "q": 5000.0, "family": "mass"}
    vol = out["productTS"]["777"][0]
    assert vol["family"] == "volume" and vol["q"] == 6.0  # m³ ÷1e6

    # overviewTS: v in billions; q_mass mil t, q_vol mi m³
    ov = out["overviewTS"][0]
    assert ov["v"] == 3.0 and ov["q_mass"] == 5000.0 and ov["q_vol"] == 6.0

    uf = out["ufData"][0]
    assert uf["uf"] == "PA" and uf["region"] == "N" and uf["value"] == 1.5
    assert out["quality"][0] == {"id": "OK", "count": 42, "share": 0.8}
    assert out["preview"] is False and out["_synthetic"] is False


def test_serialize_snapshot_empty_is_safe():
    out = s.serialize_snapshot(
        {
            "products": None,
            "product_ts": None,
            "overview_ts": None,
            "uf_data": None,
            "quality": None,
            "value_label": "",
        }
    )
    assert out["products"] == [] and out["productTS"] == {} and out["overviewTS"] == []
    assert out["ufData"] == [] and out["quality"] == []


def test_serialize_cross_camelcase_and_preview():
    assert s.serialize_market_share(
        {
            "unit": "US$ bi",
            "series": [{"y": 2020, "br": 1, "world": 10, "share": 10}],
            "by_product": [{"code": "x", "name": "X", "share": 5}],
        }
    ) == {
        "preview": False,
        "unit": "US$ bi",
        "series": [{"y": 2020, "br": 1, "world": 10, "share": 10}],
        "byProduct": [{"code": "x", "name": "X", "share": 5}],
    }

    ec = s.serialize_export_coef(
        {"unit": "mil t", "incompatible": True, "by_uf": [], "national": {}, "timeseries": []}
    )
    assert ec["byUf"] == [] and ec["incompatible"] is True and ec["preview"] is False


def test_serialize_value_added_derives_bylevel():
    out = s.serialize_value_added(
        {
            "series": [{"y": 2020, "brutaV": 2.0, "procV": 3.0, "procShare": 60.0, "premium": 1.5}],
            "n_codes": 4,
        }
    )
    assert out["years"] == [2020] and out["nCodes"] == 4
    assert out["byLevel"]["bruta"] == [{"y": 2020, "v": 2.0}]
    assert out["byLevel"]["processada"] == [{"y": 2020, "v": 3.0}]


def test_cross_series_none_passthrough():
    assert s.serialize_cross_series(None) is None
    assert s.serialize_cross_series({"banco": "ibge_pevs", "points": []})["preview"] is False


def test_quality_ts_pivots_to_per_year_shares():
    # 2020: 90 OK + 10 MISSING_VALUE → ok 0.9, missing_value 0.1; flag id → contract key
    df = pd.DataFrame(
        [
            {"reference_year": 2020, "data_quality_flag": "OK", "n": 90},
            {"reference_year": 2020, "data_quality_flag": "MISSING_VALUE", "n": 10},
            {"reference_year": 2021, "data_quality_flag": "OK", "n": 50},
            {"reference_year": 2021, "data_quality_flag": "BOUNDARY_HISTORIC", "n": 50},
        ]
    )
    out = s.serialize_snapshot(
        {
            "products": None,
            "product_ts": None,
            "overview_ts": None,
            "uf_data": None,
            "quality": None,
            "quality_ts": df,
            "value_label": "",
        }
    )["qualityTs"]
    assert [r["y"] for r in out] == [2020, 2021]  # sorted by year
    assert out[0]["ok"] == 0.9 and out[0]["missing_value"] == 0.1 and out[0]["outlier"] == 0.0
    assert out[1]["ok"] == 0.5 and out[1]["boundary"] == 0.5  # BOUNDARY_HISTORIC → boundary


def test_quality_by_product_per_product_shares_top_n():
    df = pd.DataFrame(
        [
            # product A: 800 rows (top by volume) — 600 OK + 200 MISSING_VALUE
            {"code": "A", "name": "Prod A", "data_quality_flag": "OK", "n": 600},
            {"code": "A", "name": "Prod A", "data_quality_flag": "MISSING_VALUE", "n": 200},
            # product B: 100 rows — all OK
            {"code": "B", "name": "Prod B", "data_quality_flag": "OK", "n": 100},
        ]
    )
    out = s.serialize_snapshot(
        {
            "products": None,
            "product_ts": None,
            "overview_ts": None,
            "uf_data": None,
            "quality": None,
            "quality_by_product": df,
            "value_label": "",
        }
    )["qualityByProduct"]
    assert [r["code"] for r in out] == ["A", "B"]  # ranked by row volume
    assert out[0]["OK"] == 0.75 and out[0]["MISSING_VALUE"] == 0.25  # flag-id keys, shares
    assert out[1]["OK"] == 1.0 and out[1]["OUTLIER"] == 0.0  # absent flags read 0
