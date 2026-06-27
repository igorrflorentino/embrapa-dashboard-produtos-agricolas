"""Tests for the dashboard data-access layer (src/embrapa_commodities/serving).

The pure modules (iap, sql) are tested directly. The cache/gateway/curation
tests guard on the optional ``flask-caching`` extra and mock BigQuery — they
never touch a live warehouse.
"""

from __future__ import annotations

from datetime import UTC
from unittest import mock

import pytest
from google.cloud import bigquery

from embrapa_commodities.config import Settings
from embrapa_commodities.serving import iap, sql


def _isolated_settings(**over) -> Settings:
    """Construct a Settings hermetically — never read the developer's .env.

    Settings has ``model_config env_file=".env"`` and the documented dev setup
    (``cp .env.example .env``) drops a real .env at repo root, so any field not
    passed here would otherwise be read from it. Several assertions in this file
    depend on default values (the literal serving/gold dataset names, the comtrade
    reporter ISO, the mart-vs-classification TTL ordering), so a dev who set e.g.
    ``BQ_SERVING_DATASET`` or ``CACHE_DEFAULT_TIMEOUT`` in .env would otherwise see
    spurious failures (or worse, spurious passes masking a regression). Pinning
    ``_env_file=None`` makes the defaults authoritative.
    """
    over.setdefault("gcp_project_id", "p")
    return Settings(_env_file=None, **over)  # type: ignore[call-arg]


@pytest.fixture(autouse=True)
def _restore_classification_ttls():
    """Restore the gateway readers' writable ``cache_timeout`` after each test.

    ``init_cache`` / ``_bind_classification_ttl`` mutate the ``cache_timeout``
    attribute of three module-level memoized singletons (the curation reads + the
    curator allowlist). The TTL-binding tests call ``init_cache`` with a non-default
    value, so without teardown they leave the singleton pinned to that value,
    leaking into every later test (e.g. ``test_classification_cache_uses_short_ttl``
    would see a stray TTL). Snapshot before, restore after — independent of import
    order or which test ran. Skipped when flask-caching is absent (gateway won't
    import).
    """
    try:
        from embrapa_commodities.serving import gateway
    except Exception:
        yield
        return
    names = (
        "fetch_current_code_industrialization",
        "fetch_current_flow_market",
        "fetch_curators",
    )
    saved = {n: getattr(gateway, n).cache_timeout for n in names}
    try:
        yield
    finally:
        for n, value in saved.items():
            getattr(gateway, n).cache_timeout = value


# ── iap: author email parsing ─────────────────────────────────────────────────


def test_author_email_strips_iap_issuer_prefix():
    headers = {iap.IAP_EMAIL_HEADER: "accounts.google.com:alice@embrapa.br"}
    assert iap.author_email_from_headers(headers) == "alice@embrapa.br"


def test_author_email_without_prefix():
    headers = {iap.IAP_EMAIL_HEADER: "bob@embrapa.br"}
    assert iap.author_email_from_headers(headers) == "bob@embrapa.br"


def test_author_email_case_insensitive_lookup():
    headers = {"x-goog-authenticated-user-email": "accounts.google.com:carol@embrapa.br"}
    assert iap.author_email_from_headers(headers) == "carol@embrapa.br"


def test_author_email_dev_fallback_used_when_absent():
    assert iap.author_email_from_headers({}, dev_fallback="dev@local") == "dev@local"


def test_author_email_missing_raises():
    with pytest.raises(iap.MissingAuthorError):
        iap.author_email_from_headers({})


def test_author_email_empty_email_after_prefix_raises():
    # IAP issuer prefix with no email after the colon — must not write "" as author.
    headers = {iap.IAP_EMAIL_HEADER: "accounts.google.com:"}
    with pytest.raises(iap.MissingAuthorError):
        iap.author_email_from_headers(headers)


def test_author_email_empty_after_prefix_uses_dev_fallback():
    headers = {iap.IAP_EMAIL_HEADER: "accounts.google.com:"}
    assert iap.author_email_from_headers(headers, dev_fallback="dev@local") == "dev@local"


def test_author_email_whitespace_only_email_raises():
    headers = {iap.IAP_EMAIL_HEADER: "accounts.google.com:   "}
    with pytest.raises(iap.MissingAuthorError):
        iap.author_email_from_headers(headers)


def test_author_email_whitespace_only_uses_dev_fallback():
    headers = {iap.IAP_EMAIL_HEADER: "accounts.google.com:   "}
    assert iap.author_email_from_headers(headers, dev_fallback="dev@local") == "dev@local"


# ── iap: signed JWT assertion verification (H4) ───────────────────────────────


def test_verify_iap_jwt_returns_verified_email(monkeypatch):
    """A valid assertion yields the verified 'email' claim (network mocked)."""
    seen = {}

    def fake_verify(token, request, *, audience, certs_url):
        seen["token"] = token
        seen["audience"] = audience
        seen["certs_url"] = certs_url
        return {"email": "verified@embrapa.br", "sub": "123", "iss": iap.IAP_ISSUER}

    monkeypatch.setattr("google.oauth2.id_token.verify_token", fake_verify)
    headers = {iap.IAP_JWT_HEADER: "signed.jwt.token"}

    email = iap.verify_iap_jwt(headers, audience="/projects/1/global/backendServices/9")

    assert email == "verified@embrapa.br"
    assert seen["token"] == "signed.jwt.token"
    assert seen["audience"] == "/projects/1/global/backendServices/9"
    assert seen["certs_url"] == iap.IAP_CERTS_URL


def test_verify_iap_jwt_missing_header_raises():
    with pytest.raises(iap.InvalidIapAssertionError):
        iap.verify_iap_jwt({}, audience="aud")


def test_verify_iap_jwt_invalid_signature_raises(monkeypatch):
    def boom(*a, **k):
        raise ValueError("Token signature is invalid")

    monkeypatch.setattr("google.oauth2.id_token.verify_token", boom)
    headers = {iap.IAP_JWT_HEADER: "tampered.jwt.token"}
    with pytest.raises(iap.InvalidIapAssertionError):
        iap.verify_iap_jwt(headers, audience="aud")


def test_verify_iap_jwt_without_email_claim_raises(monkeypatch):
    monkeypatch.setattr(
        "google.oauth2.id_token.verify_token",
        lambda *a, **k: {"sub": "123", "iss": iap.IAP_ISSUER},
    )
    headers = {iap.IAP_JWT_HEADER: "valid.but.no.email"}
    with pytest.raises(iap.InvalidIapAssertionError):
        iap.verify_iap_jwt(headers, audience="aud")


def test_verify_iap_jwt_wrong_issuer_raises(monkeypatch):
    """A validly-signed token minted for a different Google product (wrong iss) is
    rejected — verify_token checks signature/aud/exp but not the issuer."""
    monkeypatch.setattr(
        "google.oauth2.id_token.verify_token",
        lambda *a, **k: {"email": "x@embrapa.br", "iss": "https://accounts.google.com"},
    )
    headers = {iap.IAP_JWT_HEADER: "signed.but.wrong.issuer"}
    with pytest.raises(iap.InvalidIapAssertionError):
        iap.verify_iap_jwt(headers, audience="aud")


def test_author_email_prefers_verified_jwt_when_audience_set(monkeypatch):
    """With audience set, the spoofable plaintext header is ignored; JWT wins."""
    monkeypatch.setattr(
        "google.oauth2.id_token.verify_token",
        lambda *a, **k: {"email": "real@embrapa.br", "iss": iap.IAP_ISSUER},
    )
    headers = {
        iap.IAP_JWT_HEADER: "signed.jwt",
        # An attacker-supplied plaintext header — must NOT be trusted.
        iap.IAP_EMAIL_HEADER: "accounts.google.com:attacker@evil.com",
    }
    assert iap.author_email_from_headers(headers, audience="aud") == "real@embrapa.br"


def test_author_email_with_audience_rejects_missing_jwt():
    # Audience configured but no signed assertion present → hard failure, never
    # falls through to the (spoofable) plaintext header or the dev fallback.
    headers = {iap.IAP_EMAIL_HEADER: "accounts.google.com:attacker@evil.com"}
    with pytest.raises(iap.InvalidIapAssertionError):
        iap.author_email_from_headers(headers, audience="aud", dev_fallback="dev@local")


def test_author_email_without_audience_uses_plaintext_dev_path(monkeypatch):
    # Dev path (no audience): the JWT verifier must not even be invoked.
    def fail(*a, **k):  # pragma: no cover - asserts it is never called
        raise AssertionError("verify_token must not be called without an audience")

    monkeypatch.setattr("google.oauth2.id_token.verify_token", fail)
    headers = {iap.IAP_EMAIL_HEADER: "accounts.google.com:dev@embrapa.br"}
    assert iap.author_email_from_headers(headers) == "dev@embrapa.br"


# ── sql: parameterized builders ───────────────────────────────────────────────


def test_production_overview_builds_year_and_product_filters():
    query, params = sql.production_overview(
        "p.serving.serving_pevs_annual",
        year_start=2000,
        year_end=2020,
        product_codes=("3405", "3435"),
        value_column="val_real_ipca_brl",
    )
    assert "sum(val_real_ipca_brl) as total_value" in query
    assert "reference_year >= @year_start" in query
    assert "product_code in unnest(@product_codes)" in query.lower()
    by_name = {p.name: p for p in params}
    assert by_name["year_start"].value == 2000
    assert by_name["year_end"].value == 2020
    assert by_name["product_codes"].values == ["3405", "3435"]


def test_production_overview_no_filters_has_no_where():
    query, params = sql.production_overview("p.serving.serving_pevs_annual")
    assert "where" not in query.lower()
    assert params == []


def test_value_column_allowlist_blocks_injection():
    # An identifier can't be a bind param, so it must be allowlisted, not escaped.
    with pytest.raises(ValueError, match="not allowed"):
        sql.production_overview(
            "p.serving.serving_pevs_annual",
            value_column="val_real_ipca_brl; drop table gold_pevs_production",
        )


def test_filter_column_allowlist_blocks_injection():
    # The filter COLUMN is an identifier too (not bindable), so _in_array must
    # allowlist it. Builders pass a literal today; this guards a future caller
    # from interpolating a user-derived column. Filter VALUES are always bound.
    conditions: list[str] = []
    params: list = []
    with pytest.raises(ValueError, match="not allowed"):
        sql._in_array(conditions, params, "product_code); drop table x; --", "p", ("3405",))
    # An allowed column still builds the bound IN-clause...
    sql._in_array(conditions, params, "product_code", "product_codes", ("3405",))
    assert "product_code in unnest(@product_codes)" in conditions[0].lower()
    # ...and an empty value list stays a no-op (nothing interpolated, nothing to guard).
    sql._in_array(conditions, params, "ncm_code", "ncm_codes", ())
    assert len(conditions) == 1


def test_months_present_per_year_counts_distinct_months():
    """The partial-latest-year signal source: distinct months per year from the
    monthly mart (a year with < 12 months is partial)."""
    query, params = sql.months_present_per_year("p.serving.serving_comex_seasonality")
    low = query.lower()
    assert "count(distinct reference_month) as n_months" in low
    assert "group by reference_year" in low
    assert params == []


def test_current_code_industrialization_filters_is_current():
    query, params = sql.current_code_industrialization("p.serving.dim_code_industrialization_scd2")
    assert "where is_current" in query.lower()
    assert "industrialization_level" in query.lower()
    assert "source" in query.lower()
    assert params == []


def test_table_ref_builds_fqn():
    settings = _isolated_settings(gcp_project_id="my-proj", bq_serving_dataset="serving")
    assert (
        sql.table_ref(settings, "bq_serving_dataset", "serving_pevs_annual")
        == "my-proj.serving.serving_pevs_annual"
    )


def test_production_by_uf_groups_by_state():
    query, params = sql.production_by_uf(
        "p.serving.serving_pevs_annual",
        year_start=2010,
        product_codes=("3405",),
        value_column="val_yearfx_usd",
    )
    assert "group by state_acronym" in query
    assert "sum(val_yearfx_usd)" in query
    assert "reference_year >= @year_start" in query
    assert "product_code in unnest(@product_codes)" in query.lower()
    by_name = {p.name: p for p in params}
    assert by_name["year_start"].value == 2010
    assert by_name["product_codes"].values == ["3405"]


def test_production_by_uf_scopes_to_latest_year_by_default():
    """ufData's choropleth is a single labelled year compared to a latest-year KPI,
    so the by-UF reader must pin to the MAX year under the same filters — never
    cumulate the whole [year_start, year_end] window (the all-years inflation bug)."""
    query, params = sql.production_by_uf(
        "p.serving.serving_pevs_annual",
        year_start=2020,
        year_end=2022,
        product_codes=("3405",),
    )
    low = query.lower()
    # The latest-year predicate is a correlated subquery re-applying the SAME filters.
    assert "reference_year = (select max(reference_year)" in low
    assert low.count("reference_year >= @year_start") == 2  # outer + subquery
    assert low.count("product_code in unnest(@product_codes)") == 2
    # The filter VALUES are bound ONCE even though referenced twice in the SQL.
    by_name = [p.name for p in params]
    assert by_name.count("year_start") == 1 and by_name.count("product_codes") == 1


def test_production_by_uf_latest_year_tiles_sum_to_national_latest(monkeypatch):
    """Behavioral lock for the all-years inflation bug (FINDING #1): under a
    MULTI-YEAR fixture, the latest-year-scoped by-UF reader's tiles must sum to the
    national LATEST-year total — never to the all-years cumulative (which inflated
    each UF by the number of covered years). Simulates the builder's latest-year
    predicate with pandas (no BigQuery), so a regression to all-years SUM is caught.
    """
    pytest.importorskip("flask_caching")
    import pandas as pd

    from embrapa_commodities.serving import gateway

    # 3 years × 2 UFs. All-years cumulative PA = 100+136+1873; the bug summed those.
    rows = [
        {"reference_year": 1986, "state_acronym": "PA", "value": 100.0},
        {"reference_year": 1986, "state_acronym": "SP", "value": 10.0},
        {"reference_year": 2000, "state_acronym": "PA", "value": 136.0},
        {"reference_year": 2000, "state_acronym": "SP", "value": 20.0},
        {"reference_year": 2024, "state_acronym": "PA", "value": 1873.0},
        {"reference_year": 2024, "state_acronym": "SP", "value": 1739.0},
    ]
    full = pd.DataFrame(rows)

    def fake_run(query, params):
        low = query.lower()
        if "select max(reference_year)" in low:
            # Latest-year-scoped reader → only the max year's per-UF rows.
            latest = full[full["reference_year"] == full["reference_year"].max()]
            return (
                latest.groupby("state_acronym")["value"]
                .sum()
                .reset_index()
                .rename(columns={"value": "total_value"})
            )
        # National per-year overview (groups by year over the whole window).
        return (
            full.groupby("reference_year")["value"]
            .sum()
            .reset_index()
            .rename(columns={"value": "total_value"})
        )

    monkeypatch.setattr(gateway, "run_query", fake_run)
    monkeypatch.setattr(gateway, "get_settings", lambda: _isolated_settings())
    app, cache = _bind_simplecache()

    with app.app_context():
        cache.clear()
        uf = gateway.fetch_production_by_uf(year_start=1986, year_end=2024)
        overview = gateway.fetch_production_overview(year_start=1986, year_end=2024)

    national_latest = float(
        overview.loc[overview["reference_year"].idxmax(), "total_value"]
    )  # 2024 national = 1873 + 1739 = 3612
    uf_tile_sum = float(uf["total_value"].sum())
    assert national_latest == 3612.0
    assert uf_tile_sum == national_latest  # tiles sum to the latest-year national


def test_production_by_uf_cumulative_when_latest_year_only_false():
    """The export-coefficient by-UF reader opts out: it needs the window-cumulative
    sum (production vs export accumulated over the same common-year window)."""
    query, _ = sql.production_by_uf(
        "p.serving.serving_pevs_annual", year_start=1997, year_end=2000, latest_year_only=False
    )
    assert "select max(reference_year)" not in query.lower()
    assert "group by state_acronym" in query


