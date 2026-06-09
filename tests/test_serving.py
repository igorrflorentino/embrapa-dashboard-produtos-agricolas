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
