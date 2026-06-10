"""Tests for the dashboard data-access layer (src/embrapa_commodities/serving).

The pure modules (iap, sql) are tested directly. The cache/gateway/curation
tests guard on the optional ``flask-caching`` extra and mock BigQuery — they
never touch a live warehouse.
"""

from __future__ import annotations

from unittest import mock

import pytest
from google.cloud import bigquery

from embrapa_commodities.config import Settings
from embrapa_commodities.serving import iap, sql

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
        return {"email": "verified@embrapa.br", "sub": "123"}

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
    monkeypatch.setattr("google.oauth2.id_token.verify_token", lambda *a, **k: {"sub": "123"})
    headers = {iap.IAP_JWT_HEADER: "valid.but.no.email"}
    with pytest.raises(iap.InvalidIapAssertionError):
        iap.verify_iap_jwt(headers, audience="aud")


def test_author_email_prefers_verified_jwt_when_audience_set(monkeypatch):
    """With audience set, the spoofable plaintext header is ignored; JWT wins."""
    monkeypatch.setattr(
        "google.oauth2.id_token.verify_token",
        lambda *a, **k: {"email": "real@embrapa.br"},
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


def test_current_classifications_filters_is_current():
    query, params = sql.current_classifications("p.serving.dim_commodity_scd2")
    assert "where is_current" in query.lower()
    assert params == []


def test_current_code_industrialization_filters_is_current():
    query, params = sql.current_code_industrialization("p.serving.dim_code_industrialization_scd2")
    assert "where is_current" in query.lower()
    assert "industrialization_level" in query.lower()
    assert "source" in query.lower()
    assert params == []


def test_table_ref_builds_fqn():
    settings = Settings(gcp_project_id="my-proj", bq_serving_dataset="serving")
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
    assert "flow = @flow" in query
    assert "ncm_code in unnest(@ncm_codes)" in query.lower()
    by_name = {p.name: p for p in params}
    assert by_name["flow"].value == "export"
    assert by_name["ncm_codes"].values == ["08012100"]


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
    assert params == []


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
    assert "any_value(family)" in query
    assert "product_code in unnest(@codes)" in query.lower()
    by_name = {p.name: p for p in params}
    assert by_name["codes"].values == ["3405"]
    assert by_name["year_start"].value == 2000


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
    return Settings(gcp_project_id="test-project")


def test_record_processing_stage_inserts_parameterized_row_with_author():
    pytest.importorskip("flask_caching")
    from embrapa_commodities.serving import curation

    settings = _settings()
    client = mock.Mock()
    client.query.return_value.result.return_value = None
    headers = {iap.IAP_EMAIL_HEADER: "accounts.google.com:alice@embrapa.br"}

    record = curation.record_processing_stage(
        "castanha_do_para",
        "beneficiado",
        headers,
        note="reviewed 2026",
        settings=settings,
        client=client,
        invalidate_cache=False,
    )

    assert record["edited_by"] == "alice@embrapa.br"
    assert record["commodity_id"] == "castanha_do_para"
    sql_text = client.query.call_args.args[0].lower()
    assert "insert into" in sql_text
    assert "current_timestamp()" in sql_text  # server-side stamp, not client clock
    params = {p.name: p.value for p in client.query.call_args.kwargs["job_config"].query_parameters}
    assert params["commodity_id"] == "castanha_do_para"
    assert params["processing_stage"] == "beneficiado"
    assert params["edited_by"] == "alice@embrapa.br"
    assert params["note"] == "reviewed 2026"


def test_record_processing_stage_rejects_empty_inputs():
    pytest.importorskip("flask_caching")
    from embrapa_commodities.serving import curation

    headers = {iap.IAP_EMAIL_HEADER: "accounts.google.com:alice@embrapa.br"}
    with pytest.raises(ValueError):
        curation.record_processing_stage(
            "", "beneficiado", headers, settings=_settings(), client=mock.Mock()
        )


def test_ensure_curation_log_table_creates_with_explicit_schema(monkeypatch):
    pytest.importorskip("flask_caching")
    from embrapa_commodities.serving import curation

    monkeypatch.setattr(curation, "ensure_dataset", lambda *a, **k: None)
    client = mock.Mock()
    fqn = curation.ensure_curation_log_table(settings=_settings(), client=client)

    assert fqn.endswith(".commodity_processing_stage_log")
    table_arg = client.create_table.call_args.args[0]
    assert {f.name for f in table_arg.schema} == {
        "commodity_id",
        "processing_stage",
        "note",
        "edited_by",
        "edited_at",
        "change_id",
    }
    assert client.create_table.call_args.kwargs["exists_ok"] is True


def test_record_code_industrialization_inserts_parameterized_row_with_author():
    pytest.importorskip("flask_caching")
    from embrapa_commodities.serving import curation

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
    from embrapa_commodities.serving import curation

    headers = {iap.IAP_EMAIL_HEADER: "accounts.google.com:alice@embrapa.br"}
    with pytest.raises(ValueError):
        curation.record_code_industrialization(
            "mdic_comex", "", "processada", headers, settings=_settings(), client=mock.Mock()
        )


def test_ensure_code_industrialization_log_table_creates_with_explicit_schema(monkeypatch):
    pytest.importorskip("flask_caching")
    from embrapa_commodities.serving import curation

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
        return [("castanha_do_para", "beneficiado")]

    monkeypatch.setattr(gateway, "run_query", fake_run)
    monkeypatch.setattr(gateway, "get_settings", lambda: Settings(gcp_project_id="p"))

    with app.app_context():
        cache.clear()
        gateway.fetch_current_classifications()
        gateway.fetch_current_classifications()  # served from cache

    assert calls["n"] == 1


def test_classification_cache_uses_short_ttl_for_multiinstance():
    """The curation read uses a SHORT TTL, not the long mart default.

    That short window (not a shared Redis) is what bounds cross-instance
    staleness, letting the dashboard scale to N Cloud Run instances for free.
    """
    pytest.importorskip("flask_caching")
    from embrapa_commodities.serving import gateway

    mart_ttl = Settings(gcp_project_id="p").cache_default_timeout
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

    settings = Settings(gcp_project_id="p", cache_classification_timeout=17)
    app = Flask(__name__)
    init_cache(app, settings)

    effective = gateway.fetch_current_classifications.cache_timeout
    assert effective == 17
    assert effective == settings.cache_classification_timeout


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

    def recorder(query, params):
        recorded["query"] = query
        recorded["params"] = {p.name: p for p in params}
        return "df"

    monkeypatch.setattr(gateway, "run_query", recorder)
    monkeypatch.setattr(gateway, "get_settings", lambda: Settings(gcp_project_id="p"))
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


def test_fetch_production_by_uf_queries_correct_table_and_params(monkeypatch):
    pytest.importorskip("flask_caching")
    from embrapa_commodities.serving import gateway

    recorded = {}

    def recorder(query, params):
        recorded["query"] = query
        recorded["params"] = {p.name: p for p in params}
        return "df"

    monkeypatch.setattr(gateway, "run_query", recorder)
    monkeypatch.setattr(gateway, "get_settings", lambda: Settings(gcp_project_id="p"))
    app, cache = _bind_simplecache()

    with app.app_context():
        cache.clear()
        gateway.fetch_production_by_uf(year_start=2015, value_column="val_yearfx_usd")

    assert "p.serving.serving_pevs_annual" in recorded["query"]
    assert "group by state_acronym" in recorded["query"]
    assert "sum(val_yearfx_usd)" in recorded["query"]
    assert recorded["params"]["year_start"].value == 2015


def test_fetch_comex_seasonality_queries_correct_table_and_params(monkeypatch):
    pytest.importorskip("flask_caching")
    from embrapa_commodities.serving import gateway

    recorded = {}

    def recorder(query, params):
        recorded["query"] = query
        recorded["params"] = {p.name: p for p in params}
        return "df"

    monkeypatch.setattr(gateway, "run_query", recorder)
    monkeypatch.setattr(gateway, "get_settings", lambda: Settings(gcp_project_id="p"))
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

    def recorder(query, params):
        recorded["query"] = query
        recorded["params"] = {p.name: p for p in params}
        return "df"

    monkeypatch.setattr(gateway, "run_query", recorder)
    monkeypatch.setattr(gateway, "get_settings", lambda: Settings(gcp_project_id="p"))
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

    def recorder(query, params):
        recorded["query"] = query
        recorded["params"] = {p.name: p for p in params}
        return "df"

    monkeypatch.setattr(gateway, "run_query", recorder)
    monkeypatch.setattr(gateway, "get_settings", lambda: Settings(gcp_project_id="p"))
    app, cache = _bind_simplecache()

    with app.app_context():
        cache.clear()
        gateway.fetch_comtrade_partners(year_start=2022, cmd_codes=("440710",))

    assert "p.serving.serving_comtrade_annual" in recorded["query"]
    assert "group by partner_code" in recorded["query"]
    assert "case when flow = 'export'" in recorded["query"]
    assert recorded["params"]["codes"].values == ["440710"]


def test_fetch_quality_by_source_queries_quality_mart(monkeypatch):
    pytest.importorskip("flask_caching")
    from embrapa_commodities.serving import gateway

    recorded = {}

    def recorder(query, params):
        recorded["query"] = query
        recorded["params"] = {p.name: p for p in params}
        return "df"

    monkeypatch.setattr(gateway, "run_query", recorder)
    monkeypatch.setattr(gateway, "get_settings", lambda: Settings(gcp_project_id="p"))
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

    def recorder(query, params):
        recorded["query"] = query
        return "df"

    monkeypatch.setattr(gateway, "run_query", recorder)
    monkeypatch.setattr(gateway, "get_settings", lambda: Settings(gcp_project_id="p"))
    app, cache = _bind_simplecache()

    with app.app_context():
        cache.clear()
        gateway.fetch_products("un_comtrade")

    assert "p.serving.serving_comtrade_annual" in recorded["query"]
    assert "group by cmd_code" in recorded["query"]


def test_fetch_product_timeseries_uses_source_default_value_column(monkeypatch):
    pytest.importorskip("flask_caching")
    from embrapa_commodities.serving import gateway

    recorded = {}

    def recorder(query, params):
        recorded["query"] = query
        recorded["params"] = {p.name: p for p in params}
        return "df"

    monkeypatch.setattr(gateway, "run_query", recorder)
    monkeypatch.setattr(gateway, "get_settings", lambda: Settings(gcp_project_id="p"))
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

    def recorder(query, params):
        recorded["query"] = query
        recorded["params"] = {p.name: p for p in params}
        return "df"

    monkeypatch.setattr(gateway, "run_query", recorder)
    monkeypatch.setattr(gateway, "get_settings", lambda: Settings(gcp_project_id="p"))
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
    monkeypatch.setattr(gateway, "get_settings", lambda: Settings(gcp_project_id="p"))
    app, cache = _bind_simplecache()

    with app.app_context():
        cache.clear()
        with pytest.raises(ValueError, match="unknown source"):
            gateway.fetch_products("nope")


def test_fetch_cross_series_brazil_metric_filters_reporter(monkeypatch):
    pytest.importorskip("flask_caching")
    from embrapa_commodities.serving import gateway

    recorded = {}

    def recorder(query, params):
        recorded["query"] = query
        recorded["params"] = {p.name: p for p in params}
        return "df"

    monkeypatch.setattr(gateway, "run_query", recorder)
    monkeypatch.setattr(gateway, "get_settings", lambda: Settings(gcp_project_id="p"))
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

    def recorder(query, params):
        recorded["query"] = query
        recorded["params"] = {p.name: p for p in params}
        return "df"

    monkeypatch.setattr(gateway, "run_query", recorder)
    monkeypatch.setattr(gateway, "get_settings", lambda: Settings(gcp_project_id="p"))
    app, cache = _bind_simplecache()

    with app.app_context():
        cache.clear()
        gateway.fetch_cross_series("un_comtrade:world_exp", year_start=2022)

    assert "@reporter" not in recorded["query"]  # world total — no Brazil filter


def test_fetch_cross_series_unknown_metric_raises(monkeypatch):
    pytest.importorskip("flask_caching")
    from embrapa_commodities.serving import gateway

    monkeypatch.setattr(gateway, "run_query", lambda *a, **k: pytest.fail("must reject"))
    monkeypatch.setattr(gateway, "get_settings", lambda: Settings(gcp_project_id="p"))
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
    monkeypatch.setattr(gateway, "get_settings", lambda: Settings(gcp_project_id="p"))
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

    params = [bigquery.ScalarQueryParameter("year_start", "INT64", 2000)]
    result = gateway.run_query("select 1", params)

    assert result == "DF"
    sent_sql = fake_client.query.call_args.args[0]
    assert sent_sql == "select 1"
    job_config = fake_client.query.call_args.kwargs["job_config"]
    assert job_config.query_parameters == params
    # BQ Storage client disabled (avoids an extra dependency/permission at read).
    to_df = fake_client.query.return_value.result.return_value.to_dataframe
    assert to_df.call_args.kwargs["create_bqstorage_client"] is False


# ── cache.init_cache: backend selection ───────────────────────────────────────


def test_init_cache_selects_simplecache_by_default():
    pytest.importorskip("flask_caching")
    from flask import Flask

    from embrapa_commodities.serving.cache import init_cache

    app = Flask(__name__)
    init_cache(app, Settings(gcp_project_id="p"))
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

    settings = Settings(
        gcp_project_id="p",
        cache_type="RedisCache",
        cache_redis_url="redis://cache:6379/0",
    )
    cache_mod.init_cache(Flask(__name__), settings)

    assert captured["CACHE_TYPE"] == "RedisCache"
    assert captured["CACHE_REDIS_URL"] == "redis://cache:6379/0"


# ── curation: cache invalidation on save (the "scales without Redis" pillar) ──


def test_save_invalidates_classification_cache(monkeypatch):
    """record_processing_stage(invalidate_cache=True) must force the next read to re-query.

    This is the core of "scales to N Cloud Run instances without Redis": the
    writing instance drops its cached classification so the edit is immediately
    visible locally (other instances converge within the short TTL).
    """
    pytest.importorskip("flask_caching")
    from embrapa_commodities.serving import curation, gateway

    app, cache = _bind_simplecache()

    calls = {"n": 0}

    def fake_run(query, params):
        calls["n"] += 1
        return [("castanha_do_para", "beneficiado")]

    monkeypatch.setattr(gateway, "run_query", fake_run)
    monkeypatch.setattr(gateway, "get_settings", lambda: Settings(gcp_project_id="p"))

    bq_client = mock.Mock()
    bq_client.query.return_value.result.return_value = None
    headers = {iap.IAP_EMAIL_HEADER: "accounts.google.com:alice@embrapa.br"}

    with app.app_context():
        cache.clear()
        gateway.fetch_current_classifications()  # warms cache → 1 query
        gateway.fetch_current_classifications()  # cached → still 1
        assert calls["n"] == 1

        curation.record_processing_stage(
            "castanha_do_para",
            "beneficiado",
            headers,
            settings=Settings(gcp_project_id="p"),
            client=bq_client,
            invalidate_cache=True,
        )

        gateway.fetch_current_classifications()  # cache dropped → re-queries
        assert calls["n"] == 2


def test_invalidate_classification_cache_is_safe_when_unbound(monkeypatch):
    """With no Flask app bound, invalidation is a no-op (covers the except branch)."""
    pytest.importorskip("flask_caching")
    from embrapa_commodities.serving import curation
    from embrapa_commodities.serving.cache import Cache, cache

    # Reset to a pristine, unbound cache so delete_memoized raises internally and
    # the best-effort guard swallows it without propagating.
    monkeypatch.setattr(curation, "cache", Cache())
    try:
        curation.invalidate_classification_cache()  # must not raise
    finally:
        # Leave the module-level singleton as the test found it.
        assert cache is not None


# ── curation: free-text size guards (open vocabulary, bounded length) ─────────


def test_record_processing_stage_rejects_overlong_stage():
    pytest.importorskip("flask_caching")
    from embrapa_commodities.serving import curation

    headers = {iap.IAP_EMAIL_HEADER: "accounts.google.com:alice@embrapa.br"}
    with pytest.raises(ValueError, match="processing_stage exceeds"):
        curation.record_processing_stage(
            "castanha_do_para",
            "x" * (curation.MAX_STAGE_LEN + 1),
            headers,
            settings=_settings(),
            client=mock.Mock(),
        )


def test_record_processing_stage_rejects_overlong_note():
    pytest.importorskip("flask_caching")
    from embrapa_commodities.serving import curation

    headers = {iap.IAP_EMAIL_HEADER: "accounts.google.com:alice@embrapa.br"}
    with pytest.raises(ValueError, match="note exceeds"):
        curation.record_processing_stage(
            "castanha_do_para",
            "beneficiado",
            headers,
            note="n" * (curation.MAX_NOTE_LEN + 1),
            settings=_settings(),
            client=mock.Mock(),
        )


def test_record_processing_stage_accepts_free_text_stage():
    """A novel, non-allowlisted stage label is accepted (open vocabulary by design)."""
    pytest.importorskip("flask_caching")
    from embrapa_commodities.serving import curation

    client = mock.Mock()
    client.query.return_value.result.return_value = None
    headers = {iap.IAP_EMAIL_HEADER: "accounts.google.com:alice@embrapa.br"}

    record = curation.record_processing_stage(
        "castanha_do_para",
        "estágio-experimental-inédito",  # not in any allowlist — must be allowed
        headers,
        settings=_settings(),
        client=client,
        invalidate_cache=False,
    )
    assert record["processing_stage"] == "estágio-experimental-inédito"


# ── market-nature: customsCode × flowCode value + curated-purpose log ──────────


def test_comtrade_cpc_value_excludes_c00_aggregate_and_casts():
    query, params = sql.comtrade_cpc_value("p.bronze_comtrade.comtrade_flows_raw")
    low = query.lower()
    assert "customscode != 'c00'" in low  # the aggregate is excluded (no double-count)
    assert "safe_cast(primaryvalue as float64)" in low  # Bronze is all-STRING
    assert "safe_cast(refyear as int64)" in low
    assert "group by customs_code, flow_code, reference_year" in low
    assert params == []  # no commodity filter → no params


def test_comtrade_cpc_value_filters_cmd_codes_when_scoped():
    query, params = sql.comtrade_cpc_value("t", codes=("0801", "44"))
    assert "cmdcode in unnest(@cmd_codes)" in query.lower()
    assert params[0].name == "cmd_codes" and list(params[0].values) == ["0801", "44"]


def test_current_flow_market_latest_wins_and_drops_cleared():
    query, params = sql.current_flow_market("p.research_inputs.flow_market_log")
    low = query.lower()
    assert "row_number() over" in low
    assert "partition by customs_code, flow_code order by edited_at desc" in low
    assert "where rn = 1 and market != ''" in low  # a cleared (empty) market is dropped
    assert params == []


def test_record_flow_market_inserts_parameterized_row_with_author(monkeypatch):
    pytest.importorskip("flask_caching")
    from embrapa_commodities.serving import curation

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
    from embrapa_commodities.serving import curation

    headers = {iap.IAP_EMAIL_HEADER: "accounts.google.com:alice@embrapa.br"}
    with pytest.raises(ValueError):
        curation.record_flow_market(
            "", "M", "consumo", headers, settings=_settings(), client=mock.Mock()
        )


def test_record_flow_market_allows_empty_market_to_clear(monkeypatch):
    pytest.importorskip("flask_caching")
    from embrapa_commodities.serving import curation

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
    from embrapa_commodities.serving import curation

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