def test_comex_by_uf_scopes_to_latest_year_by_default():
    """Same latest-year scoping as production_by_uf for the COMEX choropleth."""
    query, params = sql.comex_by_uf(
        "p.serving.serving_comex_annual", year_start=2018, year_end=2024, ncm_codes=("08012100",)
    )
    low = query.lower()
    assert "reference_year = (select max(reference_year)" in low
    assert low.count("ncm_code in unnest(@ncm_codes)") == 2
    assert [p.name for p in params].count("ncm_codes") == 1


def test_comex_by_uf_cumulative_when_latest_year_only_false():
    query, _ = sql.comex_by_uf(
        "p.serving.serving_comex_annual",
        ncm_codes=("08012100",),
        flow="export",
        latest_year_only=False,
    )
    assert "select max(reference_year)" not in query.lower()


def test_comex_seasonality_filters_flow_and_ncm():
    query, params = sql.comex_seasonality(
        "p.serving.serving_comex_seasonality",
        year_start=2015,
        year_end=2020,
        ncm_codes=("08012100",),
        flow="export",
    )
    assert "group by reference_year, reference_month" in query
    assert "sum(val_yearfx_usd)" in query
    assert "sum(net_weight_kg)" in query  # Volume metric for the dual-metric profile
    assert "flow = @flow" in query
    assert "ncm_code in unnest(@ncm_codes)" in query.lower()
    by_name = {p.name: p for p in params}
    assert by_name["flow"].value == "export"
    assert by_name["ncm_codes"].values == ["08012100"]


def test_products_by_uf_groups_by_product_and_filters_state():
    """The inverse of *_by_uf: GROUP BY product, constrain state_acronym to the
    selected UFs, carry value + family-split q_mass/q_vol (COMEX export form)."""
    query, params = sql.products_by_uf(
        "p.serving.serving_comex_annual",
        code_column="ncm_code",
        name_column="ncm_description",
        year_start=2018,
        year_end=2024,
        uf_codes=("AC",),
        value_column="val_yearfx_usd",
        flow="export",
    )
    low = query.lower()
    assert "group by ncm_code" in low
    assert "any_value(ncm_description)" in low
    assert "state_acronym in unnest(@uf_codes)" in low
    assert "sum(val_yearfx_usd)" in low
    assert "case when family = 'massa'  then qty_base end" in query
    assert "case when family = 'volume' then qty_base end" in query
    assert "flow = @flow" in low
    by_name = {p.name: p for p in params}
    assert by_name["uf_codes"].values == ["AC"]
    assert by_name["flow"].value == "export"


def test_products_by_uf_pevs_form_has_no_flow_and_validates_columns():
    """PEVS form: product_code/product_description, no flow predicate. An identifier
    outside the product allowlist is rejected (injection guard)."""
    query, _ = sql.products_by_uf(
        "p.serving.serving_pevs_annual",
        code_column="product_code",
        name_column="product_description",
        uf_codes=("PA",),
    )
    assert "flow = @flow" not in query.lower()
    assert "group by product_code" in query.lower()
    with pytest.raises(ValueError, match="not allowed"):
        sql.products_by_uf(
            "p.serving.serving_pevs_annual",
            code_column="product_code); drop table x; --",
            name_column="product_description",
        )


# ── trade marts: overview / ufData / partner / flows / quality ─────────────────


def test_trade_overview_sums_value_and_weight_by_year():
    query, params = sql.trade_overview(
        "p.serving.serving_comex_annual",
        code_column="ncm_code",
        year_start=2018,
        year_end=2022,
        codes=("08012100",),
        flow="export",
    )
    assert "group by reference_year" in query
    assert "sum(val_yearfx_usd)" in query
    assert "sum(net_weight_kg)" in query
    assert "flow = @flow" in query
    assert "ncm_code in unnest(@codes)" in query.lower()
    by_name = {p.name: p for p in params}
    assert by_name["flow"].value == "export"
    assert by_name["codes"].values == ["08012100"]
    assert by_name["year_start"].value == 2018


def test_trade_overview_comtrade_uses_cmd_code():
    query, params = sql.trade_overview(
        "p.serving.serving_comtrade_annual", code_column="cmd_code", codes=("440710",)
    )
    assert "cmd_code in unnest(@codes)" in query.lower()
    assert {p.name: p for p in params}["codes"].values == ["440710"]


def test_comex_by_uf_groups_by_state_with_weight():
    query, params = sql.comex_by_uf(
        "p.serving.serving_comex_annual", year_start=2020, ncm_codes=("08012100",), flow="import"
    )
    assert "group by state_acronym" in query
    assert "sum(val_yearfx_usd)" in query
    assert "sum(net_weight_kg)" in query
    assert "any_value(region_abbrev)" in query
    assert {p.name: p for p in params}["flow"].value == "import"


def test_trade_overview_serves_real_brl_column_when_requested():
    """A BRL display selects the REAL year-FX BRL column the trade mart now carries —
    NOT val_yearfx_usd (the frontend used to cross-convert USD via a mock rate)."""
    query, _ = sql.trade_overview(
        "p.serving.serving_comex_annual",
        code_column="ncm_code",
        value_column="val_yearfx_brl",
    )
    assert "sum(val_yearfx_brl)" in query
    assert "sum(val_yearfx_usd)" not in query
    # The output alias stays total_value_usd so the seam's rename stays uniform.
    assert "as total_value_usd" in query


def test_comex_by_uf_serves_real_eur_column_when_requested():
    """A EUR display selects the REAL deflated EUR column (weight stays raw kg)."""
    query, _ = sql.comex_by_uf(
        "p.serving.serving_comex_annual",
        ncm_codes=("08012100",),
        value_column="val_real_ipca_eur",
    )
    assert "sum(val_real_ipca_eur)" in query
    assert "sum(val_yearfx_usd)" not in query
    assert "sum(net_weight_kg)" in query  # weight is currency-independent


def test_comex_by_uf_yearly_serves_real_brl_column_when_requested():
    query, _ = sql.comex_by_uf_yearly(
        "p.serving.serving_comex_annual",
        ncm_codes=("08012100",),
        value_column="val_real_ipca_brl",
    )
    assert "sum(val_real_ipca_brl)" in query
    assert "sum(val_yearfx_usd)" not in query


def test_trade_value_column_allowlist_blocks_injection():
    """The trade value_column is interpolated as an identifier, so an off-allowlist
    value (e.g. an injection attempt) must raise rather than reach the SQL."""
    import pytest

    with pytest.raises(ValueError, match="value_column"):
        sql.trade_overview(
            "p.serving.serving_comex_annual",
            code_column="ncm_code",
            value_column="val_yearfx_usd; drop table serving_comex_annual",
        )


def test_trade_by_partner_splits_export_and_import():
    query, params = sql.trade_by_partner(
        "p.serving.serving_comex_annual",
        partner_code_column="country_code",
        partner_name_column="country_name",
        code_column="ncm_code",
        year_start=2021,
        codes=("08012100",),
    )
    assert "group by country_code" in query
    assert "case when flow = 'export' then val_yearfx_usd end" in query
    assert "case when flow = 'import' then val_yearfx_usd end" in query
    assert "any_value(country_name)" in query
    assert "order by value_usd desc" in query
    assert {p.name: p for p in params}["codes"].values == ["08012100"]
    # quantity + implied unit price always present so the view can switch metric
    assert "sum(net_weight_kg)" in query
    assert "safe_divide(sum(val_yearfx_usd), sum(net_weight_kg))" in query


def test_trade_by_partner_rank_by_switches_order_clause():
    """rank_by picks the ORDER BY dimension server-side (Capital/Volume/Preço)."""
    base = dict(
        partner_code_column="country_code",
        partner_name_column="country_name",
        code_column="ncm_code",
    )
    q_weight, _ = sql.trade_by_partner("p.s.t", rank_by="weight", **base)
    assert "order by total_weight_kg desc nulls last" in q_weight
    q_price, _ = sql.trade_by_partner("p.s.t", rank_by="price", **base)
    assert "order by price_usd_per_kg desc nulls last" in q_price
    # an unknown metric falls back to value (never an unvalidated literal)
    q_bad, _ = sql.trade_by_partner("p.s.t", rank_by="; drop table x", **base)
    assert "order by value_usd desc" in q_bad


def test_trade_flows_groups_by_origin_and_dest():
    query, _ = sql.trade_flows(
        "p.serving.serving_comtrade_annual",
        origin_code_column="reporter_code",
        origin_name_column="reporter_name",
        dest_code_column="partner_code",
        dest_name_column="partner_name",
        code_column="cmd_code",
    )
    assert "group by reporter_code, partner_code" in query
    assert "any_value(reporter_name)" in query
    assert "any_value(partner_name)" in query
    assert "sum(val_yearfx_usd)" in query
    # No reporter pin unless asked: the COMEX caller relies on this.
    assert "reporter_iso_a3 = @reporter" not in query


def test_trade_builders_pin_reporter_when_given():
    """Both trade builders accept an optional reporter pin (Brazil for the
    multi-reporter COMTRADE mart): the identifier is allowlist-validated and the
    value is bound, exactly like the cross-source path."""
    q_partner, p_partner = sql.trade_by_partner(
        "p.serving.serving_comtrade_annual",
        partner_code_column="partner_code",
        partner_name_column="partner_name",
        code_column="cmd_code",
        reporter_column="reporter_iso_a3",
        reporter_value="BRA",
    )
    assert "reporter_iso_a3 = @reporter" in q_partner
    assert {p.name: p for p in p_partner}["reporter"].value == "BRA"

    q_flows, p_flows = sql.trade_flows(
        "p.serving.serving_comtrade_annual",
        origin_code_column="reporter_code",
        origin_name_column="reporter_name",
        dest_code_column="partner_code",
        dest_name_column="partner_name",
        code_column="cmd_code",
        reporter_column="reporter_iso_a3",
        reporter_value="BRA",
    )
    assert "reporter_iso_a3 = @reporter" in q_flows
    assert {p.name: p for p in p_flows}["reporter"].value == "BRA"


def test_trade_flows_narrows_to_origin_ufs_when_uf_codes_given():
    # COMEX origin = state_acronym: a UF filter must add an IN UNNEST predicate
    # bound as a param (never f-string interpolated).
    query, params = sql.trade_flows(
        "p.serving.serving_comex_annual",
        origin_code_column="state_acronym",
        origin_name_column="state_name",
        dest_code_column="country_code",
        dest_name_column="country_name",
        code_column="ncm_code",
        uf_codes=("PA", "SP"),
    )
    assert "state_acronym in unnest(@uf_codes)" in query.lower()
    by_name = {p.name: p for p in params}
    assert by_name["uf_codes"].values == ["PA", "SP"]


def test_trade_flows_no_uf_codes_adds_no_uf_predicate():
    # Empty/absent UF list = no filter (the existing convention) — no @uf_codes.
    query, params = sql.trade_flows(
        "p.serving.serving_comex_annual",
        origin_code_column="state_acronym",
        origin_name_column="state_name",
        dest_code_column="country_code",
        dest_name_column="country_name",
        code_column="ncm_code",
    )
    assert "uf_codes" not in query.lower()
    assert not any(p.name == "uf_codes" for p in params)


def test_trade_by_partner_narrows_to_origin_ufs_when_uf_codes_given():
    query, params = sql.trade_by_partner(
        "p.serving.serving_comex_annual",
        partner_code_column="country_code",
        partner_name_column="country_name",
        code_column="ncm_code",
        uf_codes=("PA",),
    )
    assert "state_acronym in unnest(@uf_codes)" in query.lower()
    assert {p.name: p for p in params}["uf_codes"].values == ["PA"]


def test_trade_by_partner_no_uf_codes_adds_no_uf_predicate():
    query, params = sql.trade_by_partner(
        "p.serving.serving_comex_annual",
        partner_code_column="country_code",
        partner_name_column="country_name",
        code_column="ncm_code",
    )
    assert "uf_codes" not in query.lower()
    assert not any(p.name == "uf_codes" for p in params)


def test_quality_by_source_filters_source():
    query, params = sql.quality_by_source(
        "p.serving.serving_quality_by_source", source="mdic_comex"
    )
    assert "source = @source" in query
    assert "data_quality_flag" in query
    assert "order by n_rows desc" in query
    assert {p.name: p for p in params}["source"].value == "mdic_comex"


def test_quality_by_source_no_filter_has_no_where():
    query, params = sql.quality_by_source("p.serving.serving_quality_by_source")
    assert "where" not in query.lower()
    assert params == []


def test_dimension_column_allowlist_blocks_injection():
    # origin/dest/partner identifiers are interpolated, so they must be allowlisted.
    with pytest.raises(ValueError, match="not allowed"):
        sql.trade_by_partner(
            "p.serving.serving_comex_annual",
            partner_code_column="country_code); drop table x; --",
            partner_name_column="country_name",
            code_column="ncm_code",
        )
    with pytest.raises(ValueError, match="not allowed"):
        sql.trade_flows(
            "p.serving.serving_comex_annual",
            origin_code_column="state_acronym",
            origin_name_column="state_name",
            dest_code_column="evil_column",
            dest_name_column="country_name",
            code_column="ncm_code",
        )


# ── sql: products / productTS / provenance (uniform across sources) ────────────


def test_products_lists_distinct_codes_with_unit_and_family():
    query, params = sql.products(
        "p.serving.serving_comex_annual", code_column="ncm_code", name_column="ncm_description"
    )
    assert "group by ncm_code" in query
    assert "any_value(ncm_description)" in query
    assert "any_value(base_unit)" in query
    assert "any_value(unit_native)" in query
    assert "any_value(family)" in query
    # measure_kind is OFF by default → the SELECT stays schema-compatible with marts
    # (COMEX/PEVS/PAM) that do not carry the column.
    assert "measure_kind" not in query
    assert params == []


def test_products_adds_measure_kind_only_when_requested():
    """The livestock mart (serving_ppm_annual) carries measure_kind (stock|flow); the
    seam opts in so the UI can tell the value-less herd from animal-product flows."""
    query, _ = sql.products(
        "p.serving.serving_ppm_annual",
        code_column="product_code",
        name_column="product_description",
        with_measure_kind=True,
    )
    assert "any_value(measure_kind) as measure_kind" in query


def test_product_timeseries_sums_value_and_native_quantity():
    query, params = sql.product_timeseries(
        "p.serving.serving_pevs_annual",
        code_column="product_code",
        value_column="val_real_ipca_brl",
        year_start=2000,
        codes=("3405",),
    )
    assert "group by product_code, reference_year" in query
    assert "sum(val_real_ipca_brl)" in query
    assert "sum(qty_native)" in query
    # Per-family base quantity via CASE: mass (t) and volume (m³) are summed
    # SEPARATELY, so a mixed-unit code never blends units and a count/energy/area
    # family contributes to neither (no dimensionless mis-scale downstream).
    assert "case when family = 'massa' then qty_base end" in query
    assert "as q_mass" in query
    assert "case when family = 'volume' then qty_base end" in query
    assert "as q_vol" in query
    # contagem (livestock head / eggs — PPM) gets its OWN qty_base track so the herd
    # is not invisible in the quantity charts.
    assert "case when family = 'contagem' then qty_base end" in query
    assert "as q_count" in query
    # qty_base is never summed across families anymore — the old single column is gone.
    assert "as total_qty_base" not in query
    assert "any_value(family)" in query
    assert "product_code in unnest(@codes)" in query.lower()
    by_name = {p.name: p for p in params}
    assert by_name["codes"].values == ["3405"]
    assert by_name["year_start"].value == 2000


def test_product_timeseries_applies_flow_filter_for_trade():
    """A trade source's per-product series narrows to one direction so it stays
    consistent with a flow-filtered overview (the mart carries `flow` in its grain)."""
    query, params = sql.product_timeseries(
        "p.serving.serving_comex_annual",
        code_column="ncm_code",
        year_start=2020,
        flow="export",
    )
    assert "flow = @flow" in query
    assert {p.name: p for p in params}["flow"].value == "export"


def test_product_timeseries_no_flow_adds_no_predicate():
    """The default (flow=None) sums every flow — production marts (no `flow`
    column) always take this path, so the predicate must stay absent."""
    query, _ = sql.product_timeseries("p.serving.serving_pevs_annual", code_column="product_code")
    assert "flow = @flow" not in query.lower()


