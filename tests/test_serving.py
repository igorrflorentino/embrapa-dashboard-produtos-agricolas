"""Tests for the dashboard data-access layer (src/embrapa_commodities/serving).

The pure modules (iap, sql) are tested directly. The cache/gateway/curation
tests guard on the optional ``flask-caching`` extra and mock BigQuery — they
never touch a live warehouse.
"""

from __future__ import annotations

from unittest import mock

import pytest

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
