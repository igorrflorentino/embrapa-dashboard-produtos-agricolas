"""HTTP-layer tests for the ``/api`` blueprint via Flask's ``test_client``.

These sit beneath the pure ``test_webapi_seam`` / ``test_webapi_serializers``
unit tests and exercise the request → auth → JSON contract that nothing else
guards: the curation-write authentication (401) / authorization (403), input
validation (400), the JSON error handler, and the curator allowlist. No
BigQuery — Settings is stubbed and seam functions are monkeypatched.
"""

from __future__ import annotations

import pytest


def _client(monkeypatch, **settings_over):
    pytest.importorskip("flask")
    pytest.importorskip("flask_caching")
    from embrapa_commodities.config import Settings
    from embrapa_commodities.webapi import app as app_mod
    from embrapa_commodities.webapi import auth, routes, seam

    base = {
        "gcp_project_id": "test-project",
        "curation_dev_author": None,
        "iap_audience": None,
        "curation_allowed_emails": "",
    }
    base.update(settings_over)
    # _env_file=None: never read the developer's .env. The auth/allowlist behaviour
    # under test (dev-author fallback, IAP audience, the curator allowlist) is driven
    # entirely by these explicit fields, so a real .env at repo root must not leak in.
    cfg = Settings(_env_file=None, **base)  # type: ignore[arg-type]
    # Auth + allowlist read get_settings from their own module namespaces.
    monkeypatch.setattr(auth, "get_settings", lambda: cfg)
    monkeypatch.setattr(routes, "get_settings", lambda: cfg)
    # Stub the BQ-table curator read empty by default so authorization tests
    # exercise only the env allowlist and never touch BigQuery; the table-backed
    # test overrides this.
    monkeypatch.setattr(seam, "curator_emails", lambda: set())
    # Stub the allowlist-table auto-create so authorization tests never touch
    # BigQuery; the dedicated test overrides this to assert it is invoked.
    monkeypatch.setattr(routes, "ensure_curators_table", lambda: None)
    app = app_mod.create_app()
    app.config.update(TESTING=True)
    return app.test_client()


def test_healthz_ok(monkeypatch):
    client = _client(monkeypatch)
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "ok"}


@pytest.mark.parametrize(
    ("endpoint", "seam_fn", "serialize_fn"),
    [
        ("/api/flow", "flow_data", "serialize_flow"),
        ("/api/partners", "partner_data", "serialize_partner"),
        ("/api/monthly", "monthly_data", "serialize_monthly"),
    ],
)
def test_trade_route_threads_basket_and_year_window_to_seam(
    monkeypatch, endpoint, seam_fn, serialize_fn
):
    """The active-filter params (`codes`/`y0`/`y1`) reach the seam as a summary
    dict — the bug was routes parsing none and passing summary=None, so a basket
    or year window left the trade charts unchanged."""
    from embrapa_commodities.webapi import seam, serializers

    client = _client(monkeypatch)
    captured = {}

    def fake_seam(banco, summary=None):
        captured["banco"] = banco
        captured["summary"] = summary
        return None

    monkeypatch.setattr(seam, seam_fn, fake_seam)
    monkeypatch.setattr(serializers, serialize_fn, lambda *a, **k: {"ok": True})

    resp = client.get(f"{endpoint}?banco=mdic_comex&codes=0801,0802&y0=2018&y1=2022")
    assert resp.status_code == 200
    assert captured["banco"] == "mdic_comex"
    assert captured["summary"] == {
        "basket": ["0801", "0802"],
        "startDate": "2018",
        "endDate": "2022",
    }


def test_trade_route_unfiltered_passes_summary_none(monkeypatch):
    """No filter params → summary is None (the unfiltered default — no behavior
    change for an unfiltered request)."""
    from embrapa_commodities.webapi import seam, serializers

    client = _client(monkeypatch)
    captured = {}

    monkeypatch.setattr(
        seam, "flow_data", lambda banco, summary=None: captured.update(summary=summary)
    )
    monkeypatch.setattr(serializers, "serialize_flow", lambda *a, **k: {})
    resp = client.get("/api/flow?banco=mdic_comex")
    assert resp.status_code == 200
    assert captured["summary"] is None


