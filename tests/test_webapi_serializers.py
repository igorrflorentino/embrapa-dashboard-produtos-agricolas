"""Unit tests for webapi serializers — seam output → contracts.js shapes.

Pure functions, no BigQuery: synthetic DataFrames/dicts in, asserted shapes out.
Locks the magnitude contract (productTS.v in millions, overviewTS.v in billions,
mass quantity ÷1e3, volume ÷1e6) and the pt-BR→en family rename the views need.
"""

from __future__ import annotations

import pandas as pd
import pytest

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
                # mass: 2_000_000_000 R$ → 2000 mi; 5_000_000 t (base) → 5000 mil t
                {
                    "code": "001",
                    "reference_year": 2020,
                    "total_value": 2_000_000_000,
                    "total_qty_native": 5_000_000,
                    "total_qty_base": 5_000_000,  # PEVS: native == base (t)
                    "family": "massa",
                },
                # volume: 6_000_000 m³ (base) → 6 mi m³
                {
                    "code": "777",
                    "reference_year": 2020,
                    "total_value": 1_000_000,
                    "total_qty_native": 6_000_000,
                    "total_qty_base": 6_000_000,  # PEVS: native == base (m³)
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
    # no q_mass/q_vol columns in this fixture → safe 0.0 fallback (real values
    # are asserted in test_uf_data_emits_per_family_quantities).
    assert uf["q_mass"] == 0.0 and uf["q_vol"] == 0.0
    # _quality emits a pt-BR label so the donut stays Portuguese even for flags the
    # frontend taxonomy lacks (INCOMPLETE/MISSING_WEIGHT).
    assert out["quality"][0] == {"id": "OK", "label": "OK", "count": 42, "share": 0.8}
    assert out["preview"] is False and out["_synthetic"] is False


def test_product_ts_scales_qty_base_not_native_for_kg_native_trade_codes():
    """Regression: COMEX/COMTRADE quantities are mostly kg-NATIVE. The serializer
    must scale total_qty_base (already t / m³ in the marts) — scaling the native
    kg as if tonnes displayed trade quantities 1000× too large."""
    snap = {
        "products": None,
        "product_ts": pd.DataFrame(
            [
                # kg-native NCM: 5_000_000_000 kg native = 5_000_000 t base → 5000 mil t
                {
                    "code": "08012100",
                    "reference_year": 2022,
                    "total_value": 1_000_000_000,
                    "total_qty_native": 5_000_000_000,
                    "total_qty_base": 5_000_000,
                    "family": "massa",
                },
                # t-native NCM in the same family: base == native
                {
                    "code": "44012200",
                    "reference_year": 2022,
                    "total_value": 2_000_000,
                    "total_qty_native": 3_000,
                    "total_qty_base": 3_000,
                    "family": "massa",
                },
            ]
        ),
        "overview_ts": pd.DataFrame(
            [
                {
                    "reference_year": 2022,
                    "total_value": 1_002_000_000,
                    # the seam already aggregated qty_base per family (t)
                    "q_mass": 5_003_000,
                    "q_vol": 0.0,
                }
            ]
        ),
        "uf_data": None,
        "quality": None,
        "value_label": "Valor (US$ FOB)",
    }
    out = s.serialize_snapshot(snap)
    assert out["productTS"]["08012100"][0]["q"] == 5000.0  # mil t, from qty_base
    assert out["productTS"]["44012200"][0]["q"] == 3.0
    assert out["overviewTS"][0]["q_mass"] == 5003.0  # mil t — never kg/1e3


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
    # Real Gold flags only: 2020 OK/MISSING_VALUE; 2021 OK/INCOMPLETE (PEVS) +
    # MISSING_WEIGHT (COMEX) — the synthetic ESTIMATED/OUTLIER/BOUNDARY are gone.
    df = pd.DataFrame(
        [
            {"reference_year": 2020, "data_quality_flag": "OK", "n": 90},
            {"reference_year": 2020, "data_quality_flag": "MISSING_VALUE", "n": 10},
            {"reference_year": 2021, "data_quality_flag": "OK", "n": 50},
            {"reference_year": 2021, "data_quality_flag": "INCOMPLETE", "n": 30},
            {"reference_year": 2021, "data_quality_flag": "MISSING_WEIGHT", "n": 20},
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
    assert out[0]["ok"] == 0.9 and out[0]["missing_value"] == 0.1
    # every real contract key present (absent ones read 0); synthetic keys are gone
    assert set(out[0]) == {
        "y",
        "ok",
        "missing_value",
        "missing_quantity",
        "missing_weight",
        "incomplete",
    }
    assert out[1]["ok"] == 0.5 and out[1]["incomplete"] == 0.3 and out[1]["missing_weight"] == 0.2


def test_quality_ts_unmapped_flag_lowers_known_shares_not_dropped():
    # An unexpected flag still counts toward the denominator (so the stack never
    # silently sums to >1 by ignoring it) — it just maps to no output key.
    df = pd.DataFrame(
        [
            {"reference_year": 2020, "data_quality_flag": "OK", "n": 80},
            {"reference_year": 2020, "data_quality_flag": "SOMETHING_NEW", "n": 20},
        ]
    )
    out = s._quality_ts(df)
    assert out[0]["ok"] == 0.8  # 80/100 — the 20 unknown rows are in `total`


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
    # absent REAL flags read 0 (MISSING_WEIGHT/INCOMPLETE), and the synthetic
    # OUTLIER/ESTIMATED/BOUNDARY_HISTORIC keys no longer exist at all.
    assert out[1]["OK"] == 1.0 and out[1]["MISSING_WEIGHT"] == 0.0
    assert "OUTLIER" not in out[1] and "BOUNDARY_HISTORIC" not in out[1]


def test_serialize_market_nature_passthrough():
    out = s.serialize_market_nature(
        {
            "years": [2022, 2023],
            "series": [
                {"y": 2022, "consumo": 1.0, "processamento": 2.0},
                {"y": 2023, "consumo": 1.5, "processamento": 2.5},
            ],
            "latest": {"y": 2023, "consumo": 1.5, "processamento": 2.5},
            "n_classified": 3,
        }
    )
    assert out["preview"] is False  # real data, never a synthetic demo banner
    assert out["years"] == [2022, 2023]
    assert out["latest"]["processamento"] == 2.5
    assert len(out["series"]) == 2


def test_serialize_market_nature_empty_is_safe():
    # Pre-classification (no pair curated) → empty shells; the view guards series[0].
    assert s.serialize_market_nature({}) == {
        "preview": False,
        "years": [],
        "series": [],
        "latest": {},
    }


def _productivity_payload():
    # Soja, 2 UFs × 2 years. Yield (kg/ha) = production_t × 1000 / area_harvested_ha,
    # recomputed from the SUMMED totals at each grain — never averaged across UFs.
    rows = pd.DataFrame(
        [
            {
                "reference_year": 2023,
                "state_acronym": "PR",
                "state_name": "Paraná",
                "region": "Sul",
                "region_abbrev": "S",
                "production_t": 1000.0,
                "area_planted_ha": 520.0,
                "area_harvested_ha": 500.0,
            },
            {
                "reference_year": 2023,
                "state_acronym": "MT",
                "state_name": "Mato Grosso",
                "region": "Centro-Oeste",
                "region_abbrev": "CO",
                "production_t": 2000.0,
                "area_planted_ha": 410.0,
                "area_harvested_ha": 400.0,
            },
            {
                "reference_year": 2024,
                "state_acronym": "PR",
                "state_name": "Paraná",
                "region": "Sul",
                "region_abbrev": "S",
                "production_t": 1200.0,
                "area_planted_ha": 520.0,
                "area_harvested_ha": 500.0,
            },
            {
                "reference_year": 2024,
                "state_acronym": "MT",
                "state_name": "Mato Grosso",
                "region": "Centro-Oeste",
                "region_abbrev": "CO",
                "production_t": 2400.0,
                "area_planted_ha": 410.0,
                "area_harvested_ha": 400.0,
            },
        ]
    )
    return {
        "crops": [{"code": "40124", "name": "Soja"}, {"code": "40122", "name": "Milho"}],
        "active": "40124",
        "active_name": "Soja",
        "rows": rows,
    }


def test_serialize_productivity_recomputes_yield_and_aggregates():
    out = s.serialize_productivity(_productivity_payload())
    assert out["preview"] is False  # the contract requires the preview key
    assert out["crop"] == {"code": "40124", "name": "Soja"}
    assert [c["code"] for c in out["crops"]] == ["40124", "40122"]
    assert out["yieldUnit"] == "kg/ha" and out["areaUnit"] == "ha"

    # National series: production + harvested area SUMMED per year; yield from totals.
    assert [d["y"] for d in out["series"]] == [2023, 2024]
    y2023, y2024 = out["series"]
    assert y2023["prodT"] == 3000.0 and y2023["areaHa"] == 900.0
    # 3333.3 kg/ha — from the totals, NOT the average of 2000 & 5000.
    assert y2023["yieldKgHa"] == pytest.approx(3000.0 * 1000 / 900)
    assert y2024["yieldKgHa"] == pytest.approx(3600.0 * 1000 / 900)  # 4000

    # national = the LATEST year's totals (matches the byUF grain) + CAGR.
    assert out["national"]["prodT"] == 3600.0 and out["national"]["areaHa"] == 900.0
    assert out["national"]["yieldKgHa"] == pytest.approx(4000.0)
    # CAGR over the 1-year span: (4000/3333.3)^(1/1) − 1 = 20%.
    assert out["national"]["yieldCagr"] == pytest.approx(20.0, abs=0.1)

    # Per-UF is the LATEST year (2024) only, with yield + summable area/production.
    by_uf = {r["uf"]: r for r in out["byUF"]}
    assert set(by_uf) == {"PR", "MT"}
    assert by_uf["MT"]["yieldKgHa"] == pytest.approx(2400.0 * 1000 / 400)  # 6000
    assert by_uf["PR"]["yieldKgHa"] == pytest.approx(1200.0 * 1000 / 500)  # 2400
    assert by_uf["MT"]["prodT"] == 2400.0 and by_uf["MT"]["areaHa"] == 400.0


def test_serialize_productivity_handles_zero_area_and_empty():
    assert s.serialize_productivity(None) is None  # banco lacks the yield capability
    # Empty frame → a valid contract with empty series (the view renders empty charts).
    empty = s.serialize_productivity(
        {"crops": [], "active": "", "active_name": "", "rows": pd.DataFrame()}
    )
    assert empty["preview"] is False
    assert empty["series"] == [] and empty["byUF"] == []
    # national carries every contracted field, zeroed, even with no data.
    assert empty["national"] == {"yieldKgHa": 0.0, "areaHa": 0.0, "prodT": 0.0, "yieldCagr": 0.0}
    # Zero harvested area must not divide-by-zero → yield 0.
    zero = s.serialize_productivity(
        {
            "crops": [{"code": "1", "name": "X"}],
            "active": "1",
            "active_name": "X",
            "rows": pd.DataFrame(
                [
                    {
                        "reference_year": 2024,
                        "state_acronym": "PR",
                        "state_name": "Paraná",
                        "region": "Sul",
                        "region_abbrev": "S",
                        "production_t": 100.0,
                        "area_planted_ha": 0.0,
                        "area_harvested_ha": 0.0,
                    }
                ]
            ),
        }
    )
    assert zero["series"][0]["yieldKgHa"] == 0.0 and zero["byUF"][0]["yieldKgHa"] == 0.0


def test_uf_data_emits_per_family_quantities():
    """ufData q_mass/q_vol are real (from the by-UF per-family qty_base sums),
    scaled like overviewTS: massa ÷1e3 → mil t, volume ÷1e6 → mi m³."""
    snap = {
        "products": None,
        "product_ts": None,
        "overview_ts": None,
        "uf_data": pd.DataFrame(
            [
                {
                    "state_acronym": "PA",
                    "state_name": "Pará",
                    "region_abbrev": "N",
                    "total_value": 1_500_000,
                    "q_mass": 5_000_000,  # t → 5000 mil t
                    "q_vol": 6_000_000,  # m³ → 6 mi m³
                }
            ]
        ),
        "quality": None,
        "value_label": "",
    }
    uf = s.serialize_snapshot(snap)["ufData"][0]
    assert uf["value"] == 1.5 and uf["q_mass"] == 5000.0 and uf["q_vol"] == 6.0


def test_uf_yearly_emits_real_per_uf_year_rows():
    """ufYearly is REAL per-(UF, year) Gold history (backs the ano × UF heatmap),
    scaled like ufData: value ÷1e6, q_mass ÷1e3 → mil t, q_vol ÷1e6 → mi m³."""
    snap = {
        "products": None,
        "product_ts": None,
        "overview_ts": None,
        "uf_data": None,
        "uf_yearly": pd.DataFrame(
            [
                {
                    "state_acronym": "PA",
                    "state_name": "Pará",
                    "region_abbrev": "N",
                    "reference_year": 2019,
                    "total_value": 1_000_000,
                    "q_mass": 2_000_000,  # t → 2000 mil t
                    "q_vol": 3_000_000,  # m³ → 3 mi m³
                },
                {
                    "state_acronym": "PA",
                    "state_name": "Pará",
                    "region_abbrev": "N",
                    "reference_year": 2020,
                    "total_value": 1_500_000,
                    "q_mass": 2_500_000,
                    "q_vol": float("nan"),  # no volume that year → 0.0
                },
            ]
        ),
        "quality": None,
        "value_label": "",
    }
    rows = s.serialize_snapshot(snap)["ufYearly"]
    assert [(r["uf"], r["year"]) for r in rows] == [("PA", 2019), ("PA", 2020)]
    assert rows[0] == {
        "year": 2019,
        "uf": "PA",
        "name": "Pará",
        "region": "N",
        "value": 1.0,
        "q_mass": 2000.0,
        "q_vol": 3.0,
    }
    assert rows[1]["value"] == 1.5 and rows[1]["q_mass"] == 2500.0 and rows[1]["q_vol"] == 0.0


def test_uf_yearly_empty_is_safe():
    out = s.serialize_snapshot(
        {
            "products": None,
            "product_ts": None,
            "overview_ts": None,
            "uf_data": None,
            "uf_yearly": None,
            "quality": None,
            "value_label": "",
        }
    )
    assert out["ufYearly"] == []


def test_serialize_geo_yearly_wraps_uf_yearly_with_same_scaling():
    """serialize_geo_yearly is the /api/geo-yearly payload: { ufYearly: [...] } with
    the EXACT scaling _uf_yearly applies (value ÷1e6, q_mass ÷1e3, q_vol ÷1e6), so the
    basket cube is byte-interchangeable with the snapshot's ufYearly client-side."""
    df = pd.DataFrame(
        [
            {
                "state_acronym": "PA",
                "state_name": "Pará",
                "region_abbrev": "N",
                "reference_year": 2024,
                "total_value": 1_000_000,
                "q_mass": 2_000_000,
                "q_vol": 3_000_000,
            }
        ]
    )
    out = s.serialize_geo_yearly(df)
    assert out == {
        "ufYearly": [
            {
                "year": 2024,
                "uf": "PA",
                "name": "Pará",
                "region": "N",
                "value": 1.0,
                "q_mass": 2000.0,
                "q_vol": 3.0,
            }
        ]
    }


def test_serialize_geo_yearly_empty_is_safe():
    assert s.serialize_geo_yearly(None) == {"ufYearly": []}
    assert s.serialize_geo_yearly(pd.DataFrame()) == {"ufYearly": []}


def test_uf_data_flags_real_vs_pseudo_uf_codes():
    """ufData rows carry a `real` flag: True for a Brazilian UF, False for a COMEX
    special trade pseudo-code (EX/ND/ZN…), which has no state_name. Lets the frontend
    count real UFs (27) instead of inflating the tally (FINDING #4)."""
    df = pd.DataFrame(
        [
            {
                "state_acronym": "SP",
                "state_name": "São Paulo",
                "region_abbrev": "SE",
                "total_value": 5_000_000,
                "q_mass": 0.0,
                "q_vol": 0.0,
            },
            {
                "state_acronym": "EX",
                "state_name": None,  # pseudo trade code — no UF lookup match
                "region_abbrev": None,
                "total_value": 9_000_000,
                "q_mass": 0.0,
                "q_vol": 0.0,
            },
        ]
    )
    rows = s._uf_data(df)
    by_uf = {r["uf"]: r for r in rows}
    assert by_uf["SP"]["real"] is True
    assert by_uf["EX"]["real"] is False


def test_uf_data_null_family_quantity_is_zero():
    # A UF with only mass production: q_vol is NULL/NaN → safe 0.0.
    df = pd.DataFrame(
        [
            {
                "state_acronym": "MT",
                "state_name": "Mato Grosso",
                "region_abbrev": "CO",
                "total_value": 2_000_000,
                "q_mass": 3_000_000,
                "q_vol": float("nan"),
            }
        ]
    )
    uf = s._uf_data(df)[0]
    assert uf["q_mass"] == 3000.0 and uf["q_vol"] == 0.0


def test_quality_uses_real_pt_br_labels():
    df = pd.DataFrame(
        [
            {"data_quality_flag": "INCOMPLETE", "n_rows": 5, "share": 0.1},
            {"data_quality_flag": "MISSING_WEIGHT", "n_rows": 3, "share": 0.06},
        ]
    )
    out = s._quality(df)
    by_id = {r["id"]: r["label"] for r in out}
    assert by_id["INCOMPLETE"] == "Incompleto"  # pt-BR, not the raw English id
    assert by_id["MISSING_WEIGHT"] == "Peso ausente"


def test_serialize_source_meta_carries_latest_year_completeness():
    """serialize_source_meta surfaces the FINDING #3 partial-year signal as camelCase
    JSON the frontend can read for an honest YoY (monthsInLatestYear /
    latestYearComplete / latestCompleteYear)."""
    out = s.serialize_source_meta(
        {
            "source": "mdic_comex",
            "gold_table": "gold_comex_flows",
            "cadence": "monthly",
            "year_start": 1997,
            "year_end": 2026,
            "months_in_latest_year": 5,
            "latest_year_complete": False,
            "latest_complete_year": 2025,
        }
    )
    assert out["monthsInLatestYear"] == 5
    assert out["latestYearComplete"] is False
    assert out["latestCompleteYear"] == 2025


def test_serialize_source_meta_annual_defaults_to_complete():
    """An annual banco (no completeness keys) → latestYearComplete True,
    monthsInLatestYear None (the serializer's safe default)."""
    out = s.serialize_source_meta(
        {"source": "ibge_pevs", "gold_table": "gold_pevs_production", "year_end": 2024}
    )
    assert out["latestYearComplete"] is True
    assert out["monthsInLatestYear"] is None


def test_serialize_source_meta_empty_is_empty_dict():
    assert s.serialize_source_meta(None) == {}
    assert s.serialize_source_meta({}) == {}


def test_serialize_monthly_empty_emits_twelve_values():
    """serialize_monthly must always emit 12 monthlyAvg entries — an empty list
    crashed ViewSeasonality's peak/low/amplitude math."""
    out = s.serialize_monthly(None)
    assert out["monthlyAvg"] == [0.0] * 12
    assert len(out["months"]) == 12 and out["years"] == [] and out["matrix"] == {}
    out_empty_df = s.serialize_monthly(pd.DataFrame())
    assert out_empty_df["monthlyAvg"] == [0.0] * 12
