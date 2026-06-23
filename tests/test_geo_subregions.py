"""Unit tests for the sub-UF + live-município geography backend.

Covers the new serving SQL builders (município cube + the IBGE mesh universe), the
serializers (city-grain scaling + the mesh shape), the seam threading, and the
gateway gating that keeps COMEX/COMTRADE out of the município cube. Pure-ish: the
gateway is monkeypatched, so no BigQuery.
"""

from __future__ import annotations

import pandas as pd
import pytest

from embrapa_commodities.serving import sql as sqlbuild


def _seam():
    pytest.importorskip("flask_caching")
    from embrapa_commodities.webapi import seam

    return seam


def _bind_simplecache():
    from flask import Flask

    from embrapa_commodities.serving.cache import cache

    app = Flask(__name__)
    cache.init_app(app, config={"CACHE_TYPE": "SimpleCache", "CACHE_DEFAULT_TIMEOUT": 300})
    return app, cache


# ── SQL builders ───────────────────────────────────────────────────────────────
def test_production_by_municipio_yearly_groups_by_city_code():
    sql, params = sqlbuild.production_by_municipio_yearly(
        "proj.gold.gold_pevs_production",
        year_start=2000,
        year_end=2020,
        product_codes=("3405", "3409"),
        value_column="val_real_ipca_brl",
    )
    assert "group by city_code, state_acronym, reference_year" in sql
    assert "val_real_ipca_brl" in sql
    # family-split quantities (only summed within a family)
    assert "q_mass" in sql and "q_vol" in sql and "q_count" in sql
    # basket + year window are bound as params (no interpolation of user values)
    assert any(getattr(p, "name", "") == "product_codes" for p in params)


def test_production_by_municipio_yearly_scopes_to_city_codes():
    # city_codes is the cost control: the client passes the narrowed selection's
    # município codes so Gold is scanned for only those cities (bound as an array param).
    sql, params = sqlbuild.production_by_municipio_yearly(
        "proj.gold.gold_pevs_production", city_codes=("1100015", "1100023")
    )
    assert "city_code IN UNNEST(@city_codes)" in sql
    assert any(getattr(p, "name", "") == "city_codes" for p in params)


def test_production_by_municipio_yearly_rejects_bad_value_column():
    with pytest.raises(ValueError):
        sqlbuild.production_by_municipio_yearly(
            "proj.gold.gold_pevs_production", value_column="val; drop table"
        )


def test_geo_municipio_mesh_selects_both_divisions():
    sql, params = sqlbuild.geo_municipio_mesh("proj.gold.dim_geo_municipio")
    assert params == []
    # classic + 2017 divisions both present
    for col in ("meso_code", "micro_code", "intermediaria_code", "imediata_code", "city_code"):
        assert col in sql


# ── Serializers ──────────────────────────────────────────────────────────────
def test_serialize_municipio_yearly_scales_like_uf_cube():
    from embrapa_commodities.webapi import serializers

    df = pd.DataFrame(
        [
            {
                "reference_year": 2023,
                "city_code": "1500602",
                "state_acronym": "PA",
                "total_value": 5e6,
                "q_mass": 2e3,
                "q_vol": 1e6,
                "q_count": 3e6,
            }
        ]
    )
    out = serializers.serialize_municipio_yearly(df)["municipioYearly"]
    assert out[0]["cityCode"] == "1500602"
    assert out[0]["uf"] == "PA"
    assert out[0]["value"] == 5.0  # ÷1e6 → mi
    assert out[0]["q_mass"] == 2.0  # ÷1e3 → mil t
    assert out[0]["q_vol"] == 1.0  # ÷1e6 → mi m³
    assert out[0]["q_count"] == 3.0  # ÷1e6 → mi un


def test_serialize_municipio_yearly_empty():
    from embrapa_commodities.webapi import serializers

    assert serializers.serialize_municipio_yearly(None) == {"municipioYearly": []}