def test_trade_route_cleared_basket_drops_basket_key(monkeypatch):
    """An empty `codes` param ('basket cleared / all') yields no `basket` key, so
    the seam reads it as "no product filter" rather than "none selected"."""
    from embrapa_commodities.webapi import seam, serializers

    client = _client(monkeypatch)
    captured = {}

    monkeypatch.setattr(
        seam, "partner_data", lambda banco, summary=None: captured.update(summary=summary)
    )
    monkeypatch.setattr(serializers, "serialize_partner", lambda *a, **k: {})
    resp = client.get("/api/partners?banco=mdic_comex&codes=&y0=2020")
    assert resp.status_code == 200
    assert captured["summary"] == {"startDate": "2020"}
    assert "basket" not in captured["summary"]


@pytest.mark.parametrize(
    ("endpoint", "seam_fn", "serialize_fn"),
    [
        ("/api/flow", "flow_data", "serialize_flow"),
        ("/api/partners", "partner_data", "serialize_partner"),
    ],
)
def test_trade_route_threads_origin_uf_filter_to_seam(monkeypatch, endpoint, seam_fn, serialize_fn):
    """The origin-UF (``states``) param reaches the seam as ``summary['states']`` —
    the audit gap was the UF dimension being dropped on the trade origin readers."""
    from embrapa_commodities.webapi import seam, serializers

    client = _client(monkeypatch)
    captured = {}
    monkeypatch.setattr(seam, seam_fn, lambda banco, summary=None: captured.update(summary=summary))
    monkeypatch.setattr(serializers, serialize_fn, lambda *a, **k: {})
    resp = client.get(f"{endpoint}?banco=mdic_comex&states=PA,SP&y0=2020")
    assert resp.status_code == 200
    assert captured["summary"] == {"states": ["PA", "SP"], "startDate": "2020"}


def test_trade_route_no_states_param_omits_states_key(monkeypatch):
    """No ``states`` param → no ``states`` key in the summary (empty = unfiltered,
    the existing convention)."""
    from embrapa_commodities.webapi import seam, serializers

    client = _client(monkeypatch)
    captured = {}
    monkeypatch.setattr(
        seam, "flow_data", lambda banco, summary=None: captured.update(summary=summary)
    )
    monkeypatch.setattr(serializers, "serialize_flow", lambda *a, **k: {})
    resp = client.get("/api/flow?banco=mdic_comex&codes=0801")
    assert resp.status_code == 200
    assert captured["summary"] == {"basket": ["0801"]}
    assert "states" not in captured["summary"]


def test_productivity_route_threads_year_window_not_basket(monkeypatch):
    """ViewProductivity honours the period window (y0/y1) but NOT the product
    basket — the crop selector is its product dimension — so the route passes a
    summary carrying only the year window."""
    from embrapa_commodities.webapi import seam, serializers

    client = _client(monkeypatch)
    captured = {}

    def fake_productivity(banco, crop, summary=None):
        captured.update(banco=banco, crop=crop, summary=summary)
        return None

    monkeypatch.setattr(seam, "productivity", fake_productivity)
    monkeypatch.setattr(serializers, "serialize_productivity", lambda *a, **k: None)
    resp = client.get("/api/productivity?banco=ibge_pam&crop=2713&y0=2010&y1=2020")
    assert resp.status_code == 200
    assert captured["crop"] == "2713"
    assert captured["summary"] == {"startDate": "2010", "endDate": "2020"}


def test_geo_yearly_route_threads_basket_to_seam(monkeypatch):
    """/geo-yearly turns ?codes into the basket summary the seam pushes down to the
    by-UF-yearly mart, and threads currency/correction so the cube's value column
    matches the snapshot's."""
    from embrapa_commodities.webapi import seam, serializers

    client = _client(monkeypatch)
    captured = {}

    def fake_geo_yearly(banco, conv, summary=None):
        captured.update(banco=banco, conv=conv, summary=summary)
        return None

    monkeypatch.setattr(seam, "geo_yearly", fake_geo_yearly)
    monkeypatch.setattr(serializers, "serialize_geo_yearly", lambda *a, **k: {"ufYearly": []})
    resp = client.get(
        "/api/geo-yearly?banco=ibge_pevs&codes=3405,3434&currency=BRL&correction=IPCA"
    )
    assert resp.status_code == 200
    assert resp.get_json() == {"ufYearly": []}
    assert captured["banco"] == "ibge_pevs"
    assert captured["conv"] == {"currency": "BRL", "correction": "IPCA"}
    assert captured["summary"] == {"basket": ["3405", "3434"]}