def test_product_columns_allowlist_blocks_injection():
    with pytest.raises(ValueError, match="not allowed"):
        sql.products(
            "p.serving.serving_comex_annual",
            code_column="ncm_code); drop table x; --",
            name_column="ncm_description",
        )
    with pytest.raises(ValueError, match="not allowed"):
        sql.product_timeseries("p.serving.serving_pevs_annual", code_column="evil")


def test_source_metadata_selects_provenance_columns():
    query, params = sql.source_metadata("p.gold.gold_source_metadata", source="mdic_comex")
    assert "gold_table" in query
    assert "products_total" in query
    assert "ufs_total" in query
    assert "source = @source" in query
    assert {p.name: p for p in params}["source"].value == "mdic_comex"


def test_source_metadata_no_filter_has_no_where():
    query, params = sql.source_metadata("p.gold.gold_source_metadata")
    assert "where" not in query.lower()
    assert params == []


# ── sql: cross_annual (cross-source view) ─────────────────────────────────────


def test_cross_annual_comex_export_has_no_reporter_filter():
    query, params = sql.cross_annual(
        "p.serving.serving_comex_annual",
        measure_column="val_yearfx_usd",
        flow="export",
        code_column="ncm_code",
        codes=("08012100",),
        year_start=2018,
    )
    assert "sum(val_yearfx_usd) as value" in query
    assert "flow = @flow" in query
    assert "ncm_code in unnest(@codes)" in query.lower()
    assert "group by reference_year" in query
    assert "@reporter" not in query  # COMEX is Brazil's own customs — no reporter split
    assert {p.name: p for p in params}["flow"].value == "export"


def test_cross_annual_comtrade_brazil_applies_reporter_filter():
    query, params = sql.cross_annual(
        "p.serving.serving_comtrade_annual",
        measure_column="val_yearfx_usd",
        flow="export",
        reporter_column="reporter_iso_a3",
        reporter_value="BRA",
    )
    assert "reporter_iso_a3 = @reporter" in query
    assert {p.name: p for p in params}["reporter"].value == "BRA"


def test_cross_annual_world_total_omits_reporter_filter():
    query, _ = sql.cross_annual(
        "p.serving.serving_comtrade_annual", measure_column="val_yearfx_usd", flow="export"
    )
    assert "@reporter" not in query
    assert "reporter_iso_a3" not in query


# ── curation: append-only SCD2 writer ─────────────────────────────────────────


def _settings() -> Settings:
    return _isolated_settings(gcp_project_id="test-project")


def test_record_code_industrialization_inserts_parameterized_row_with_author(monkeypatch):
    pytest.importorskip("flask_caching")
    from embrapa_commodities.serving import attribute_engineering as curation

    monkeypatch.setattr(curation, "ensure_dataset", lambda *a, **k: None)  # writer self-heals
    settings = _settings()
    client = mock.Mock()
    client.query.return_value.result.return_value = None
    headers = {iap.IAP_EMAIL_HEADER: "accounts.google.com:alice@embrapa.br"}

    record = curation.record_code_industrialization(
        "mdic_comex",
        "08013200",
        "processada",
        headers,
        note="shelled",
        settings=settings,
        client=client,
        invalidate_cache=False,
    )

    assert record["edited_by"] == "alice@embrapa.br"
    assert record["source"] == "mdic_comex"
    assert record["code"] == "08013200"
    assert record["industrialization_level"] == "processada"
    sql_text = client.query.call_args.args[0].lower()
    assert "insert into" in sql_text
    assert "current_timestamp()" in sql_text  # server-side stamp, not client clock
    params = {p.name: p.value for p in client.query.call_args.kwargs["job_config"].query_parameters}
    assert params["source"] == "mdic_comex"
    assert params["code"] == "08013200"
    assert params["level"] == "processada"
    assert params["edited_by"] == "alice@embrapa.br"
    assert params["note"] == "shelled"


def test_record_code_industrialization_rejects_empty_inputs():
    pytest.importorskip("flask_caching")
    from embrapa_commodities.serving import attribute_engineering as curation

    headers = {iap.IAP_EMAIL_HEADER: "accounts.google.com:alice@embrapa.br"}
    with pytest.raises(ValueError):
        curation.record_code_industrialization(
            "mdic_comex", "", "processada", headers, settings=_settings(), client=mock.Mock()
        )


def test_ensure_code_industrialization_log_table_creates_with_explicit_schema(monkeypatch):
    pytest.importorskip("flask_caching")
    from embrapa_commodities.serving import attribute_engineering as curation

    monkeypatch.setattr(curation, "ensure_dataset", lambda *a, **k: None)
    client = mock.Mock()
    fqn = curation.ensure_code_industrialization_log_table(settings=_settings(), client=client)

    assert fqn.endswith(".code_industrialization_log")
    table_arg = client.create_table.call_args.args[0]
    assert {f.name for f in table_arg.schema} == {
        "source",
        "code",
        "industrialization_level",
        "note",
        "edited_by",
        "edited_at",
        "change_id",
    }
    assert client.create_table.call_args.kwargs["exists_ok"] is True


# ── curation: idempotency key (client-supplied change_id) ─────────────────────


def _seen_client(exists: bool):
    """A mock BQ client whose SELECT (the dedupe probe) yields one row when
    ``exists`` else none; every ``query().result()`` returns the same iterable."""
    client = mock.Mock()
    client.query.return_value.result.return_value = [(1,)] if exists else []
    return client


def test_record_code_industrialization_generates_change_id_when_absent(monkeypatch):
    """No client change_id → a fresh uuid is minted, the dedupe SELECT is SKIPPED
    (a brand-new uuid can't pre-exist), and exactly one query (the INSERT) runs."""
    pytest.importorskip("flask_caching")
    from embrapa_commodities.serving import attribute_engineering as curation

    monkeypatch.setattr(curation, "ensure_dataset", lambda *a, **k: None)
    client = _seen_client(exists=True)  # would dedupe IF it probed — it must not
    headers = {iap.IAP_EMAIL_HEADER: "accounts.google.com:alice@embrapa.br"}

    record = curation.record_code_industrialization(
        "mdic_comex",
        "08013200",
        "processada",
        headers,
        settings=_settings(),
        client=client,
        invalidate_cache=False,
    )

    assert record["deduped"] is False
    assert len(record["change_id"]) == 32  # uuid4().hex
    assert client.query.call_count == 1  # only the INSERT — no dedupe SELECT
    assert "insert into" in client.query.call_args.args[0].lower()


def test_record_code_industrialization_dedupes_on_repeated_change_id(monkeypatch):
    """A client change_id that ALREADY exists in the log → no-op: the writer
    returns deduped=True and never issues the INSERT (only the SELECT probe)."""
    pytest.importorskip("flask_caching")
    from embrapa_commodities.serving import attribute_engineering as curation

    monkeypatch.setattr(curation, "ensure_dataset", lambda *a, **k: None)
    client = _seen_client(exists=True)
    headers = {iap.IAP_EMAIL_HEADER: "accounts.google.com:alice@embrapa.br"}

    record = curation.record_code_industrialization(
        "mdic_comex",
        "08013200",
        "processada",
        headers,
        change_id="dup-key-123",
        settings=_settings(),
        client=client,
        invalidate_cache=False,
    )

    assert record["deduped"] is True
    assert record["change_id"] == "dup-key-123"
    # The single query is the SELECT probe; the INSERT must never run.
    assert client.query.call_count == 1
    assert "insert into" not in client.query.call_args.args[0].lower()


def test_record_code_industrialization_inserts_when_change_id_is_new(monkeypatch):
    """A client change_id NOT yet in the log → the probe misses and the INSERT
    proceeds, carrying the SAME change_id (so a retry would then dedupe)."""
    pytest.importorskip("flask_caching")
    from embrapa_commodities.serving import attribute_engineering as curation

    monkeypatch.setattr(curation, "ensure_dataset", lambda *a, **k: None)
    client = _seen_client(exists=False)
    headers = {iap.IAP_EMAIL_HEADER: "accounts.google.com:alice@embrapa.br"}

    record = curation.record_code_industrialization(
        "mdic_comex",
        "08013200",
        "processada",
        headers,
        change_id="fresh-key-9",
        settings=_settings(),
        client=client,
        invalidate_cache=False,
    )

    assert record["deduped"] is False
    assert record["change_id"] == "fresh-key-9"
    assert client.query.call_count == 2  # SELECT probe (miss) + INSERT
    insert_call = client.query.call_args  # the LAST call is the INSERT
    params = {p.name: p.value for p in insert_call.kwargs["job_config"].query_parameters}
    assert params["change_id"] == "fresh-key-9"


def test_record_flow_market_dedupes_on_repeated_change_id(monkeypatch):
    """The flow-market writer honours the same idempotency contract."""
    pytest.importorskip("flask_caching")
    from embrapa_commodities.serving import attribute_engineering as curation

    monkeypatch.setattr(curation, "ensure_flow_market_log_table", lambda *a, **k: None)
    client = _seen_client(exists=True)
    headers = {iap.IAP_EMAIL_HEADER: "accounts.google.com:alice@embrapa.br"}

    record = curation.record_flow_market(
        "4000",
        "X",
        "consumo",
        headers,
        change_id="dup-flow-1",
        settings=_settings(),
        client=client,
        invalidate_cache=False,
    )

    assert record["deduped"] is True
    assert client.query.call_count == 1
    assert "insert into" not in client.query.call_args.args[0].lower()


def test_ensure_curators_table_creates_with_explicit_schema(monkeypatch):
    """The Console-managed curator allowlist table is auto-created with the
    explicit (email, added_by, added_at) schema — never autodetected."""
    pytest.importorskip("flask_caching")
    from embrapa_commodities.serving import research_inputs as curation

    monkeypatch.setattr(curation, "ensure_dataset", lambda *a, **k: None)
    client = mock.Mock()
    fqn = curation.ensure_curators_table(settings=_settings(), client=client)

    assert fqn.endswith(".curators")
    table_arg = client.create_table.call_args.args[0]
    assert {f.name for f in table_arg.schema} == {"email", "added_by", "added_at"}
    assert client.create_table.call_args.kwargs["exists_ok"] is True


# ── gateway: caching behavior ─────────────────────────────────────────────────


def test_memoize_avoids_repeated_bigquery_roundtrip(monkeypatch):
    pytest.importorskip("flask_caching")
    from flask import Flask

    from embrapa_commodities.serving import gateway
    from embrapa_commodities.serving.cache import cache

    app = Flask(__name__)
    cache.init_app(app, config={"CACHE_TYPE": "SimpleCache", "CACHE_DEFAULT_TIMEOUT": 300})

    calls = {"n": 0}

    def fake_run(query, params):
        calls["n"] += 1
        return [("mdic_comex", "08013200", "processada")]

    monkeypatch.setattr(gateway, "run_query", fake_run)
    monkeypatch.setattr(gateway, "get_settings", lambda: _isolated_settings())

    with app.app_context():
        cache.clear()
        gateway.fetch_current_code_industrialization()
        gateway.fetch_current_code_industrialization()  # served from cache

    assert calls["n"] == 1


def test_classification_cache_uses_short_ttl_for_multiinstance():
    """The curation read uses a SHORT TTL, not the long mart default.

    That short window (not a shared Redis) is what bounds cross-instance
    staleness, letting the dashboard scale to N Cloud Run instances for free.
    """
    pytest.importorskip("flask_caching")
    from embrapa_commodities.serving import gateway

    mart_ttl = _isolated_settings().cache_default_timeout
    assert gateway.DEFAULT_CLASSIFICATION_TTL <= 60
    assert mart_ttl > gateway.DEFAULT_CLASSIFICATION_TTL


def test_init_cache_binds_classification_ttl_from_settings():
    """The effective classification TTL is the authoritative Settings value.

    init_cache must set the memoized read's writable cache_timeout to
    Settings.cache_classification_timeout (flask-caching re-reads it per call), so
    the config field — not a separately-read env var — governs cross-instance
    staleness. This is what fixes the TTL drift.
    """
    pytest.importorskip("flask_caching")
    from flask import Flask

    from embrapa_commodities.serving import gateway
    from embrapa_commodities.serving.cache import init_cache

    settings = _isolated_settings(cache_classification_timeout=17)
    app = Flask(__name__)
    init_cache(app, settings)

    effective = gateway.fetch_current_code_industrialization.cache_timeout
    assert effective == 17
    assert effective == settings.cache_classification_timeout


def test_init_cache_binds_classification_ttl_to_curator_allowlist():
    """The curator-allowlist read honors CACHE_CLASSIFICATION_TIMEOUT too.

    fetch_curators gates POST /api/curation/* authorization, so lowering the TTL to
    revoke a removed curator faster must actually take effect — it must not stay
    pinned at the decoration-time DEFAULT_CLASSIFICATION_TTL.
    """
    pytest.importorskip("flask_caching")
    from flask import Flask

    from embrapa_commodities.serving import gateway
    from embrapa_commodities.serving.cache import init_cache

    settings = _isolated_settings(cache_classification_timeout=7)
    app = Flask(__name__)
    init_cache(app, settings)

    assert gateway.fetch_curators.cache_timeout == 7
    assert gateway.fetch_curators.cache_timeout == settings.cache_classification_timeout


def test_init_cache_binds_classification_ttl_to_catalog_editors():
    """The catalog-editor allowlist read honors CACHE_CLASSIFICATION_TIMEOUT too (L-5).

    fetch_catalog_editors gates POST /api/catalog/* and is Console-edited, so the TTL is
    the sole convergence control — lowering it to revoke a removed editor must take effect,
    not stay pinned at the decoration-time DEFAULT_CLASSIFICATION_TTL.
    """
    pytest.importorskip("flask_caching")
    from flask import Flask

    from embrapa_commodities.serving import gateway
    from embrapa_commodities.serving.cache import init_cache

    settings = _isolated_settings(cache_classification_timeout=9)
    app = Flask(__name__)
    init_cache(app, settings)

    assert gateway.fetch_catalog_editors.cache_timeout == 9
    assert gateway.fetch_catalog_editors.cache_timeout == settings.cache_classification_timeout


# ── gateway: mart readers exercise SQL + params + allowlist ───────────────────


def _bind_simplecache():
    """Bind the shared cache to a fresh Flask app on SimpleCache; return (app, cache)."""
    from flask import Flask

    from embrapa_commodities.serving.cache import cache

    app = Flask(__name__)
    cache.init_app(app, config={"CACHE_TYPE": "SimpleCache", "CACHE_DEFAULT_TIMEOUT": 300})
    return app, cache


def test_fetch_production_overview_queries_correct_table_and_params(monkeypatch):
    pytest.importorskip("flask_caching")
    from embrapa_commodities.serving import gateway

    recorded = {}

    def recorder(query, params, **kwargs):
        recorded["query"] = query
        recorded["params"] = {p.name: p for p in params}
        return "df"

    monkeypatch.setattr(gateway, "run_query", recorder)
    monkeypatch.setattr(gateway, "get_settings", lambda: _isolated_settings())
    app, cache = _bind_simplecache()

    with app.app_context():
        cache.clear()
        out = gateway.fetch_production_overview(
            year_start=2000, year_end=2010, product_codes=("3405",)
        )

    assert out == "df"
    assert "p.serving.serving_pevs_annual" in recorded["query"]
    assert "sum(val_real_ipca_brl)" in recorded["query"]
    assert recorded["params"]["year_start"].value == 2000
    assert recorded["params"]["year_end"].value == 2010
    assert recorded["params"]["product_codes"].values == ["3405"]


def test_quality_readers_return_none_for_unknown_source_without_querying(monkeypatch):
    """Tri-state contract (documented in gateway's module docstring): the per-source
    quality readers return None for an UNKNOWN source — short-circuiting BEFORE any
    BigQuery read — rather than querying or raising. The webapi serializers normalize
    that None to empty, so this is the intended, lower-risk behavior; pin it so it is
    not silently changed."""
    pytest.importorskip("flask_caching")
    from embrapa_commodities.serving import gateway

    def boom(query, params):  # must never be reached for an unknown source
        raise AssertionError("run_query must not run for an unknown source")

    monkeypatch.setattr(gateway, "run_query", boom)
    app, cache = _bind_simplecache()

    with app.app_context():
        cache.clear()
        assert gateway.fetch_quality_timeseries("not_a_real_source") is None
        assert gateway.fetch_quality_by_product("not_a_real_source") is None