def test_serialize_geo_mesh_shape_and_blank_levels():
    from embrapa_commodities.webapi import serializers

    df = pd.DataFrame(
        [
            {
                "city_code": "3550308",
                "city_name": "São Paulo",
                "state_acronym": "SP",
                "region_abbrev": "SE",
                "meso_code": "3515",
                "meso_name": "Metropolitana de São Paulo",
                "micro_code": "35061",
                "micro_name": "São Paulo",
                "intermediaria_code": "3501",
                "intermediaria_name": "São Paulo",
                "imediata_code": "350001",
                "imediata_name": "São Paulo",
            },
            # a post-classic município: blank meso/micro must serialize to {code:'',name:''}
            {
                "city_code": "5101837",
                "city_name": "Boa Esperança do Norte",
                "state_acronym": "MT",
                "region_abbrev": "CO",
                "meso_code": "",
                "meso_name": "",
                "micro_code": "",
                "micro_name": "",
                "intermediaria_code": "5103",
                "intermediaria_name": "Sinop",
                "imediata_code": "510008",
                "imediata_name": "Sinop",
            },
        ]
    )
    out = serializers.serialize_geo_mesh(df)["municipios"]
    sp = out[0]
    assert sp["meso"] == {"code": "3515", "name": "Metropolitana de São Paulo"}
    assert sp["imediata"]["code"] == "350001"
    boa = out[1]
    assert boa["meso"] == {"code": "", "name": ""}  # no classic division
    assert boa["intermediaria"]["code"] == "5103"  # but has the 2017 one
    assert boa["uf"] == "MT"


# ── Seam threading + gateway gating ──────────────────────────────────────────
def test_geo_municipio_yearly_threads_basket_to_gateway(monkeypatch):
    seam = _seam()
    captured = {}

    def fake(**k):
        captured.update(k)
        return pd.DataFrame()

    monkeypatch.setattr(seam.gateway, "fetch_production_by_municipio_yearly", fake)
    seam.geo_municipio_yearly(
        "ibge_pevs", {"currency": "BRL", "correction": "IPCA"}, {"basket": ["3405"]}
    )
    assert captured["product_codes"] == ("3405",)
    assert captured["source"] == "ibge_pevs"


def test_geo_municipio_yearly_none_for_non_geo_banco():
    seam = _seam()
    # COMTRADE is international (no UF/município grain) → the seam returns None before
    # ever calling the gateway.
    assert (
        seam.geo_municipio_yearly("un_comtrade", {"currency": "USD", "correction": "Nominal"}, None)
        is None
    )


def test_municipio_cube_gateway_skips_non_municipal_source():
    pytest.importorskip("flask_caching")
    from embrapa_commodities.serving import gateway

    app, _ = _bind_simplecache()
    with app.app_context():
        # mdic_comex is UF-origin only — no município cube, returns None WITHOUT a query.
        assert gateway.fetch_production_by_municipio_yearly(source="mdic_comex") is None


def test_municipio_cube_gateway_requires_city_codes():
    # Cost guard (audit D): the cube is ALWAYS city-scoped, so an empty city set returns
    # None WITHOUT a query — never a full ~146k-row município grid scan.
    pytest.importorskip("flask_caching")
    from embrapa_commodities.serving import gateway

    app, _ = _bind_simplecache()
    with app.app_context():
        assert (
            gateway.fetch_production_by_municipio_yearly(source="ibge_pevs", city_codes=()) is None
        )


def test_geo_readers_degrade_to_none_on_missing_table(monkeypatch):
    # A missing dim_geo_municipio / Gold table raises NotFound; the seam must degrade to
    # None (→ serializer empty payload), NOT let it 500 the geography menu (audit C).
    from google.api_core.exceptions import NotFound

    seam = _seam()

    def boom(*a, **k):
        raise NotFound("table not built")

    monkeypatch.setattr(seam.gateway, "fetch_geo_municipio_mesh", boom)
    monkeypatch.setattr(seam.gateway, "fetch_production_by_municipio_yearly", boom)
    assert seam.geo_mesh() is None
    assert (
        seam.geo_municipio_yearly(
            "ibge_pevs", {"currency": "BRL", "correction": "IPCA"}, {"cityCodes": ["1"]}
        )
        is None
    )