def test_geo_yearly_route_unfiltered_passes_summary_none(monkeypatch):
    """No ?codes → summary is None (all products), same convention as /snapshot."""
    from embrapa_commodities.webapi import seam, serializers

    client = _client(monkeypatch)
    captured = {}
    monkeypatch.setattr(
        seam, "geo_yearly", lambda banco, conv, summary=None: captured.update(summary=summary)
    )
    monkeypatch.setattr(serializers, "serialize_geo_yearly", lambda *a, **k: {"ufYearly": []})
    resp = client.get("/api/geo-yearly?banco=ibge_pevs")
    assert resp.status_code == 200
    assert captured["summary"] is None


# ── convention validation: invalid currency/correction → 400 (not silent BRL/IPCA) ──


@pytest.mark.parametrize(
    "endpoint",
    ["/api/snapshot", "/api/product-uf", "/api/geo-yearly"],
)
@pytest.mark.parametrize(
    "query",
    [
        "correction=ipca",  # wrong case — keys are case-sensitive exact-match
        "correction=IPC",  # typo
        "currency=brl",  # wrong case
        "currency=GBP",  # unsupported currency
    ],
)
def test_convention_routes_reject_invalid_currency_or_correction(monkeypatch, endpoint, query):
    """An invalid currency/correction must 400 at the route boundary, not silently
    fall back to BRL/IPCA inside monetary_column (which would hand the user the
    wrong deflated series with no signal). Covers all three conv-accepting routes."""
    from embrapa_commodities.webapi import seam

    client = _client(monkeypatch)

    # Make the seam blow up if reached, so the test fails loudly if validation is
    # bypassed and the request is served with a fallback convention.
    def must_not_run(*a, **k):
        raise AssertionError("seam was reached despite an invalid convention")

    monkeypatch.setattr(seam, "snapshot", must_not_run)
    monkeypatch.setattr(seam, "product_uf_ranking", must_not_run)
    monkeypatch.setattr(seam, "geo_yearly", must_not_run)

    resp = client.get(f"{endpoint}?banco=ibge_pevs&code=3405&{query}")
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_convention_route_accepts_valid_non_default_pair(monkeypatch):
    """A valid non-default pair (e.g. USD/IGP-M) passes validation and reaches the
    seam verbatim — the validation only rejects unknown values, not legal ones."""
    from embrapa_commodities.webapi import seam

    client = _client(monkeypatch)
    captured = {}
    monkeypatch.setattr(
        seam, "snapshot", lambda banco, conv, summary: captured.update(conv=conv) or {}
    )
    resp = client.get("/api/snapshot?banco=ibge_pevs&currency=USD&correction=IGP-M")
    assert resp.status_code == 200
    assert captured["conv"] == {"currency": "USD", "correction": "IGP-M"}


# ── GET read endpoints: route → seam → serializer wiring ──────────────────────


def test_catalog_get_returns_seam_payload_as_json(monkeypatch):
    """/catalog jsonifies seam.commodity_catalog() verbatim (no serializer)."""
    from embrapa_commodities.webapi import seam

    client = _client(monkeypatch)
    monkeypatch.setattr(seam, "commodity_catalog", lambda: {"castanha": {"name": "Castanha"}})
    resp = client.get("/api/catalog")
    assert resp.status_code == 200
    assert resp.content_type.startswith("application/json")
    assert resp.get_json() == {"castanha": {"name": "Castanha"}}