def test_fetch_curators_queries_allowlist_table_distinct_lowered(monkeypatch):
    """fetch_curators gates curation AUTHORIZATION, so pin its SQL exactly: distinct
    lower(trim(email)) with NULLs excluded, from the research_inputs allowlist table.
    A typo here would silently widen or empty the curator allowlist."""
    pytest.importorskip("flask_caching")
    from embrapa_commodities.serving import gateway

    recorded = {}

    def recorder(query, params, **kwargs):
        recorded["query"] = query
        recorded["params"] = params
        return "df"

    monkeypatch.setattr(gateway, "run_query", recorder)
    monkeypatch.setattr(gateway, "get_settings", lambda: _isolated_settings())
    app, cache = _bind_simplecache()

    with app.app_context():
        cache.clear()
        out = gateway.fetch_curators()

    assert out == "df"
    q = recorded["query"].lower()
    assert "p.research_inputs.curators" in q
    assert "distinct lower(trim(email))" in q
    assert "where email is not null" in q
    assert recorded["params"] == []  # constant table FQN only — no bound params


def test_fetch_banco_metadata_binds_banco_id_as_param(monkeypatch):
    """fetch_banco_metadata reads operator overrides for ONE banco — the banco_id
    must be a BOUND parameter (not interpolated) and hit the overrides table."""
    pytest.importorskip("flask_caching")
    from embrapa_commodities.serving import gateway

    recorded = {}

    def recorder(query, params, **kwargs):
        recorded["query"] = query
        recorded["params"] = {p.name: p for p in params}
        return "df"

    monkeypatch.setattr(gateway, "run_query", recorder)
    monkeypatch.setattr(gateway, "get_settings", lambda: _isolated_settings())
    app, cache = _bind_simplecache()

    with app.app_context():
        cache.clear()
        gateway.fetch_banco_metadata("ibge_pevs")

    assert "p.research_inputs.banco_metadata" in recorded["query"]
    assert "where banco_id = @banco_id" in recorded["query"]
    assert recorded["params"]["banco_id"].value == "ibge_pevs"


def test_fetch_production_by_uf_queries_correct_table_and_params(monkeypatch):
    pytest.importorskip("flask_caching")
    from embrapa_commodities.serving import gateway

    recorded = {}

    def recorder(query, params, **kwargs):
        recorded["query"] = query
        recorded["params"] = {p.name: p for p in params}
        return "df"

    monkeypatch.setattr(gateway, "run_query", recorder)
    monkeypatch.setattr(gateway, "get_settings", lambda: _isolated_settings())
    app, cache = _bind_simplecache()

    with app.app_context():
        cache.clear()
        gateway.fetch_production_by_uf(year_start=2015, value_column="val_yearfx_usd")

    assert "p.serving.serving_pevs_annual" in recorded["query"]
    assert "group by state_acronym" in recorded["query"]
    assert "sum(val_yearfx_usd)" in recorded["query"]
    assert recorded["params"]["year_start"].value == 2015


def test_fetch_production_by_uf_latest_year_flag_threads_to_builder(monkeypatch):
    """fetch_production_by_uf defaults to the latest-year scoping; latest_year_only
    =False threads through to the cumulative builder (export-coefficient path)."""
    pytest.importorskip("flask_caching")
    from embrapa_commodities.serving import gateway

    recorded = {}

    def recorder(query, params, **kwargs):
        recorded["query"] = query
        return "df"

    monkeypatch.setattr(gateway, "run_query", recorder)
    monkeypatch.setattr(gateway, "get_settings", lambda: _isolated_settings())
    app, cache = _bind_simplecache()

    with app.app_context():
        cache.clear()
        gateway.fetch_production_by_uf(year_start=2020, year_end=2022)  # default → latest
        assert "select max(reference_year)" in recorded["query"].lower()
        cache.clear()
        gateway.fetch_production_by_uf(year_start=2020, year_end=2022, latest_year_only=False)
        assert "select max(reference_year)" not in recorded["query"].lower()


def test_fetch_comex_by_uf_latest_year_flag_threads_to_builder(monkeypatch):
    pytest.importorskip("flask_caching")
    from embrapa_commodities.serving import gateway

    recorded = {}

    def recorder(query, params, **kwargs):
        recorded["query"] = query
        return "df"

    monkeypatch.setattr(gateway, "run_query", recorder)
    monkeypatch.setattr(gateway, "get_settings", lambda: _isolated_settings())
    app, cache = _bind_simplecache()

    with app.app_context():
        cache.clear()
        gateway.fetch_comex_by_uf(ncm_codes=("0801",))  # default → latest
        assert "select max(reference_year)" in recorded["query"].lower()
        cache.clear()
        gateway.fetch_comex_by_uf(ncm_codes=("0801",), latest_year_only=False)
        assert "select max(reference_year)" not in recorded["query"].lower()


def test_fetch_comex_months_per_year_queries_seasonality_mart(monkeypatch):
    pytest.importorskip("flask_caching")
    from embrapa_commodities.serving import gateway

    recorded = {}

    def recorder(query, params, **kwargs):
        recorded["query"] = query
        return "df"

    monkeypatch.setattr(gateway, "run_query", recorder)
    monkeypatch.setattr(gateway, "get_settings", lambda: _isolated_settings())
    app, cache = _bind_simplecache()

    with app.app_context():
        cache.clear()
        out = gateway.fetch_comex_months_per_year()

    assert out == "df"
    assert "p.serving.serving_comex_seasonality" in recorded["query"]
    assert "count(distinct reference_month)" in recorded["query"].lower()


def test_fetch_comex_seasonality_queries_correct_table_and_params(monkeypatch):
    pytest.importorskip("flask_caching")
    from embrapa_commodities.serving import gateway

    recorded = {}

    def recorder(query, params, **kwargs):
        recorded["query"] = query
        recorded["params"] = {p.name: p for p in params}
        return "df"

    monkeypatch.setattr(gateway, "run_query", recorder)
    monkeypatch.setattr(gateway, "get_settings", lambda: _isolated_settings())
    app, cache = _bind_simplecache()

    with app.app_context():
        cache.clear()
        gateway.fetch_comex_seasonality(year_start=2019, ncm_codes=("08012100",), flow="export")

    assert "p.serving.serving_comex_seasonality" in recorded["query"]
    assert "group by reference_year, reference_month" in recorded["query"]
    assert recorded["params"]["flow"].value == "export"
    assert recorded["params"]["ncm_codes"].values == ["08012100"]


def test_fetch_comex_overview_queries_annual_mart(monkeypatch):
    pytest.importorskip("flask_caching")
    from embrapa_commodities.serving import gateway

    recorded = {}

    def recorder(query, params, **kwargs):
        recorded["query"] = query
        recorded["params"] = {p.name: p for p in params}
        return "df"

    monkeypatch.setattr(gateway, "run_query", recorder)
    monkeypatch.setattr(gateway, "get_settings", lambda: _isolated_settings())
    app, cache = _bind_simplecache()

    with app.app_context():
        cache.clear()
        gateway.fetch_comex_overview(year_start=2019, ncm_codes=("08012100",), flow="export")

    assert "p.serving.serving_comex_annual" in recorded["query"]
    assert "sum(val_yearfx_usd)" in recorded["query"]
    assert "sum(net_weight_kg)" in recorded["query"]
    assert recorded["params"]["codes"].values == ["08012100"]
    assert recorded["params"]["flow"].value == "export"


def test_fetch_comtrade_partners_queries_annual_mart(monkeypatch):
    pytest.importorskip("flask_caching")
    from embrapa_commodities.serving import gateway

    recorded = {}

    def recorder(query, params, **kwargs):
        recorded["query"] = query
        recorded["params"] = {p.name: p for p in params}
        return "df"

    monkeypatch.setattr(gateway, "run_query", recorder)
    monkeypatch.setattr(gateway, "get_settings", lambda: _isolated_settings())
    app, cache = _bind_simplecache()

    with app.app_context():
        cache.clear()
        gateway.fetch_comtrade_partners(year_start=2022, cmd_codes=("440710",))

    assert "p.serving.serving_comtrade_annual" in recorded["query"]
    assert "group by partner_code" in recorded["query"]
    assert "case when flow = 'export'" in recorded["query"]
    assert recorded["params"]["codes"].values == ["440710"]
    # The multi-reporter mart is pinned to Brazil so the partner ranking is
    # 'Brazil's trade with X', not 'the world's trade with X' (the all-reporters
    # years 2022-2023 would otherwise multi-count).
    assert "reporter_iso_a3 = @reporter" in recorded["query"]
    assert recorded["params"]["reporter"].value == "BRA"


def test_fetch_comtrade_flows_pins_reporter_to_brazil(monkeypatch):
    pytest.importorskip("flask_caching")
    from embrapa_commodities.serving import gateway

    recorded = {}

    def recorder(query, params, **kwargs):
        recorded["query"] = query
        recorded["params"] = {p.name: p for p in params}
        return "df"

    monkeypatch.setattr(gateway, "run_query", recorder)
    monkeypatch.setattr(gateway, "get_settings", lambda: _isolated_settings())
    app, cache = _bind_simplecache()

    with app.app_context():
        cache.clear()
        gateway.fetch_comtrade_flows(year_start=2022, cmd_codes=("440710",), flow="export")

    assert "p.serving.serving_comtrade_annual" in recorded["query"]
    assert "group by reporter_code, partner_code" in recorded["query"]
    # Reporter pinned to Brazil → the Sankey shows Brazil's own links, not every
    # reporter's flows blended (the all-reporters years would surface non-BR origins).
    assert "reporter_iso_a3 = @reporter" in recorded["query"]
    assert recorded["params"]["reporter"].value == "BRA"
    assert recorded["params"]["flow"].value == "export"


def test_fetch_comex_partners_does_not_pin_a_reporter(monkeypatch):
    """COMEX is Brazil's own customs (no reporter concept), so its readers must NOT
    add a reporter predicate — only the multi-reporter COMTRADE mart needs it."""
    pytest.importorskip("flask_caching")
    from embrapa_commodities.serving import gateway

    recorded = {}

    def recorder(query, params, **kwargs):
        recorded["query"] = query
        recorded["params"] = {p.name: p for p in params}
        return "df"

    monkeypatch.setattr(gateway, "run_query", recorder)
    monkeypatch.setattr(gateway, "get_settings", lambda: _isolated_settings())
    app, cache = _bind_simplecache()

    with app.app_context():
        cache.clear()
        gateway.fetch_comex_partners(year_start=2022, ncm_codes=("08012100",))

    assert "reporter" not in recorded["query"]
    assert "reporter" not in recorded["params"]


def test_fetch_comtrade_overview_pins_reporter_to_brazil(monkeypatch):
    """The UN COMTRADE banco's OWN overviewTS must be Brazil's view, not a sum over
    every reporter — the serving_comtrade_annual mart is multi-reporter, so the
    all-reporters years (2022-2023) would otherwise add the whole world's trade
    (regression guard for the NUM-1 audit finding)."""
    pytest.importorskip("flask_caching")
    from embrapa_commodities.serving import gateway

    recorded = {}

    def recorder(query, params, **kwargs):
        recorded["query"] = query
        recorded["params"] = {p.name: p for p in params}
        return "df"

    monkeypatch.setattr(gateway, "run_query", recorder)
    monkeypatch.setattr(gateway, "get_settings", lambda: _isolated_settings())
    app, cache = _bind_simplecache()

    with app.app_context():
        cache.clear()
        gateway.fetch_comtrade_overview(year_start=2022, cmd_codes=("440710",))

    assert "p.serving.serving_comtrade_annual" in recorded["query"]
    assert "reporter_iso_a3 = @reporter" in recorded["query"]
    assert recorded["params"]["reporter"].value == "BRA"


def test_fetch_product_timeseries_pins_reporter_only_for_comtrade(monkeypatch):
    """productTS for the multi-reporter COMTRADE mart pins Brazil (NUM-1); the
    single-reporter production marts (PEVS/PAM/PPM) and Brazil's-own-customs COMEX
    must NOT add a reporter predicate."""
    pytest.importorskip("flask_caching")
    from embrapa_commodities.serving import gateway

    recorded = {}

    def recorder(query, params, **kwargs):
        recorded["query"] = query
        recorded["params"] = {p.name: p for p in params}
        return "df"

    monkeypatch.setattr(gateway, "run_query", recorder)
    monkeypatch.setattr(gateway, "get_settings", lambda: _isolated_settings())
    app, cache = _bind_simplecache()

    with app.app_context():
        cache.clear()
        gateway.fetch_product_timeseries("un_comtrade", year_start=2022, codes=("440710",))
    assert "reporter_iso_a3 = @reporter" in recorded["query"]
    assert recorded["params"]["reporter"].value == "BRA"

    with app.app_context():
        cache.clear()
        gateway.fetch_product_timeseries("ibge_pevs", year_start=2022, codes=("3405",))
    assert "reporter" not in recorded["query"]
    assert "reporter" not in recorded["params"]


@pytest.mark.parametrize(
    ("call", "expect_table"),
    [
        # PEVS/PAM production readers resolve the mart via _PRODUCTION_MART[source].
        (
            lambda g: g.fetch_production_by_uf_yearly(
                year_start=2020, product_codes=("1",), source="ibge_pevs"
            ),
            "serving_pevs_annual",
        ),
        (
            lambda g: g.fetch_productivity("2713", source="ibge_pam", year_start=2020),
            "serving_pam_annual",
        ),
        # Trade annual/by-uf/flow readers pin their hard-coded mart.
        (
            lambda g: g.fetch_comtrade_overview(year_start=2020, cmd_codes=("44",)),
            "serving_comtrade_annual",
        ),
        (
            lambda g: g.fetch_comex_by_uf_yearly(year_start=2020, ncm_codes=("44",)),
            "serving_comex_annual",
        ),
        (
            lambda g: g.fetch_comex_flows(year_start=2020, ncm_codes=("44",), flow="export"),
            "serving_comex_annual",
        ),
        (
            lambda g: g.fetch_products_by_uf(
                table_key="serving_comex_annual",
                code_column="ncm_code",
                name_column="ncm_description",
            ),
            "serving_comex_annual",
        ),
        # Quality readers' KNOWN-source branch hits the Gold table (the None branch
        # for an unknown source is covered separately).
        (lambda g: g.fetch_quality_timeseries("ibge_pevs"), "gold_pevs_production"),
        (lambda g: g.fetch_quality_by_product("ibge_pevs"), "gold_pevs_production"),
        # CPC value reads Bronze (the only place the customs dimension survives).
        (lambda g: g.fetch_comtrade_cpc_value(codes=("0801",)), "comtrade_flows_raw"),
        # Curation flow-market log lives in research_inputs.
        (lambda g: g.fetch_current_flow_market(), "flow_market_log"),
    ],
)
def test_gateway_readers_build_expected_table_query(monkeypatch, call, expect_table):
    """Each cache-backed reader builds a query against the EXPECTED table — running
    the table/column wiring that was otherwise never executed in tests. A wrong
    mart/dataset name is a silent prod 404/400, so this locks the source→table
    mapping. Mirrors the per-reader gateway tests above."""
    pytest.importorskip("flask_caching")
    from embrapa_commodities.serving import gateway

    recorded = {}

    def recorder(query, params, **kwargs):
        recorded["query"] = query
        return "df"

    monkeypatch.setattr(gateway, "run_query", recorder)
    monkeypatch.setattr(gateway, "get_settings", lambda: _isolated_settings())
    app, cache = _bind_simplecache()

    with app.app_context():
        cache.clear()
        result = call(gateway)

    assert result == "df"
    assert expect_table in recorded["query"]