def test_source_meta_get_threads_banco_and_shapes_payload(monkeypatch):
    """/source-meta passes ?banco to the seam and returns the serialized shape."""
    from embrapa_commodities.webapi import seam

    client = _client(monkeypatch)
    captured = {}
    monkeypatch.setattr(
        seam, "source_meta", lambda banco: captured.update(banco=banco) or {"source": banco}
    )
    resp = client.get("/api/source-meta?banco=ibge_pevs")
    assert resp.status_code == 200
    assert captured["banco"] == "ibge_pevs"
    assert resp.get_json()["source"] == "ibge_pevs"


def test_source_meta_unknown_banco_returns_empty_object(monkeypatch):
    """An unknown banco yields {} (the seam's honest "no provenance row"), 200."""
    from embrapa_commodities.webapi import seam

    client = _client(monkeypatch)
    monkeypatch.setattr(seam, "source_meta", lambda banco: {})
    resp = client.get("/api/source-meta?banco=does_not_exist")
    assert resp.status_code == 200
    assert resp.get_json() == {}


def test_snapshot_get_threads_banco_and_conventions(monkeypatch):
    """/snapshot forwards banco + the currency/correction conventions to the seam;
    defaults are BRL/IPCA. The empty seam payload still serializes to the full
    BancoSnapshot key set (the contract the SPA reads)."""
    from embrapa_commodities.webapi import seam

    client = _client(monkeypatch)
    captured = {}

    def fake_snapshot(banco, conv, summary):
        captured.update(banco=banco, conv=conv, summary=summary)
        return {}  # serializer fills the empty shape

    monkeypatch.setattr(seam, "snapshot", fake_snapshot)
    resp = client.get("/api/snapshot?banco=mdic_comex&currency=USD&correction=Nominal")
    assert resp.status_code == 200
    assert captured["banco"] == "mdic_comex"
    assert captured["conv"] == {"currency": "USD", "correction": "Nominal"}
    assert captured["summary"] is None
    body = resp.get_json()
    # The serialized snapshot exposes the contract's top-level keys.
    for key in ("products", "productTS", "overviewTS", "ufData", "quality", "preview"):
        assert key in body


def test_snapshot_get_defaults_conventions_to_brl_ipca(monkeypatch):
    from embrapa_commodities.webapi import seam

    client = _client(monkeypatch)
    captured = {}
    monkeypatch.setattr(
        seam, "snapshot", lambda banco, conv, summary: captured.update(conv=conv) or {}
    )
    resp = client.get("/api/snapshot?banco=ibge_pevs")
    assert resp.status_code == 200
    assert captured["conv"] == {"currency": "BRL", "correction": "IPCA"}


def test_product_uf_get_threads_code_conv_and_year_window(monkeypatch):
    """/product-uf forwards code + conventions + the startDate/endDate→summary."""
    from embrapa_commodities.webapi import seam

    client = _client(monkeypatch)
    captured = {}

    def fake_ranking(banco, code, conv, summary):
        captured.update(banco=banco, code=code, conv=conv, summary=summary)
        return None  # serializer → {"uf": []}

    monkeypatch.setattr(seam, "product_uf_ranking", fake_ranking)
    resp = client.get("/api/product-uf?banco=ibge_pevs&code=3405&startDate=2010&endDate=2020")
    assert resp.status_code == 200
    assert captured["code"] == "3405"
    assert captured["conv"] == {"currency": "BRL", "correction": "IPCA"}
    assert captured["summary"] == {"startDate": "2010", "endDate": "2020"}
    assert resp.get_json() == {"uf": []}


def test_product_uf_get_no_year_window_passes_summary_none(monkeypatch):
    from embrapa_commodities.webapi import seam

    client = _client(monkeypatch)
    captured = {}
    monkeypatch.setattr(
        seam,
        "product_uf_ranking",
        lambda banco, code, conv, summary: captured.update(summary=summary),
    )
    resp = client.get("/api/product-uf?banco=ibge_pevs&code=3405")
    assert resp.status_code == 200
    assert captured["summary"] is None


def test_productivity_get_defaults_crop_to_none(monkeypatch):
    """No ?crop → seam receives crop=None (it picks the first crop)."""
    from embrapa_commodities.webapi import seam

    client = _client(monkeypatch)
    captured = {}
    monkeypatch.setattr(
        seam,
        "productivity",
        lambda banco, crop, summary: captured.update(crop=crop, summary=summary),
    )
    resp = client.get("/api/productivity?banco=ibge_pam")
    assert resp.status_code == 200
    assert captured["crop"] is None
    assert captured["summary"] is None
    # None payload serializes to JSON null (the view's honest empty-state).
    assert resp.get_json() is None