def test_visibility_clause_and_builder_injection():
    """The F7 visibility predicate (sql.visibility_clause) builds the NOT EXISTS over
    dim_commodity_visibility, and the direct-Gold builders inject it only when passed."""
    from embrapa_commodities.serving import sql

    clause = sql.visibility_clause(_isolated_settings(), "pevs", "product_code")
    assert "not exists" in clause.lower() and "dim_commodity_visibility" in clause
    assert "v.source = 'pevs'" in clause
    assert "product_code like v.code_prefix || '%'" in clause
    # default empty → no gate injected (back-compat)
    ts0, _ = sql.quality_timeseries("t")
    assert "not exists" not in ts0.lower()
    # passed → injected into the WHERE
    ts1, _ = sql.quality_timeseries("t", visibility_predicate=clause)
    assert clause in ts1
    bp1, _ = sql.quality_by_product(
        "t",
        code_column="product_code",
        name_column="product_description",
        visibility_predicate=clause,
    )
    assert clause in bp1


def test_quality_readers_thread_f7_visibility_gate(monkeypatch):
    """The gateway's direct-Gold readers (quality timeseries/by-product, município cube)
    thread the F7 visibility gate — a deep-link to a hidden commodity is excluded even
    though these bypass the (already-gated) serving marts. Uses each source's short token
    + its own code column."""
    pytest.importorskip("flask_caching")
    from embrapa_commodities.serving import gateway

    recorded = {}
    monkeypatch.setattr(gateway, "run_query", lambda q, p, **kw: recorded.update(query=q) or "df")
    monkeypatch.setattr(gateway, "get_settings", lambda: _isolated_settings())
    app, cache = _bind_simplecache()
    with app.app_context():
        cache.clear()
        gateway.fetch_quality_timeseries("mdic_comex")
        assert "dim_commodity_visibility" in recorded["query"]
        assert "v.source = 'comex'" in recorded["query"]
        assert "ncm_code like v.code_prefix" in recorded["query"]

        cache.clear()
        gateway.fetch_quality_by_product("ibge_pevs")
        assert "dim_commodity_visibility" in recorded["query"]
        assert "v.source = 'pevs'" in recorded["query"]

        cache.clear()
        gateway.fetch_production_by_municipio_yearly(source="ibge_ppm", city_codes=("1100015",))
        assert "dim_commodity_visibility" in recorded["query"]
        assert "v.source = 'ppm'" in recorded["query"]


def test_inspect_visibility_predicate_gates_gold_facts_only(monkeypatch):
    """The Dados raw-row inspector gates ONLY the Gold facts — the serving marts are already
    gated at build time. _inspect_visibility_predicate returns the F7 NOT EXISTS for a Gold table
    and '' for a serving mart / unknown source."""
    from embrapa_commodities.serving import gateway

    monkeypatch.setattr(gateway, "get_settings", lambda: _isolated_settings())
    pred = gateway._inspect_visibility_predicate("ibge_pevs", "gold_pevs_production")
    assert "dim_commodity_visibility" in pred
    assert "v.source = 'pevs'" in pred
    assert "product_code like v.code_prefix" in pred
    cpred = gateway._inspect_visibility_predicate("mdic_comex", "gold_comex_flows")
    assert "v.source = 'comex'" in cpred and "ncm_code like v.code_prefix" in cpred
    # serving marts already gated at build → no extra predicate; unknown → none either
    assert gateway._inspect_visibility_predicate("ibge_pevs", "serving_pevs_annual") == ""
    assert gateway._inspect_visibility_predicate("nope", "whatever") == ""


def test_raw_table_builders_inject_visibility_predicate():
    """The Dados Gold-fact SQL builders AND-in the F7 predicate only when given (back-compat)."""
    from embrapa_commodities.serving import sql

    cols = {"product_code": "STRING", "reference_year": "INT64"}
    pred = "not exists (select 1 from x)"
    rows_sql, _ = sql.raw_table_rows("t", columns_types=cols, limit=5, visibility_predicate=pred)
    assert pred in rows_sql
    cnt_sql, _ = sql.raw_table_count("t", columns_types=cols, visibility_predicate=pred)
    assert pred in cnt_sql
    rows0, _ = sql.raw_table_rows("t", columns_types=cols, limit=5)
    assert "not exists" not in rows0.lower()


def test_fetch_quality_by_source_queries_quality_mart(monkeypatch):
    pytest.importorskip("flask_caching")
    from embrapa_commodities.serving import gateway

    recorded = {}

    def recorder(query, params, **kwargs):
        recorded["query"] = query
        recorded["params"] = {p.name: p for p in params}
        return "df"

    monkeypatch.setattr(gateway, "run_query", recorder)
    monkeypatch.setattr(gateway, "get_settings", lambda: _isolated_settings())
    app, cache = _bind_simplecache()

    with app.app_context():
        cache.clear()
        gateway.fetch_quality_by_source(source="un_comtrade")

    assert "p.serving.serving_quality_by_source" in recorded["query"]
    assert "data_quality_flag" in recorded["query"]
    assert recorded["params"]["source"].value == "un_comtrade"


def test_fetch_products_dispatches_to_source_mart(monkeypatch):
    pytest.importorskip("flask_caching")
    from embrapa_commodities.serving import gateway

    recorded = {}

    def recorder(query, params, **kwargs):
        recorded["query"] = query
        return "df"

    monkeypatch.setattr(gateway, "run_query", recorder)
    monkeypatch.setattr(gateway, "get_settings", lambda: _isolated_settings())
    app, cache = _bind_simplecache()

    with app.app_context():
        cache.clear()
        gateway.fetch_products("un_comtrade")

    assert "p.serving.serving_comtrade_annual" in recorded["query"]
    assert "group by cmd_code" in recorded["query"]
    # a non-livestock source must NOT request measure_kind (its mart lacks the column)
    assert "measure_kind" not in recorded["query"]


def test_fetch_products_requests_measure_kind_for_livestock(monkeypatch):
    """PPM is the one source whose mart carries measure_kind; fetch_products opts it
    in so the snapshot can gate the herd ('Rebanho') view on stock vs flow."""
    pytest.importorskip("flask_caching")
    from embrapa_commodities.serving import gateway

    recorded = {}

    def recorder(query, params, **kwargs):
        recorded["query"] = query
        return "df"

    monkeypatch.setattr(gateway, "run_query", recorder)
    monkeypatch.setattr(gateway, "get_settings", lambda: _isolated_settings())
    app, cache = _bind_simplecache()

    with app.app_context():
        cache.clear()
        gateway.fetch_products("ibge_ppm")

    assert "p.serving.serving_ppm_annual" in recorded["query"]
    assert "any_value(measure_kind) as measure_kind" in recorded["query"]


def test_fetch_product_timeseries_uses_source_default_value_column(monkeypatch):
    pytest.importorskip("flask_caching")
    from embrapa_commodities.serving import gateway

    recorded = {}

    def recorder(query, params, **kwargs):
        recorded["query"] = query
        recorded["params"] = {p.name: p for p in params}
        return "df"

    monkeypatch.setattr(gateway, "run_query", recorder)
    monkeypatch.setattr(gateway, "get_settings", lambda: _isolated_settings())
    app, cache = _bind_simplecache()

    with app.app_context():
        cache.clear()
        gateway.fetch_product_timeseries("ibge_pevs", year_start=2010, codes=("3405",))

    assert "p.serving.serving_pevs_annual" in recorded["query"]
    assert "sum(val_real_ipca_brl)" in recorded["query"]  # PEVS default value column
    assert "group by product_code, reference_year" in recorded["query"]
    assert recorded["params"]["codes"].values == ["3405"]


def test_fetch_source_metadata_reads_gold_dataset(monkeypatch):
    pytest.importorskip("flask_caching")
    from embrapa_commodities.serving import gateway

    recorded = {}

    def recorder(query, params, **kwargs):
        recorded["query"] = query
        recorded["params"] = {p.name: p for p in params}
        return "df"

    monkeypatch.setattr(gateway, "run_query", recorder)
    monkeypatch.setattr(gateway, "get_settings", lambda: _isolated_settings())
    app, cache = _bind_simplecache()

    with app.app_context():
        cache.clear()
        gateway.fetch_source_metadata(source="ibge_pevs")

    assert "p.gold.gold_source_metadata" in recorded["query"]
    assert recorded["params"]["source"].value == "ibge_pevs"


def test_fetch_products_unknown_source_raises(monkeypatch):
    pytest.importorskip("flask_caching")
    from embrapa_commodities.serving import gateway

    monkeypatch.setattr(gateway, "run_query", lambda *a, **k: pytest.fail("must reject"))
    monkeypatch.setattr(gateway, "get_settings", lambda: _isolated_settings())
    app, cache = _bind_simplecache()

    with app.app_context():
        cache.clear()
        with pytest.raises(ValueError, match="unknown source"):
            gateway.fetch_products("nope")


def test_fetch_cross_series_brazil_metric_filters_reporter(monkeypatch):
    pytest.importorskip("flask_caching")
    from embrapa_commodities.serving import gateway

    recorded = {}

    def recorder(query, params, **kwargs):
        recorded["query"] = query
        recorded["params"] = {p.name: p for p in params}
        return "df"

    monkeypatch.setattr(gateway, "run_query", recorder)
    monkeypatch.setattr(gateway, "get_settings", lambda: _isolated_settings())
    app, cache = _bind_simplecache()

    with app.app_context():
        cache.clear()
        gateway.fetch_cross_series("un_comtrade:exp_value", year_start=2022, codes=("440710",))

    assert "p.serving.serving_comtrade_annual" in recorded["query"]
    assert "reporter_iso_a3 = @reporter" in recorded["query"]
    assert recorded["params"]["reporter"].value == "BRA"
    assert recorded["params"]["flow"].value == "export"


def test_fetch_cross_series_world_exp_sums_all_reporters(monkeypatch):
    pytest.importorskip("flask_caching")
    from embrapa_commodities.serving import gateway

    recorded = {}

    def recorder(query, params, **kwargs):
        recorded["query"] = query
        recorded["params"] = {p.name: p for p in params}
        return "df"

    monkeypatch.setattr(gateway, "run_query", recorder)
    monkeypatch.setattr(gateway, "get_settings", lambda: _isolated_settings())
    app, cache = _bind_simplecache()

    with app.app_context():
        cache.clear()
        gateway.fetch_cross_series("un_comtrade:world_exp", year_start=2022)

    assert "@reporter" not in recorded["query"]  # world total — no Brazil filter


def test_fetch_cross_series_unknown_metric_raises(monkeypatch):
    pytest.importorskip("flask_caching")
    from embrapa_commodities.serving import gateway

    monkeypatch.setattr(gateway, "run_query", lambda *a, **k: pytest.fail("must reject"))
    monkeypatch.setattr(gateway, "get_settings", lambda: _isolated_settings())
    app, cache = _bind_simplecache()

    with app.app_context():
        cache.clear()
        with pytest.raises(ValueError, match="unknown cross metric"):
            gateway.fetch_cross_series("bogus:metric")


@pytest.mark.parametrize("fetch_name", ["fetch_production_overview", "fetch_production_by_uf"])
def test_gateway_rejects_invalid_value_column(monkeypatch, fetch_name):
    """The allowlist is enforced THROUGH the gateway, not only the bare builder."""
    pytest.importorskip("flask_caching")
    from embrapa_commodities.serving import gateway

    monkeypatch.setattr(
        gateway, "run_query", lambda *a, **k: pytest.fail("must reject before querying")
    )
    monkeypatch.setattr(gateway, "get_settings", lambda: _isolated_settings())
    app, cache = _bind_simplecache()

    with app.app_context():
        cache.clear()
        with pytest.raises(ValueError, match="not allowed"):
            getattr(gateway, fetch_name)(value_column="evil; drop table gold")


# ── gateway.run_query: client wiring ──────────────────────────────────────────


def test_run_query_executes_with_parameterized_job_config(monkeypatch):
    pytest.importorskip("flask_caching")
    from embrapa_commodities.serving import gateway

    fake_client = mock.Mock()
    fake_client.query.return_value.result.return_value.to_dataframe.return_value = "DF"
    monkeypatch.setattr(gateway, "_client", lambda: fake_client)
    monkeypatch.setattr(
        gateway, "get_settings", lambda: _isolated_settings(bq_max_bytes_billed=4242)
    )

    params = [bigquery.ScalarQueryParameter("year_start", "INT64", 2000)]
    result = gateway.run_query("select 1", params)

    assert result == "DF"
    sent_sql = fake_client.query.call_args.args[0]
    assert sent_sql == "select 1"
    job_config = fake_client.query.call_args.kwargs["job_config"]
    assert job_config.query_parameters == params
    # The serving cost ceiling is applied to the job (Settings.bq_max_bytes_billed).
    assert job_config.maximum_bytes_billed == 4242
    # BQ Storage client disabled (avoids an extra dependency/permission at read).
    to_df = fake_client.query.return_value.result.return_value.to_dataframe
    assert to_df.call_args.kwargs["create_bqstorage_client"] is False


# ── cache.init_cache: backend selection ───────────────────────────────────────


def test_init_cache_selects_simplecache_by_default():
    pytest.importorskip("flask_caching")
    from flask import Flask

    from embrapa_commodities.serving.cache import init_cache

    app = Flask(__name__)
    init_cache(app, _isolated_settings())
    # app.extensions["cache"] maps the Cache instance -> its bound backend object.
    backend = next(iter(app.extensions["cache"].values()))
    assert type(backend).__name__ == "SimpleCache"


def test_init_cache_selects_redis_when_configured(monkeypatch):
    """RedisCache + URL is passed through when configured (no real Redis needed)."""
    pytest.importorskip("flask_caching")
    from flask import Flask

    from embrapa_commodities.serving import cache as cache_mod

    # init_app on RedisCache would try to import/connect redis; stub init_app to
    # capture the config the backend WOULD receive (we test selection, not redis).
    captured = {}
    monkeypatch.setattr(
        cache_mod.cache,
        "init_app",
        lambda server, config: captured.update(config),
    )
    # The TTL-binding step pokes gateway; make it a harmless no-op here.
    monkeypatch.setattr(cache_mod, "_bind_classification_ttl", lambda t: None)

    settings = _isolated_settings(
        cache_type="RedisCache",
        cache_redis_url="redis://cache:6379/0",
    )
    cache_mod.init_cache(Flask(__name__), settings)

    assert captured["CACHE_TYPE"] == "RedisCache"
    assert captured["CACHE_REDIS_URL"] == "redis://cache:6379/0"


def test_init_cache_safely_logs_loud_error_and_falls_back_to_nullcache(monkeypatch, caplog):
    """A misconfigured prod must FAIL LOUD: the NullCache fallback still binds (so
    the app boots) but the failure is logged at ERROR and the message states that
    caching is DISABLED and the curation-cache invalidation guarantees are void."""
    pytest.importorskip("flask_caching")
    import logging

    from flask import Flask

    from embrapa_commodities.serving import cache as cache_mod

    def boom(server):
        raise RuntimeError("gcp_project_id Field required")

    monkeypatch.setattr(cache_mod, "init_cache", boom)

    app = Flask(__name__)
    with caplog.at_level(logging.WARNING, logger=cache_mod.logger.name):
        cache_mod.init_cache_safely(app)

    # Fallback control flow is unchanged: a NullCache is bound so the app still boots.
    backend = next(iter(app.extensions["cache"].values()))
    assert type(backend).__name__ == "NullCache"

    # The failure is now loud (ERROR, not WARNING) and explicit about the impact.
    record = next(r for r in caplog.records if r.name == cache_mod.logger.name)
    assert record.levelno == logging.ERROR
    msg = record.getMessage().lower()
    assert "disabled" in msg
    assert "invalidation" in msg  # curation-cache invalidation guarantees are void


# ── curation: cache invalidation on save (the "scales without Redis" pillar) ──