def test_cross_series_get_coerces_year_bounds_to_int(monkeypatch):
    """y0/y1 use Flask's type=int coercion — the seam must receive ints, not the
    raw query strings (the comparable-window math is integer year arithmetic)."""
    from embrapa_commodities.webapi import seam

    client = _client(monkeypatch)
    captured = {}

    def fake_series(banco, metric, y0, y1):
        captured.update(banco=banco, metric=metric, y0=y0, y1=y1)
        return None  # serialize_cross_series(None) → None

    monkeypatch.setattr(seam, "cross_series", fake_series)
    resp = client.get("/api/cross/series?banco=mdic_comex&metric=exp_value&y0=2018&y1=2022")
    assert resp.status_code == 200
    assert captured["metric"] == "exp_value"
    assert captured["y0"] == 2018 and captured["y1"] == 2022
    assert isinstance(captured["y0"], int) and isinstance(captured["y1"], int)


def test_cross_series_get_missing_year_bounds_are_none(monkeypatch):
    from embrapa_commodities.webapi import seam

    client = _client(monkeypatch)
    captured = {}
    monkeypatch.setattr(
        seam,
        "cross_series",
        lambda banco, metric, y0, y1: captured.update(y0=y0, y1=y1),
    )
    resp = client.get("/api/cross/series?banco=mdic_comex&metric=exp_value")
    assert resp.status_code == 200
    assert captured["y0"] is None and captured["y1"] is None


def test_cross_metric_refs_get_returns_seam_list(monkeypatch):
    from embrapa_commodities.webapi import seam

    client = _client(monkeypatch)
    monkeypatch.setattr(
        seam, "cross_metric_refs", lambda: [{"banco": "mdic_comex", "metric": "exp_value"}]
    )
    resp = client.get("/api/cross/metric-refs")
    assert resp.status_code == 200
    assert resp.get_json() == [{"banco": "mdic_comex", "metric": "exp_value"}]


@pytest.mark.parametrize(
    ("endpoint", "seam_fn", "top_keys"),
    [
        (
            "/api/cross/export-coef",
            "export_coefficient",
            ("unit", "byUf", "national", "timeseries"),
        ),
        ("/api/cross/market-share", "market_share", ("unit", "series", "byProduct")),
        ("/api/cross/price-spread", "price_spread", ("unit", "series")),
        ("/api/cross/mirror", "trade_mirror", ("unit", "series", "discrepancy")),
        ("/api/cross/value-added", "value_added", ("years", "byLevel", "series", "nCodes")),
        ("/api/cross/market-nature", "market_nature", ("years", "series", "latest")),
    ],
)
def test_cross_analytics_get_threads_commodity_and_shapes_payload(
    monkeypatch, endpoint, seam_fn, top_keys
):
    """Each cross-analytics GET forwards ?commodity to the seam and returns the
    serialized contract shape (an empty seam dict still yields all the keys)."""
    from embrapa_commodities.webapi import seam

    client = _client(monkeypatch)
    captured = {}
    monkeypatch.setattr(seam, seam_fn, lambda commodity: captured.update(commodity=commodity) or {})
    resp = client.get(f"{endpoint}?commodity=castanha")
    assert resp.status_code == 200
    assert captured["commodity"] == "castanha"
    body = resp.get_json()
    for key in top_keys:
        assert key in body
    assert body["preview"] is False


@pytest.mark.parametrize(
    "endpoint",
    [
        "/api/cross/export-coef",
        "/api/cross/market-share",
        "/api/cross/price-spread",
        "/api/cross/mirror",
        "/api/cross/value-added",
        "/api/cross/market-nature",
    ],
)
def test_cross_analytics_get_unknown_commodity_passes_none(monkeypatch, endpoint):
    """No ?commodity → the seam receives None (all-commodities), 200; a blank
    ?commodity= is also normalized to None (the route's `or None`)."""
    from embrapa_commodities.webapi import seam

    client = _client(monkeypatch)
    captured = {}
    seam_fn = endpoint.rsplit("/", 1)[1].replace("-", "_")
    name = {
        "export_coef": "export_coefficient",
        "market_share": "market_share",
        "price_spread": "price_spread",
        "mirror": "trade_mirror",
        "value_added": "value_added",
        "market_nature": "market_nature",
    }[seam_fn]
    monkeypatch.setattr(seam, name, lambda commodity: captured.update(commodity=commodity) or {})
    resp = client.get(f"{endpoint}?commodity=")  # blank → None
    assert resp.status_code == 200
    assert captured["commodity"] is None


def test_trade_get_endpoints_shape_empty_seam_payload(monkeypatch):
    """/flow, /partners, /monthly serialize a None/empty seam result into the
    contract's empty shape (the views' loading/empty-state math depends on it —
    notably /monthly must emit 12 monthlyAvg values, never [])."""
    from embrapa_commodities.webapi import seam

    client = _client(monkeypatch)
    monkeypatch.setattr(seam, "flow_data", lambda banco, summary=None: None)
    monkeypatch.setattr(seam, "partner_data", lambda banco, summary=None: None)
    monkeypatch.setattr(seam, "monthly_data", lambda banco, summary=None: None)

    flow = client.get("/api/flow?banco=mdic_comex").get_json()
    assert flow["nodes"] == [] and flow["links"] == []

    partners = client.get("/api/partners?banco=mdic_comex").get_json()
    assert partners["partners"] == []

    monthly = client.get("/api/monthly?banco=mdic_comex").get_json()
    assert monthly["monthlyAvg"] == [0.0] * 12  # 12-value contract, even when empty


def test_curation_worklist_get_returns_seam_payload(monkeypatch):
    from embrapa_commodities.webapi import seam

    client = _client(monkeypatch)
    monkeypatch.setattr(
        seam, "curation_worklist", lambda: {"rows": [], "total": 0, "classified": 0}
    )
    resp = client.get("/api/curation/worklist")
    assert resp.status_code == 200
    assert resp.get_json() == {"rows": [], "total": 0, "classified": 0}


def test_curation_flow_worklist_get_returns_seam_payload(monkeypatch):
    from embrapa_commodities.webapi import seam

    client = _client(monkeypatch)
    monkeypatch.setattr(
        seam, "flow_market_worklist", lambda: {"customs": [], "flows": [], "cells": []}
    )
    resp = client.get("/api/curation/flow-worklist")
    assert resp.status_code == 200
    assert resp.get_json() == {"customs": [], "flows": [], "cells": []}


def test_get_endpoint_error_returns_json_500_not_html(monkeypatch):
    """A read endpoint that raises returns parseable JSON 500 (the SPA fetch layer
    can't recover from Flask's default HTML 500). Pins the handler for the GET
    surface, not just /catalog."""
    from embrapa_commodities.webapi import seam

    client = _client(monkeypatch)

    def boom(*a, **k):
        raise RuntimeError("BigQuery exploded")

    monkeypatch.setattr(seam, "snapshot", boom)
    resp = client.get("/api/snapshot?banco=ibge_pevs")
    assert resp.status_code == 500
    assert resp.content_type.startswith("application/json")
    assert resp.get_json()["error"] == "internal server error"


def test_unknown_api_get_path_is_json_404(monkeypatch):
    """An unregistered /api GET path returns the pt-BR JSON 404, never the SPA's
    index.html with a 200 (which would burn the client's retry budget on a parse
    error)."""
    client = _client(monkeypatch)
    resp = client.get("/api/not-a-real-endpoint")
    assert resp.status_code == 404
    assert resp.content_type.startswith("application/json")
    assert resp.get_json()["error"] == "endpoint de API não encontrado"


def test_curation_post_without_identity_is_401(monkeypatch):
    """No IAP header + no dev fallback → MissingAuthorError → 401 JSON (never writes)."""
    client = _client(monkeypatch)  # curation_dev_author=None, iap_audience=None
    resp = client.post(
        "/api/curation/code-level", json={"source": "x", "code": "1", "level": "bruta"}
    )
    assert resp.status_code == 401
    assert "error" in resp.get_json()