def test_save_invalidates_code_industrialization_cache(monkeypatch):
    """record_code_industrialization(invalidate_cache=True) forces the next read to re-query.

    This is the core of "scales to N Cloud Run instances without Redis": the
    writing instance drops its cached classification so the edit is immediately
    visible locally (other instances converge within the short TTL).
    """
    pytest.importorskip("flask_caching")
    from embrapa_commodities.serving import attribute_engineering as curation
    from embrapa_commodities.serving import gateway

    app, cache = _bind_simplecache()

    calls = {"n": 0}

    def fake_run(query, params):
        calls["n"] += 1
        return [("mdic_comex", "08013200", "processada")]

    monkeypatch.setattr(gateway, "run_query", fake_run)
    monkeypatch.setattr(gateway, "get_settings", lambda: _isolated_settings())
    monkeypatch.setattr(curation, "ensure_dataset", lambda *a, **k: None)  # writer self-heals

    bq_client = mock.Mock()
    bq_client.query.return_value.result.return_value = None
    headers = {iap.IAP_EMAIL_HEADER: "accounts.google.com:alice@embrapa.br"}

    with app.app_context():
        cache.clear()
        gateway.fetch_current_code_industrialization()  # warms cache → 1 query
        gateway.fetch_current_code_industrialization()  # cached → still 1
        assert calls["n"] == 1

        curation.record_code_industrialization(
            "mdic_comex",
            "08013200",
            "processada",
            headers,
            settings=_isolated_settings(),
            client=bq_client,
            invalidate_cache=True,
        )

        gateway.fetch_current_code_industrialization()  # cache dropped → re-queries
        assert calls["n"] == 2


def test_invalidate_code_industrialization_cache_is_safe_when_unbound(monkeypatch):
    """With no Flask app bound, invalidation is a no-op (covers the except branch)."""
    pytest.importorskip("flask_caching")
    from embrapa_commodities.serving import attribute_engineering as curation
    from embrapa_commodities.serving.cache import Cache, cache

    # Reset to a pristine, unbound cache so delete_memoized raises internally and
    # the best-effort guard swallows it without propagating.
    monkeypatch.setattr(curation, "cache", Cache())
    try:
        curation.invalidate_code_industrialization_cache()  # must not raise
    finally:
        # Leave the module-level singleton as the test found it.
        assert cache is not None


# ── curation: free-text size guards (open vocabulary, bounded length) ─────────


def test_record_code_industrialization_rejects_overlong_level():
    pytest.importorskip("flask_caching")
    from embrapa_commodities.serving import attribute_engineering as curation

    headers = {iap.IAP_EMAIL_HEADER: "accounts.google.com:alice@embrapa.br"}
    with pytest.raises(ValueError, match="industrialization_level excede"):
        curation.record_code_industrialization(
            "mdic_comex",
            "08013200",
            "x" * (curation.MAX_STAGE_LEN + 1),
            headers,
            settings=_settings(),
            client=mock.Mock(),
        )


def test_record_code_industrialization_rejects_overlong_note():
    pytest.importorskip("flask_caching")
    from embrapa_commodities.serving import attribute_engineering as curation

    headers = {iap.IAP_EMAIL_HEADER: "accounts.google.com:alice@embrapa.br"}
    with pytest.raises(ValueError, match="note excede"):
        curation.record_code_industrialization(
            "mdic_comex",
            "08013200",
            "processada",
            headers,
            note="n" * (curation.MAX_NOTE_LEN + 1),
            settings=_settings(),
            client=mock.Mock(),
        )


def test_record_code_industrialization_accepts_free_text_level(monkeypatch):
    """A novel, non-allowlisted level label is accepted (open vocabulary by design)."""
    pytest.importorskip("flask_caching")
    from embrapa_commodities.serving import attribute_engineering as curation

    monkeypatch.setattr(curation, "ensure_dataset", lambda *a, **k: None)  # writer self-heals
    client = mock.Mock()
    client.query.return_value.result.return_value = None
    headers = {iap.IAP_EMAIL_HEADER: "accounts.google.com:alice@embrapa.br"}

    record = curation.record_code_industrialization(
        "mdic_comex",
        "08013200",
        "nível-experimental-inédito",  # not in any allowlist — must be allowed
        headers,
        settings=_settings(),
        client=client,
        invalidate_cache=False,
    )
    assert record["industrialization_level"] == "nível-experimental-inédito"


# ── market-nature: customsCode × flowCode value + curated-purpose log ──────────


def test_comtrade_cpc_value_excludes_c00_aggregate_and_casts():
    query, params = sql.comtrade_cpc_value("p.bronze_comtrade.comtrade_flows_raw")
    low = query.lower()
    assert "customscode != 'c00'" in low  # the aggregate is excluded (no double-count)
    assert "safe_cast(primaryvalue as float64)" in low  # Bronze is all-STRING
    assert "safe_cast(refyear as int64)" in low
    assert "group by customs_code, flow_code, reference_year" in low
    assert params == []  # no commodity filter → no params


def test_comtrade_cpc_value_dedups_append_only_bronze():
    """The cpc read bypasses Silver, so it must mirror silver_comtrade_flows'
    cleaning: latest ingestion batch per (refYear, reporterCode) — without it the
    summed value inflates with every re-ingestion — then row-level dedup on the
    natural key with the qtyUnitCode collapse, plus the World/HS4 exclusions."""
    query, _ = sql.comtrade_cpc_value("p.bronze_comtrade.comtrade_flows_raw")
    flat = " ".join(query.lower().split())  # collapse whitespace for matching
    # Stage 1: a re-published reporter-year replaces the previous generation.
    assert "max(ingestion_timestamp) over (partition by refyear, reportercode)" in flat
    # Stage 2: row-level dedup — NOT partitioned by qtyUnitCode (its duplicate
    # variants carry an identical primaryValue), recency first, '-1' last.
    assert "row_number() over" in flat
    natural_key = (
        "partition by refyear, reportercode, partnercode, partner2code, "
        "cmdcode, flowcode, customscode, moscode, motcode"
    )
    assert natural_key in flat
    assert "order by ingestion_timestamp desc, (qtyunitcode = '-1')" in flat
    # Same exclusions as Silver: World partner aggregate + legacy HS4 rows.
    assert "partnercode != '0'" in flat
    assert "length(cmdcode) = 6" in flat
    # DBT-2: also pin the other three breakdown axes to '0' exactly like Silver, so the
    # customs-procedure sum can never pick up a mot/mos/partner2 breakdown row.
    assert "motcode = '0'" in flat
    assert "partner2code = '0'" in flat
    assert "moscode = '0'" in flat


def test_comtrade_cpc_value_filters_cmd_codes_when_scoped():
    query, params = sql.comtrade_cpc_value("t", codes=("0801", "44"))
    assert "cmdcode in unnest(@cmd_codes)" in query.lower()
    assert params[0].name == "cmd_codes" and list(params[0].values) == ["0801", "44"]


def test_comtrade_cpc_value_projects_columns_and_keeps_predicates_after_batch_selection():
    """M5 (byte budget WITHOUT a semantic change): the latest_batch scan must reduce
    bytes by PROJECTING an explicit column list (never `select *`) — Bronze is wide
    and all-STRING and this reader runs under maximum_bytes_billed. The row predicates
    must stay AFTER the max(ingestion_timestamp) batch-selection window (in the
    deduplicated CTE), byte-for-byte mirroring silver_comtrade_flows — filtering
    before the window could pick an older generation when the newest one's rows are
    all predicate-filtered (a retraction-resurrection divergence we must NOT
    introduce)."""
    query, _ = sql.comtrade_cpc_value("p.bronze_comtrade.comtrade_flows_raw", codes=("0801",))
    # Strip SQL line comments first so explanatory prose (which mentions "select *")
    # can't satisfy or break the STRUCTURAL assertions below — match real SQL only.
    code_only = "\n".join(line.split("--")[0] for line in query.splitlines())
    flat = " ".join(code_only.lower().split())  # collapse whitespace for matching

    # Column projection, not select-* — the actual byte lever in columnar BigQuery.
    assert "select *" not in flat, "latest_batch must project columns, not select *"
    assert "partner2code, cmdcode, moscode, motcode, qtyunitcode" in flat

    where_pos = flat.find("where customscode != 'c00'")
    window_pos = flat.find("max(ingestion_timestamp) over (partition by refyear, reportercode)")
    rownum_pos = flat.find("row_number() over")
    cmd_pos = flat.find("cmdcode in unnest(@cmd_codes)")

    # Batch selection (the window) comes FIRST; predicates + cmdCode scope apply AFTER
    # it — the only order that preserves silver_comtrade_flows' retraction semantics.
    assert window_pos != -1 and where_pos != -1
    assert window_pos < where_pos, "predicates must filter AFTER the batch-selection window"
    assert window_pos < cmd_pos, "the cmdCode scope must also apply after the window"
    # The dedup (row_number) runs on the chosen batch, after the predicates.
    assert window_pos < rownum_pos
    # The predicates live in the deduplicated CTE, scanning latest_batch (not the raw table).
    assert "from latest_batch where customscode != 'c00'" in flat


def test_current_flow_market_latest_wins_and_drops_cleared():
    query, params = sql.current_flow_market("p.research_inputs.flow_market_log")
    low = " ".join(query.lower().split())  # collapse whitespace for matching
    assert "row_number() over" in low
    # Latest-wins per pair, breaking same-microsecond ties on change_id DESC so a
    # clear-vs-set race resolves deterministically — same tiebreaker the code SCD2 uses
    # (DBT-3).
    assert "partition by customs_code, flow_code order by edited_at desc, change_id desc" in low
    assert "where rn = 1 and market != ''" in low  # a cleared (empty) market is dropped
    assert params == []


def test_record_flow_market_inserts_parameterized_row_with_author(monkeypatch):
    pytest.importorskip("flask_caching")
    from embrapa_commodities.serving import attribute_engineering as curation

    # Isolate the INSERT — the first-write auto-create is covered by its own test.
    monkeypatch.setattr(curation, "ensure_flow_market_log_table", lambda *a, **k: None)
    client = mock.Mock()
    client.query.return_value.result.return_value = None
    headers = {iap.IAP_EMAIL_HEADER: "accounts.google.com:alice@embrapa.br"}

    record = curation.record_flow_market(
        "C04",
        "M",
        "processamento",
        headers,
        settings=_settings(),
        client=client,
        invalidate_cache=False,
    )

    assert record["edited_by"] == "alice@embrapa.br"
    assert record["customs_code"] == "C04"
    assert record["flow_code"] == "M"
    assert record["market"] == "processamento"
    sql_text = client.query.call_args.args[0].lower()
    assert "insert into" in sql_text
    assert "current_timestamp()" in sql_text  # server-side stamp, not client clock
    params = {p.name: p.value for p in client.query.call_args.kwargs["job_config"].query_parameters}
    assert params["customs_code"] == "C04"
    assert params["flow_code"] == "M"
    assert params["market"] == "processamento"
    assert params["edited_by"] == "alice@embrapa.br"


def test_record_flow_market_rejects_empty_pair():
    pytest.importorskip("flask_caching")
    from embrapa_commodities.serving import attribute_engineering as curation

    headers = {iap.IAP_EMAIL_HEADER: "accounts.google.com:alice@embrapa.br"}
    with pytest.raises(ValueError):
        curation.record_flow_market(
            "", "M", "consumo", headers, settings=_settings(), client=mock.Mock()
        )


def test_record_flow_market_allows_empty_market_to_clear(monkeypatch):
    pytest.importorskip("flask_caching")
    from embrapa_commodities.serving import attribute_engineering as curation

    monkeypatch.setattr(curation, "ensure_flow_market_log_table", lambda *a, **k: None)
    client = mock.Mock()
    client.query.return_value.result.return_value = None
    headers = {iap.IAP_EMAIL_HEADER: "accounts.google.com:alice@embrapa.br"}
    # market='' is the explicit "a classificar" clear — recorded, not rejected.
    record = curation.record_flow_market(
        "C04", "M", "", headers, settings=_settings(), client=client, invalidate_cache=False
    )
    assert record["market"] == ""


def test_ensure_flow_market_log_table_creates_with_explicit_schema(monkeypatch):
    pytest.importorskip("flask_caching")
    from embrapa_commodities.serving import attribute_engineering as curation

    monkeypatch.setattr(curation, "ensure_dataset", lambda *a, **k: None)
    client = mock.Mock()
    fqn = curation.ensure_flow_market_log_table(settings=_settings(), client=client)

    assert fqn.endswith(".flow_market_log")
    table_arg = client.create_table.call_args.args[0]
    assert {f.name for f in table_arg.schema} == {
        "customs_code",
        "flow_code",
        "market",
        "edited_by",
        "edited_at",
        "change_id",
    }
    assert table_arg.clustering_fields == ["customs_code", "flow_code"]
    assert client.create_table.call_args.kwargs["exists_ok"] is True


# ── gateway: PAM rides the PEVS-shaped production registries ───────────────────
def test_gateway_production_mart_resolves_pevs_pam_and_ppm():
    """fetch_production_* are generic over the PEVS-shaped marts; PAM + PPM are registered."""
    pytest.importorskip("flask_caching")
    from embrapa_commodities.serving import gateway

    assert gateway._production_mart("ibge_pevs") == "serving_pevs_annual"
    assert gateway._production_mart("ibge_pam") == "serving_pam_annual"
    assert gateway._production_mart("ibge_ppm") == "serving_ppm_annual"
    with pytest.raises(ValueError, match="unknown production source"):
        gateway._production_mart("mdic_comex")  # trade mart is a different shape


def test_gateway_pam_in_product_and_gold_registries():
    """PAM is wired into the source-parameterized products / quality readers."""
    pytest.importorskip("flask_caching")
    from embrapa_commodities.serving import gateway

    assert gateway._product_source("ibge_pam")[0] == "serving_pam_annual"
    assert gateway._GOLD_TABLE["ibge_pam"] == "gold_pam_production"
    assert gateway._GOLD_PRODUCT["ibge_pam"] == ("product_code", "product_description")


def test_gateway_ppm_in_product_and_gold_registries():
    """PPM (livestock, PEVS-shaped) rides the same source-parameterized readers."""
    pytest.importorskip("flask_caching")
    from embrapa_commodities.serving import gateway

    assert gateway._product_source("ibge_ppm")[0] == "serving_ppm_annual"
    assert gateway._product_source("ibge_ppm")[3] == "val_real_ipca_brl"  # BRL-native default
    assert gateway._GOLD_TABLE["ibge_ppm"] == "gold_ppm_production"
    assert gateway._GOLD_PRODUCT["ibge_ppm"] == ("product_code", "product_description")


# ── P6: per-UF scoping of the cross-source / seasonality readers ────────────────


def test_cross_source_builders_narrow_to_uf_when_uf_codes_given():
    """production_overview / product_timeseries / cross_annual / comex_seasonality
    all add a bound ``state_acronym IN UNNEST(@uf_codes)`` predicate (P6 per-UF)."""
    q_prod, p_prod = sql.production_overview("p.s.pevs", uf_codes=("AC",))
    assert "state_acronym in unnest(@uf_codes)" in q_prod.lower()
    assert {p.name: p for p in p_prod}["uf_codes"].values == ["AC"]

    q_ts, _ = sql.product_timeseries("p.s.pevs", code_column="product_code", uf_codes=("AC", "PA"))
    assert "state_acronym in unnest(@uf_codes)" in q_ts.lower()

    q_cross, _ = sql.cross_annual(
        "p.s.comex", measure_column="val_yearfx_usd", code_column="ncm_code", uf_codes=("AC",)
    )
    assert "state_acronym in unnest(@uf_codes)" in q_cross.lower()

    q_seas, _ = sql.comex_seasonality("p.s.seas", uf_codes=("AC",))
    assert "state_acronym in unnest(@uf_codes)" in q_seas.lower()


def test_cross_source_builders_no_uf_predicate_when_empty():
    """No uf_codes → no state predicate (national, the unchanged default)."""
    q_prod, _ = sql.production_overview("p.s.pevs")
    assert "state_acronym" not in q_prod.lower()
    q_seas, _ = sql.comex_seasonality("p.s.seas")
    assert "state_acronym" not in q_seas.lower()


def test_fetch_cross_series_drops_uf_for_comtrade(monkeypatch):
    """The gateway applies uf_codes ONLY for the COMEX mart — a COMTRADE metric has
    no state_acronym column, so the UF filter is dropped (query stays valid).

    Uses _isolated_settings + _bind_simplecache (NOT create_app) so it runs in CI
    without a real .env / GCP_PROJECT_ID."""
    pytest.importorskip("flask_caching")
    from embrapa_commodities.serving import gateway

    recorded = {}

    def fake_run(sql_text, params):
        recorded["sql"] = sql_text
        return "df"

    monkeypatch.setattr(gateway, "run_query", fake_run)
    monkeypatch.setattr(gateway, "get_settings", lambda: _isolated_settings())
    app, cache = _bind_simplecache()
    with app.app_context():
        cache.clear()
        # COMEX metric → UF predicate present
        gateway.fetch_cross_series("mdic_comex:exp_value", uf_codes=("AC",))
        assert "state_acronym in unnest(@uf_codes)" in recorded["sql"].lower()
        cache.clear()
        # COMTRADE metric → UF dropped (no state_acronym on that mart)
        gateway.fetch_cross_series("un_comtrade:world_exp", uf_codes=("AC",))
        assert "state_acronym" not in recorded["sql"].lower()