def test_curation_post_missing_fields_is_400(monkeypatch):
    """Authenticated (dev fallback) but an incomplete body → 400 before any write."""
    client = _client(monkeypatch, curation_dev_author="dev@embrapa.br")
    resp = client.post("/api/curation/code-level", json={"source": "x"})  # no code/level
    assert resp.status_code == 400


def test_curation_post_not_in_allowlist_is_403(monkeypatch):
    """A real identity that is NOT on the curator allowlist → 403 (authorization)."""
    client = _client(
        monkeypatch,
        curation_dev_author="intruder@embrapa.br",
        curation_allowed_emails="curator@embrapa.br",
    )
    resp = client.post(
        "/api/curation/code-level",
        json={"source": "x", "code": "1", "level": "bruta"},
    )
    assert resp.status_code == 403


def test_curation_post_invalid_iap_assertion_is_403(monkeypatch):
    """An audience is configured but no signed JWT is present → InvalidIapAssertion → 403."""
    client = _client(monkeypatch, iap_audience="/projects/1/global/backendServices/2")
    resp = client.post(
        "/api/curation/code-level",
        json={"source": "x", "code": "1", "level": "bruta"},
    )
    assert resp.status_code == 403


def test_api_error_handler_returns_json_not_html(monkeypatch):
    """An unhandled error in a read endpoint returns parseable JSON (so the SPA's
    fetch layer doesn't choke on Flask's default HTML 500 and retry-loop)."""
    client = _client(monkeypatch)
    from embrapa_commodities.webapi import seam

    def boom():
        raise RuntimeError("BigQuery exploded")

    monkeypatch.setattr(seam, "commodity_catalog", boom)
    resp = client.get("/api/catalog")
    assert resp.status_code == 500
    assert resp.content_type.startswith("application/json")
    assert resp.get_json()["error"] == "internal server error"


def test_curation_post_authorized_via_bq_curators_table(monkeypatch):
    """An author absent from the ENV allowlist but present in the Console-managed
    BQ curators table is authorized — the effective allowlist is their UNION."""
    from embrapa_commodities.webapi import seam

    # Env allowlist names someone else; the author is only in the BQ table.
    client = _client(
        monkeypatch,
        curation_dev_author="researcher@embrapa.br",
        curation_allowed_emails="someone.else@embrapa.br",
    )
    monkeypatch.setattr(seam, "curator_emails", lambda: {"researcher@embrapa.br"})
    monkeypatch.setattr(seam, "record_code_level", lambda *a, **k: {"ok": True, "deduped": False})
    resp = client.post(
        "/api/curation/code-level",
        json={"source": "x", "code": "1", "level": "bruta"},
    )
    assert resp.status_code == 200
    assert resp.get_json()["ok"] is True


def test_curation_post_forwards_change_id_to_seam(monkeypatch):
    """The client-supplied idempotency key reaches the seam writer verbatim."""
    from embrapa_commodities.webapi import seam

    client = _client(monkeypatch, curation_dev_author="researcher@embrapa.br")
    captured = {}

    def fake_record(source, code, level, change_id=None):
        captured.update(source=source, code=code, level=level, change_id=change_id)
        return {"deduped": False, "change_id": change_id}

    monkeypatch.setattr(seam, "record_code_level", fake_record)
    resp = client.post(
        "/api/curation/code-level",
        json={"source": "mdic_comex", "code": "0801", "level": "bruta", "change_id": "k-42"},
    )
    assert resp.status_code == 200
    assert captured["change_id"] == "k-42"


def test_curation_post_overlong_input_is_400_not_500(monkeypatch):
    """A ValueError from the serving writer (e.g. an over-length level the curation
    writer caps) is a client fault → HTTP 400 with a pt-BR message, not a 500."""
    from embrapa_commodities.webapi import seam

    client = _client(monkeypatch, curation_dev_author="researcher@embrapa.br")

    def raise_overlong(*a, **k):
        raise ValueError("industrialization_level exceeds 200 chars.")

    monkeypatch.setattr(seam, "record_code_level", raise_overlong)
    resp = client.post(
        "/api/curation/code-level",
        json={"source": "x", "code": "1", "level": "y" * 300},
    )
    assert resp.status_code == 400
    body = resp.get_json()
    assert "error" in body
    # End-user message must be pt-BR (not the internal English ValueError text).
    assert "Dados inválidos" in body["error"]
    assert "exceeds" not in body["error"]