# ── Raw table inspection ("Dados" perspective) ────────────────────────────────


def test_raw_table_rows_validates_columns_and_binds_filters():
    cols = {"reference_year": "INTEGER", "product_code": "STRING", "val_yearfx_brl": "FLOAT"}
    # an order-by outside the table's schema is rejected (the schema IS the allowlist)
    with pytest.raises(ValueError):
        sql.raw_table_rows("p.d.t", columns_types=cols, limit=50, order_by="evil")
    query, params = sql.raw_table_rows(
        "p.d.t",
        columns_types=cols,
        limit=50,
        offset=20,
        order_by="reference_year",
        order_dir="desc",
        filters=[
            {"col": "reference_year", "op": "eq", "val": "1999"},
            {"col": "product_code", "op": "contains", "val": "casta"},
        ],
    )
    assert "order by `reference_year` desc" in query
    assert "limit 50 offset 20" in query
    assert "`reference_year` = @f0" in query
    # contains → CONTAINS_SUBSTR with the search bound as a plain literal (no LIKE wildcards
    # to escape, so a value containing % or _ matches literally, not as a wildcard).
    assert "contains_substr(`product_code`, @f1)" in query
    by_name = {p.name: p for p in params}
    assert by_name["f0"].type_ == "INT64" and by_name["f0"].value == 1999  # coerced to int
    assert by_name["f1"].type_ == "STRING" and by_name["f1"].value == "casta"


def test_raw_table_rows_caps_limit_and_plain_browse_has_no_predicates():
    cols = {"reference_year": "INTEGER"}
    query, params = sql.raw_table_rows("p.d.t", columns_types=cols, limit=10**9)
    assert f"limit {sql.RAW_TABLE_MAX_LIMIT} offset 0" in query  # hard row cap
    assert "order by" not in query and "where" not in query
    assert params == []


def test_raw_table_count_applies_filters():
    cols = {"reference_year": "INTEGER"}
    query, params = sql.raw_table_count(
        "p.d.t",
        columns_types=cols,
        filters=[{"col": "reference_year", "op": "ge", "val": "2000"}],
    )
    assert "count(*)" in query and "`reference_year` >= @f0" in query
    assert params[0].value == 2000


def test_raw_table_rows_rejects_bad_op_and_unbindable_value():
    cols = {"reference_year": "INTEGER"}
    with pytest.raises(ValueError):  # operator not in the allowed set
        sql.raw_table_rows(
            "p.d.t",
            columns_types=cols,
            limit=10,
            filters=[{"col": "reference_year", "op": "DROP", "val": "1"}],
        )
    with pytest.raises(ValueError):  # 'abc' cannot bind to an INT column
        sql.raw_table_rows(
            "p.d.t",
            columns_types=cols,
            limit=10,
            filters=[{"col": "reference_year", "op": "eq", "val": "abc"}],
        )
    with pytest.raises(ValueError):  # a filter column outside the schema
        sql.raw_table_rows(
            "p.d.t",
            columns_types=cols,
            limit=10,
            filters=[{"col": "evil; drop table", "op": "eq", "val": "1"}],
        )


def test_gateway_inspectable_tables_and_allowlist_boundary():
    from embrapa_commodities.serving import gateway

    ppm = gateway.inspectable_tables("ibge_ppm")
    ids = [t["id"] for t in ppm]
    assert "gold_ppm_production" in ids and "serving_ppm_annual" in ids
    assert all(t.get("label") and t.get("grain") for t in ppm)
    comex_ids = [t["id"] for t in gateway.inspectable_tables("mdic_comex")]
    assert "serving_comex_seasonality" in comex_ids  # the monthly mart is inspectable too
    assert gateway.inspectable_tables("nope") == []
    # SECURITY: a (banco, table) outside the allowlist is refused (the rejection happens
    # before any table_ref/get_settings call, so no settings stub is needed here).
    with pytest.raises(ValueError):
        gateway._resolve_inspect_table("ibge_ppm", "gold_comex_flows")  # not PPM's table
    with pytest.raises(ValueError):
        gateway._resolve_inspect_table("ibge_pevs", "bronze_ibge")  # not allowlisted at all


def test_gateway_seed_catalog_and_allowlist_boundary():
    """The 'Referências' seed catalog: the editable flag distinguishes the editable
    catalog seed from the read-only CALIBRATION seeds, and an id outside the catalog is
    refused before any BigQuery / table_ref call (the security boundary)."""
    from embrapa_commodities.serving import gateway

    seeds = gateway.seed_tables()
    by_id = {s["id"]: s for s in seeds}
    # commodity_crosswalk became the editable Curadoria catalog — NO longer a read-only seed.
    assert "commodity_crosswalk" not in by_id
    # The remaining consultable seeds are read-only calibration / source-faithful data.
    assert {
        "historical_currency_factors",
        "unit_family_conversions",
        "ibge_municipio_mesh",
    } <= set(by_id)
    assert all(s.get("label") and s.get("description") for s in seeds)
    assert all(s["editable"] is False for s in seeds)
    # SECURITY: an id outside the catalog is refused (before any table_ref/get_settings),
    # including the RETIRED commodity_crosswalk seed and a real table that is NOT a seed.
    with pytest.raises(ValueError):
        gateway._resolve_seed_table("commodity_crosswalk")
    with pytest.raises(ValueError):
        gateway._resolve_seed_table("gold_pevs_production")
    with pytest.raises(ValueError):
        gateway._resolve_seed_table("../etc/passwd")


def test_serialize_seed_page_reuses_grid_and_adds_editable():
    """serialize_seed_page == the table-page grid shape + an ``editable`` flag; ``None``
    degrades to an empty, non-editable page (never crashes)."""
    import pandas as pd

    from embrapa_commodities.webapi import serializers

    page = {
        "columns": [{"name": "commodity_id", "type": "STRING"}],
        "df": pd.DataFrame({"commodity_id": ["acai"]}),
        "total": 1,
        "table": "commodity_crosswalk",
        "label": "Crosswalk de commodities",
        "grain": "Liga o mesmo produto entre as fontes.",
        "editable": True,
    }
    out = serializers.serialize_seed_page(page)
    assert out["editable"] is True
    assert out["table"] == "commodity_crosswalk"
    assert out["rows"] == [["acai"]]
    assert out["grain"].startswith("Liga o mesmo produto")
    empty = serializers.serialize_seed_page(None)
    assert empty["editable"] is False and empty["rows"] == []


# ── Curadoria (catalog): the editable commodity catalog writer ────────────────


def _catalog_row_obj(codigo, prefix):
    """A row stand-in for the prefix-disjointness read (has .codigo_commodity/.code_prefix)."""
    import collections

    return collections.namedtuple("R", ["codigo_commodity", "code_prefix"])(codigo, prefix)


def test_slug_matches_seed_commodity_ids():
    from embrapa_commodities.serving import curation

    assert curation._slug("Castanha-do-pará") == "castanha_do_para"
    assert curation._slug("Açaí") == "acai"
    assert curation._slug("Soja") == "soja"
    assert curation._slug("") == ""


def test_assert_prefix_disjoint_rejects_overlap_but_allows_same_key():
    from embrapa_commodities.serving import curation

    # A new prefix that is a prefix of (or prefixed by) an existing one in the banco fans
    # out the cross-source join → reject.
    with pytest.raises(ValueError):
        curation._assert_prefix_disjoint("4403", "440", [("9999", "4403")])
    # Updating the SAME entry (same codigo) is never a conflict with itself.
    curation._assert_prefix_disjoint("4403", "4403", [("4403", "44")])
    # Genuinely disjoint prefixes are fine.
    curation._assert_prefix_disjoint("4407", "4407", [("4403", "4403")])


def test_record_commodity_catalog_inserts_active_row_with_author(monkeypatch):
    pytest.importorskip("flask_caching")
    from embrapa_commodities.serving import curation

    monkeypatch.setattr(curation, "ensure_dataset", lambda *a, **k: None)
    client = mock.Mock()
    client.query.return_value.result.return_value = []  # empty disjoint-read + insert ok
    headers = {iap.IAP_EMAIL_HEADER: "accounts.google.com:alice@embrapa.br"}

    rec = curation.record_commodity_catalog(
        "4403",
        "un_comtrade",
        headers,
        agrupamento="Madeira",
        ciclo_de_vida="Fazer Ingestão e deixar disponível",
        settings=_settings(),
        client=client,
        invalidate_cache=False,
    )

    assert rec["edited_by"] == "alice@embrapa.br"
    assert rec["codigo_commodity"] == "4403" and rec["banco"] == "un_comtrade"
    assert rec["active"] is True
    assert rec["code_prefix"] == "4403"  # defaults to codigo_commodity
    assert rec["commodity_id"] == "madeira"  # slug of the agrupamento
    sql_text = client.query.call_args.args[0].lower()  # the LAST query is the INSERT
    assert "insert into" in sql_text and "current_timestamp()" in sql_text
    params = {p.name: p.value for p in client.query.call_args.kwargs["job_config"].query_parameters}
    assert params["codigo_commodity"] == "4403" and params["active"] is True


def test_record_commodity_catalog_rejects_blank_key():
    pytest.importorskip("flask_caching")
    from embrapa_commodities.serving import curation

    headers = {iap.IAP_EMAIL_HEADER: "accounts.google.com:alice@embrapa.br"}
    with pytest.raises(ValueError):  # blank codigo_commodity breaks the key → reject
        curation.record_commodity_catalog(
            "", "un_comtrade", headers, settings=_settings(), client=mock.Mock()
        )


def test_record_commodity_catalog_rejects_overlapping_prefix(monkeypatch):
    pytest.importorskip("flask_caching")
    from embrapa_commodities.serving import curation

    monkeypatch.setattr(curation, "ensure_dataset", lambda *a, **k: None)
    client = mock.Mock()
    # the disjoint-read returns an existing ('9999','4403') in the banco
    client.query.return_value.result.return_value = [_catalog_row_obj("9999", "4403")]
    headers = {iap.IAP_EMAIL_HEADER: "accounts.google.com:alice@embrapa.br"}

    with pytest.raises(ValueError):  # new prefix '440' overlaps existing '4403'
        curation.record_commodity_catalog(
            "4403",
            "un_comtrade",
            headers,
            agrupamento="Madeira",  # required now (else the H-1 guard short-circuits first)
            code_prefix="440",
            settings=_settings(),
            client=client,
        )


def test_remove_commodity_catalog_appends_inactive_tombstone(monkeypatch):
    pytest.importorskip("flask_caching")
    from embrapa_commodities.serving import curation

    monkeypatch.setattr(curation, "ensure_dataset", lambda *a, **k: None)
    # The entry is currently active with a COARSE prefix (codigo 'madeira' != prefix '4403').
    # The tombstone must carry the REAL prefix, not the codigo — orphan detection keys off it.
    monkeypatch.setattr(curation, "_current_prefixes", lambda *a, **k: [("madeira", "4403")])
    client = mock.Mock()
    client.query.return_value.result.return_value = []
    headers = {iap.IAP_EMAIL_HEADER: "accounts.google.com:alice@embrapa.br"}

    rec = curation.remove_commodity_catalog(
        "madeira",
        "un_comtrade",
        headers,
        settings=_settings(),
        client=client,
        invalidate_cache=False,
    )
    assert rec["active"] is False
    assert rec["code_prefix"] == "4403"  # M-2: the real active prefix, not the codigo
    params = {p.name: p.value for p in client.query.call_args.kwargs["job_config"].query_parameters}
    assert params["active"] is False  # the tombstone row is active=false
    assert params["code_prefix"] == "4403"


def test_remove_commodity_catalog_rejects_uncataloged_key(monkeypatch):
    """Removing a key with no ACTIVE entry must raise (L-1) — a phantom tombstone would
    fabricate a false orphan, never silently appear."""
    pytest.importorskip("flask_caching")
    from embrapa_commodities.serving import curation

    monkeypatch.setattr(curation, "ensure_dataset", lambda *a, **k: None)
    monkeypatch.setattr(curation, "_current_prefixes", lambda *a, **k: [])  # nothing active
    headers = {iap.IAP_EMAIL_HEADER: "accounts.google.com:alice@embrapa.br"}
    with pytest.raises(ValueError):
        curation.remove_commodity_catalog(
            "9999",
            "un_comtrade",
            headers,
            settings=_settings(),
            client=mock.Mock(),
            invalidate_cache=False,
        )


def test_record_commodity_catalog_rejects_blank_agrupamento(monkeypatch):
    """A blank agrupamento → NULL commodity_id/commodity_name → the nightly prod dbt build
    not_null tests fail (H-1). Reject at the write gate (a fixable 400), not at build time."""
    pytest.importorskip("flask_caching")
    from embrapa_commodities.serving import curation

    monkeypatch.setattr(curation, "ensure_dataset", lambda *a, **k: None)
    headers = {iap.IAP_EMAIL_HEADER: "accounts.google.com:alice@embrapa.br"}
    with pytest.raises(ValueError):  # whitespace agrupamento → blank after strip
        curation.record_commodity_catalog(
            "4403",
            "un_comtrade",
            headers,
            agrupamento="   ",
            settings=_settings(),
            client=mock.Mock(),
        )
    with pytest.raises(ValueError):  # missing entirely
        curation.record_commodity_catalog(
            "4403", "un_comtrade", headers, settings=_settings(), client=mock.Mock()
        )


def test_record_commodity_catalog_rejects_blank_or_wildcard_prefix(monkeypatch):
    """A whitespace code_prefix collapses to '' → LIKE '%' (every code absorbed); a LIKE
    wildcard ('%'/'_') over-matches. Both rejected at the write gate (M-1)."""
    pytest.importorskip("flask_caching")
    from embrapa_commodities.serving import curation

    monkeypatch.setattr(curation, "ensure_dataset", lambda *a, **k: None)
    headers = {iap.IAP_EMAIL_HEADER: "accounts.google.com:alice@embrapa.br"}
    with pytest.raises(ValueError):  # whitespace → '' after strip
        curation.record_commodity_catalog(
            "4403",
            "un_comtrade",
            headers,
            agrupamento="Madeira",
            code_prefix="   ",
            settings=_settings(),
            client=mock.Mock(),
        )
    with pytest.raises(ValueError):  # '_' is a LIKE single-char wildcard
        curation.record_commodity_catalog(
            "4403",
            "un_comtrade",
            headers,
            agrupamento="Madeira",
            code_prefix="44_3",
            settings=_settings(),
            client=mock.Mock(),
        )


def test_ensure_commodity_catalog_log_table_creates_with_explicit_schema(monkeypatch):
    pytest.importorskip("flask_caching")
    from embrapa_commodities.serving import curation

    monkeypatch.setattr(curation, "ensure_dataset", lambda *a, **k: None)
    client = mock.Mock()
    fqn = curation.ensure_commodity_catalog_log_table(settings=_settings(), client=client)

    assert fqn.endswith(".commodity_catalog_log")
    table_arg = client.create_table.call_args.args[0]
    assert {f.name for f in table_arg.schema} >= {
        "codigo_commodity",
        "banco",
        "code_prefix",
        "active",
        "edited_by",
        "change_id",
    }
    assert table_arg.clustering_fields == ["banco", "codigo_commodity"]


# ── Curadoria lifecycle: orphan → Descontinuado (non-destructive) ─────────────


def _one_orphan_df():
    import pandas as pd

    return pd.DataFrame(
        [
            {
                "codigo_commodity": "20079926",
                "banco": "comex",
                "code_prefix": "20079926",
                "agrupamento": "Cupuaçu",
            }
        ]
    )