def test_flow_market_post_overlong_market_is_400_not_500(monkeypatch):
    """The second writer's over-length validation also maps to 400 (the route only
    presence-checks; length is enforced in the serving writer)."""
    from embrapa_commodities.webapi import seam

    client = _client(monkeypatch, curation_dev_author="researcher@embrapa.br")

    def raise_overlong(*a, **k):
        raise ValueError("market exceeds 200 chars.")

    monkeypatch.setattr(seam, "record_flow_market", raise_overlong)
    resp = client.post(
        "/api/curation/flow-market",
        json={"customs_code": "4", "flow_code": "1", "market": "m" * 300},
    )
    assert resp.status_code == 400
    assert "Dados inválidos" in resp.get_json()["error"]


def test_curation_post_auto_creates_curators_allowlist_table(monkeypatch):
    """First authorization check self-heals the Console-managed allowlist table so
    the runbook's documented INSERT path is real (auto-creates on first use)."""
    from embrapa_commodities.webapi import routes, seam

    client = _client(monkeypatch, curation_dev_author="researcher@embrapa.br")
    called = {"n": 0}
    monkeypatch.setattr(routes, "ensure_curators_table", lambda: called.__setitem__("n", 1))
    monkeypatch.setattr(seam, "record_code_level", lambda *a, **k: {"deduped": False})

    resp = client.post(
        "/api/curation/code-level",
        json={"source": "x", "code": "1", "level": "bruta"},
    )
    assert resp.status_code == 200
    assert called["n"] == 1


def test_auto_create_curators_failure_does_not_block_write(monkeypatch):
    """A transient BQ/permission fault while ensuring the allowlist table must not
    block an otherwise-authorized write (best-effort; empty table = open mode)."""
    from embrapa_commodities.webapi import routes, seam

    client = _client(monkeypatch, curation_dev_author="researcher@embrapa.br")

    def boom():
        raise RuntimeError("BQ down")

    monkeypatch.setattr(routes, "ensure_curators_table", boom)
    monkeypatch.setattr(seam, "record_code_level", lambda *a, **k: {"deduped": False})
    resp = client.post(
        "/api/curation/code-level",
        json={"source": "x", "code": "1", "level": "bruta"},
    )
    assert resp.status_code == 200


# ── JSON sanitization: numpy scalars + datetimes round-trip (no 500) ──────────


def test_response_with_numpy_scalars_and_dates_serializes_to_valid_json(monkeypatch):
    """A seam payload carrying numpy.integer/floating/bool_ + date/Timestamp (the
    shapes that reach serialization straight off a pandas DataFrame, e.g.
    /source-meta maturityDate/cobertura) round-trips through SafeJSONProvider to
    valid JSON instead of 500-ing on an un-coerced field."""
    import datetime

    import numpy as np
    import pandas as pd

    from embrapa_commodities.webapi import seam

    client = _client(monkeypatch)
    monkeypatch.setattr(
        seam,
        "commodity_catalog",
        lambda: {
            "count": np.int64(7),
            "ratio": np.float64(1.5),
            "flag": np.bool_(True),
            "nan": np.float64("nan"),
            "maturityDate": datetime.date(2026, 6, 16),
            "lastRefresh": pd.Timestamp("2026-06-16T12:30:00"),
        },
    )
    resp = client.get("/api/catalog")
    assert resp.status_code == 200
    assert resp.content_type.startswith("application/json")
    body = resp.get_json()  # parses → confirms no bare NaN/unserializable type leaked
    assert body["count"] == 7 and isinstance(body["count"], int)
    assert body["ratio"] == 1.5
    assert body["flag"] is True
    assert body["nan"] is None  # NaN → null (invalid-JSON literal avoided)
    assert body["maturityDate"] == "2026-06-16"
    assert body["lastRefresh"].startswith("2026-06-16T12:30:00")