def test_ensure_catalog_lifecycle_log_table_schema(monkeypatch):
    pytest.importorskip("flask_caching")
    from embrapa_commodities.serving import catalog_lifecycle

    monkeypatch.setattr(catalog_lifecycle, "ensure_dataset", lambda *a, **k: None)
    client = mock.Mock()
    fqn = catalog_lifecycle.ensure_catalog_lifecycle_log_table(settings=_settings(), client=client)

    assert fqn.endswith(".catalog_lifecycle_log")
    table_arg = client.create_table.call_args.args[0]
    assert {f.name for f in table_arg.schema} >= {
        "element_kind",
        "banco",
        "code",
        "status",
        "scheduled_purge_note",
        "edited_by",
        "change_id",
    }
    assert table_arg.clustering_fields == ["element_kind", "banco"]


def test_auto_mark_orphans_marks_new_with_system_author(monkeypatch):
    """A detected orphan (removed + Gold lingering) is marked 'descontinuado' by the
    reserved system author, with the deletion warning — and NEVER deleted."""
    pytest.importorskip("flask_caching")
    from google.api_core.exceptions import NotFound

    from embrapa_commodities.serving import catalog_lifecycle, gateway

    monkeypatch.setattr(gateway, "fetch_orphan_commodities", _one_orphan_df)

    def _no_log():
        raise NotFound("no lifecycle log yet")

    monkeypatch.setattr(gateway, "fetch_lifecycle_status", _no_log)
    monkeypatch.setattr(
        catalog_lifecycle, "ensure_catalog_lifecycle_log_table", lambda *a, **k: "p.r.l"
    )
    monkeypatch.setattr(catalog_lifecycle, "_change_id_seen", lambda *a, **k: False)
    inserted = []
    monkeypatch.setattr(
        catalog_lifecycle,
        "_insert_lifecycle_event",
        lambda bq, table_fqn, **kw: inserted.append(kw),
    )
    monkeypatch.setattr(catalog_lifecycle, "invalidate_lifecycle_cache", lambda: None)

    res = catalog_lifecycle.auto_mark_orphans(settings=_settings(), client=mock.Mock())
    assert res == {"detected": 1, "newly_marked": 1, "already_marked": 0}
    ev = inserted[0]
    assert ev["status"] == "descontinuado"
    assert ev["edited_by"] == "system:orphan-detector"
    assert ev["banco"] == "comex" and ev["code"] == "20079926"
    assert ev["purge_note"]  # carries the deletion warning


def test_auto_mark_orphans_is_idempotent_when_already_marked(monkeypatch):
    """Re-running the marker is a no-op for an already-Descontinuado element (the
    deterministic change_id is already seen)."""
    pytest.importorskip("flask_caching")
    from google.api_core.exceptions import NotFound

    from embrapa_commodities.serving import catalog_lifecycle, gateway

    monkeypatch.setattr(gateway, "fetch_orphan_commodities", _one_orphan_df)

    def _no_log():
        raise NotFound("no lifecycle log yet")

    monkeypatch.setattr(gateway, "fetch_lifecycle_status", _no_log)
    monkeypatch.setattr(
        catalog_lifecycle, "ensure_catalog_lifecycle_log_table", lambda *a, **k: "p.r.l"
    )
    monkeypatch.setattr(
        catalog_lifecycle, "_change_id_seen", lambda *a, **k: True
    )  # already recorded
    monkeypatch.setattr(
        catalog_lifecycle,
        "_insert_lifecycle_event",
        lambda *a, **k: (_ for _ in ()).throw(
            AssertionError("must not insert when already marked")
        ),
    )

    res = catalog_lifecycle.auto_mark_orphans(settings=_settings(), client=mock.Mock())
    assert res == {"detected": 1, "newly_marked": 0, "already_marked": 1}


def test_auto_mark_orphans_remarks_a_fresh_reorphan(monkeypatch):
    """An entry re-added then re-removed AFTER a prior purge is re-detected AND re-marked
    (M-3): the new removal's removed_at is newer than the stale 'purged' flagged_at, so the
    generation-aware marker writes a FRESH 'descontinuado' (re-opening the purge gate).
    The inverse — a lifecycle event newer than the removal — is NOT re-marked."""
    pytest.importorskip("flask_caching")
    import pandas as pd

    from embrapa_commodities.serving import catalog_lifecycle, gateway

    removed_at = pd.Timestamp("2026-06-26T12:00:00Z")

    def _orphan_with_removed_at():
        return pd.DataFrame(
            [
                {
                    "codigo_commodity": "20079926",
                    "banco": "comex",
                    "code_prefix": "20079926",
                    "agrupamento": "Cupuaçu",
                    "removed_at": removed_at,
                }
            ]
        )

    def _status(status, flagged_at):
        return lambda: pd.DataFrame(
            [
                {
                    "element_kind": "commodity",
                    "banco": "comex",
                    "code": "20079926",
                    "status": status,
                    "reason": None,
                    "scheduled_purge_note": None,
                    "flagged_at": flagged_at,
                }
            ]
        )

    monkeypatch.setattr(gateway, "fetch_orphan_commodities", _orphan_with_removed_at)
    monkeypatch.setattr(
        catalog_lifecycle, "ensure_catalog_lifecycle_log_table", lambda *a, **k: "p.r.l"
    )
    monkeypatch.setattr(catalog_lifecycle, "_change_id_seen", lambda *a, **k: False)
    monkeypatch.setattr(catalog_lifecycle, "invalidate_lifecycle_cache", lambda: None)
    inserted = []
    monkeypatch.setattr(
        catalog_lifecycle, "_insert_lifecycle_event", lambda bq, t, **kw: inserted.append(kw)
    )

    # Prior 'purged' event OLDER than the new removal → re-mark.
    monkeypatch.setattr(
        gateway, "fetch_lifecycle_status", _status("purged", pd.Timestamp("2026-01-01T00:00:00Z"))
    )
    res = catalog_lifecycle.auto_mark_orphans(settings=_settings(), client=mock.Mock())
    assert res["newly_marked"] == 1 and inserted[0]["status"] == "descontinuado"

    # Lifecycle event NEWER than the removal (already covers it) → no re-mark.
    inserted.clear()
    monkeypatch.setattr(
        gateway,
        "fetch_lifecycle_status",
        _status("descontinuado", pd.Timestamp("2026-06-26T18:00:00Z")),
    )
    res2 = catalog_lifecycle.auto_mark_orphans(settings=_settings(), client=mock.Mock())
    assert res2["newly_marked"] == 0 and not inserted


def test_orphan_worklist_marks_descontinuado_with_warning(monkeypatch):
    """seam.orphan_worklist marks each detected orphan 'descontinuado' with the default
    deletion warning when nothing was recorded yet (flagged_at None)."""
    pytest.importorskip("flask_caching")
    from google.api_core.exceptions import NotFound

    from embrapa_commodities.serving import gateway
    from embrapa_commodities.webapi import seam_curation

    monkeypatch.setattr(gateway, "fetch_orphan_commodities", _one_orphan_df)

    def _no_log():
        raise NotFound("no lifecycle log yet")

    monkeypatch.setattr(gateway, "fetch_lifecycle_status", _no_log)
    out = seam_curation.orphan_worklist()
    assert out["total"] == 1
    o = out["orphans"][0]
    assert o["status"] == "descontinuado" and o["codigo_commodity"] == "20079926"
    assert o["flagged_at"] is None and o["warning"]  # default warning before the marker runs


def test_orphan_worklist_reports_recorded_status(monkeypatch):
    """orphan_worklist surfaces the RECORDED lifecycle status — 'purged' for a re-orphaned,
    already-purged code — not a hardcoded 'descontinuado' (L-4); and falls back to the
    standing warning when a purged event carries no purge note."""
    pytest.importorskip("flask_caching")
    import pandas as pd

    from embrapa_commodities.serving import gateway
    from embrapa_commodities.webapi import seam_curation

    monkeypatch.setattr(gateway, "fetch_orphan_commodities", _one_orphan_df)

    def _status_purged():
        return pd.DataFrame(
            [
                {
                    "element_kind": "commodity",
                    "banco": "comex",
                    "code": "20079926",
                    "status": "purged",
                    "reason": None,
                    "scheduled_purge_note": None,
                    "flagged_at": pd.Timestamp("2026-06-26T12:00:00Z"),
                }
            ]
        )

    monkeypatch.setattr(gateway, "fetch_lifecycle_status", _status_purged)
    o = seam_curation.orphan_worklist()["orphans"][0]
    assert o["status"] == "purged"
    assert o["warning"]  # purged events carry no note → standing warning


def test_purge_plan_requires_descontinuado_and_builds_scoped_deletes(monkeypatch):
    """The purge plan REFUSES an element that is not marked Descontinuado, and for one
    that is, builds the scoped Gold DELETE(s) + the backup status — without deleting."""
    pytest.importorskip("flask_caching")
    from embrapa_commodities.serving import catalog_lifecycle

    # not marked → refuse
    monkeypatch.setattr(catalog_lifecycle, "_current_status", lambda cfg: {})
    with pytest.raises(ValueError):
        catalog_lifecycle.purge_plan("comex", "20079926", settings=_settings())

    # marked descontinuado → plan with the scoped Gold DELETE + backup status
    monkeypatch.setattr(
        catalog_lifecycle,
        "_current_status",
        lambda cfg: {("commodity", "comex", "20079926"): "descontinuado"},
    )
    monkeypatch.setattr(catalog_lifecycle, "_backup_status", lambda cfg: (True, "snapshot ok"))
    plan = catalog_lifecycle.purge_plan("comex", "20079926", settings=_settings())
    assert plan["backup_ok"] is True
    assert any("gold_comex_flows" in s and "20079926%" in s for s in plan["statements"])
    assert all(s.strip().startswith("DELETE FROM") for s in plan["statements"])


def test_purge_plan_rejects_injection_in_code():
    """A non-alphanumeric code (SQL-injection attempt) is rejected — the plan is printed
    verbatim for a human to run, so the code must be a simple token."""
    from embrapa_commodities.serving import catalog_lifecycle

    with pytest.raises(ValueError):
        catalog_lifecycle.purge_plan("comex", "1' ; DROP TABLE x; --", settings=_settings())


def test_mark_purged_appends_terminal_event_idempotently(monkeypatch):
    """mark_purged records a terminal 'purged' audit event (who/when); idempotent."""
    pytest.importorskip("flask_caching")
    from embrapa_commodities.serving import catalog_lifecycle

    monkeypatch.setattr(
        catalog_lifecycle, "ensure_catalog_lifecycle_log_table", lambda *a, **k: "p.r.l"
    )
    monkeypatch.setattr(catalog_lifecycle, "invalidate_lifecycle_cache", lambda: None)
    inserted = []
    monkeypatch.setattr(
        catalog_lifecycle, "_insert_lifecycle_event", lambda bq, t, **kw: inserted.append(kw)
    )
    monkeypatch.setattr(catalog_lifecycle, "_change_id_seen", lambda *a, **k: False)
    monkeypatch.setattr(catalog_lifecycle, "_current_lifecycle", lambda *a, **k: {})
    res = catalog_lifecycle.mark_purged(
        "comex", "20079926", edited_by="op", settings=_settings(), client=mock.Mock()
    )
    assert res["status"] == "purged" and res["deduped"] is False
    assert inserted[0]["status"] == "purged" and inserted[0]["edited_by"] == "op"

    monkeypatch.setattr(catalog_lifecycle, "_change_id_seen", lambda *a, **k: True)
    res2 = catalog_lifecycle.mark_purged(
        "comex", "20079926", edited_by="op", settings=_settings(), client=mock.Mock()
    )
    assert res2["deduped"] is True


def test_mark_purged_records_a_fresh_event_per_descontinuado_generation(monkeypatch):
    """A code re-added, re-removed (a NEW descontinuado generation) and re-purged records its OWN
    terminal 'purged' event — not collapsed onto the first purge's audit row (the per-generation
    idempotency fix). An already-purged element with no fresh removal is a no-op."""
    pytest.importorskip("flask_caching")
    from datetime import datetime

    from embrapa_commodities.serving import catalog_lifecycle

    monkeypatch.setattr(
        catalog_lifecycle, "ensure_catalog_lifecycle_log_table", lambda *a, **k: "p.r.l"
    )
    monkeypatch.setattr(catalog_lifecycle, "invalidate_lifecycle_cache", lambda: None)
    seen = set()
    inserted = []

    def _ins(bq, t, **kw):
        inserted.append(kw)
        seen.add(kw["change_id"])

    monkeypatch.setattr(catalog_lifecycle, "_insert_lifecycle_event", _ins)
    monkeypatch.setattr(catalog_lifecycle, "_change_id_seen", lambda bq, t, cid: cid in seen)
    gen1 = datetime(2026, 1, 1, tzinfo=UTC)
    gen2 = datetime(2026, 6, 1, tzinfo=UTC)

    def _purge():
        return catalog_lifecycle.mark_purged(
            "comex", "0801", edited_by="op", settings=_settings(), client=mock.Mock()
        )

    def _state(status, at):
        monkeypatch.setattr(
            catalog_lifecycle,
            "_current_lifecycle",
            lambda *a, **k: {("commodity", "comex", "0801"): (status, at)},
        )

    _state("descontinuado", gen1)  # generation 1 → records the purge
    assert _purge()["deduped"] is False
    _state("purged", gen1)  # already purged, no re-removal → no-op
    assert _purge()["deduped"] is True
    _state("descontinuado", gen2)  # re-removed → NEW generation → a fresh event
    assert _purge()["deduped"] is False

    assert len(inserted) == 2  # one terminal event per generation, not collapsed
    assert inserted[0]["change_id"] != inserted[1]["change_id"]


def test_raw_table_rows_casts_string_typed_columns_for_comparison():
    # A DATE/TIMESTAMP column binds as STRING and must compare against CAST(col AS STRING),
    # else BigQuery raises a type mismatch (TIMESTAMP = STRING param) → an opaque 500. A
    # plain STRING column is CAST too (a no-op) so there's one uniform path; numeric/bool
    # columns compare DIRECT (no cast) to keep their native ordering.
    cols = {
        "reference_date": "DATE",
        "last_refresh": "TIMESTAMP",
        "product_code": "STRING",
        "reference_year": "INTEGER",
    }
    query, params = sql.raw_table_rows(
        "p.d.t",
        columns_types=cols,
        limit=10,
        filters=[
            {"col": "reference_date", "op": "ge", "val": "2000-01-01"},
            {"col": "last_refresh", "op": "lt", "val": "2025-01-01"},
            {"col": "product_code", "op": "eq", "val": "2670"},
            {"col": "reference_year", "op": "eq", "val": "1999"},
        ],
    )
    assert "cast(`reference_date` as string) >= @f0" in query
    assert "cast(`last_refresh` as string) < @f1" in query
    assert "cast(`product_code` as string) = @f2" in query
    assert "`reference_year` = @f3" in query  # numeric column compares direct, no cast
    by_name = {p.name: p for p in params}
    assert by_name["f0"].type_ == "STRING" and by_name["f1"].type_ == "STRING"
    assert by_name["f3"].type_ == "INT64" and by_name["f3"].value == 1999


def test_raw_table_rows_rejects_missing_and_nonfinite_filter_values():
    # Every malformed value-requiring filter must raise ValueError (→ HTTP 400), never an
    # uncaught TypeError/non-finite bind that BigQuery turns into an opaque 500.
    cols = {"reference_year": "INTEGER", "val_yearfx_brl": "FLOAT"}
    with pytest.raises(ValueError):  # missing 'val' on a value-requiring op (KeyError → 500)
        sql.raw_table_rows(
            "p.d.t",
            columns_types=cols,
            limit=10,
            filters=[{"col": "reference_year", "op": "eq"}],
        )
    with pytest.raises(ValueError):  # explicit null → int(None) TypeError → 500
        sql.raw_table_rows(
            "p.d.t",
            columns_types=cols,
            limit=10,
            filters=[{"col": "reference_year", "op": "eq", "val": None}],
        )
    for bad in ("inf", "nan", "-inf"):  # non-finite float bind → BigQuery 500
        with pytest.raises(ValueError):
            sql.raw_table_rows(
                "p.d.t",
                columns_types=cols,
                limit=10,
                filters=[{"col": "val_yearfx_brl", "op": "gt", "val": bad}],
            )
