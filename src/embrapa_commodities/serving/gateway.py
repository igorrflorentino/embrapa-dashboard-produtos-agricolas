"""Cached, parameterized reads against the BigQuery serving marts.

Each public ``fetch_*`` function is the read half of one chart family: it builds
a parameterized query (``serving.sql``), runs it on BigQuery, and returns a small
Pandas DataFrame. The functions are decorated with ``@cache.memoize()`` so a
repeated (filters) combination is answered from cache instead of re-querying
BigQuery — the round-trip the stateless dashboard would otherwise pay on every
identical callback.

Caching policy (designed so the dashboard scales to N Cloud Run instances
WITHOUT a shared Redis — see ``serving.cache``):
  * Mart reads (``fetch_production_*``, ``fetch_comex_seasonality``) use the
    default TTL — the marts change solely on the nightly dbt rebuild, so every
    instance independently converges to the same data within the TTL.
  * ``fetch_current_classifications`` uses a SHORT TTL
    (``CACHE_CLASSIFICATION_TIMEOUT``, default 30s) AND is explicitly invalidated
    by the curation writer. The invalidation makes a curation edit instant on the
    writing instance; the short TTL bounds cross-instance staleness to that window
    (eventual consistency) — which is what lets multiple instances run on
    per-process SimpleCache for free.

There is no global lock and no in-memory Gold DataFrame: state lives in BigQuery,
results are cached, and the process stays stateless and horizontally scalable.
"""

from __future__ import annotations

import functools
from collections.abc import Sequence

from google.cloud import bigquery

from embrapa_commodities.config import get_credentials, get_settings
from embrapa_commodities.serving import sql as sqlbuild
from embrapa_commodities.serving.cache import cache

# Fallback short TTL for the curation-classification read, used only until
# init_cache() binds the authoritative value from config.Settings. On
# multi-instance Cloud Run, per-process SimpleCache can't be invalidated across
# instances, so this TTL (not Redis) bounds cross-instance staleness.
#
# @cache.memoize fixes a *default* timeout at decoration time (before Settings
# exists), but flask-caching exposes a writable ``cache_timeout`` attribute on the
# decorated function that it re-reads on every call. init_cache() — which has
# Settings — sets that attribute to cfg.cache_classification_timeout, making the
# config field authoritative (no os.environ drift). See cache.init_cache and
# config.Settings.cache_classification_timeout.
DEFAULT_CLASSIFICATION_TTL = 30


@functools.lru_cache(maxsize=1)
def _client() -> bigquery.Client:
    """Lazily build one BigQuery client per process (reused across queries)."""
    settings = get_settings()
    return bigquery.Client(
        project=settings.gcp_project_id,
        location=settings.bq_location,
        credentials=get_credentials(settings),
    )


def run_query(sql: str, params: list) -> object:
    """Execute a parameterized query and return the result as a DataFrame."""
    job = _client().query(
        sql,
        job_config=bigquery.QueryJobConfig(query_parameters=params),
    )
    return job.result().to_dataframe(create_bqstorage_client=False)


# (mart, product-code column, product-name column, default value column) per
# source. Drives the uniform products / productTS readers — one entry point each
# instead of three near-identical functions, since the three annual marts now
# share the same product/quantity columns.
_PRODUCT_SOURCES = {
    "ibge_pevs": (
        "serving_pevs_annual",
        "product_code",
        "product_description",
        "val_real_ipca_brl",
    ),
    "mdic_comex": ("serving_comex_annual", "ncm_code", "ncm_description", "val_yearfx_usd"),
    "un_comtrade": ("serving_comtrade_annual", "cmd_code", "cmd_description", "val_yearfx_usd"),
}


def _product_source(source: str) -> tuple[str, str, str, str]:
    try:
        return _PRODUCT_SOURCES[source]
    except KeyError:
        raise ValueError(
            f"unknown source {source!r}; choose one of {sorted(_PRODUCT_SOURCES)}"
        ) from None


@cache.memoize()
def fetch_production_overview(
    year_start: int | None = None,
    year_end: int | None = None,
    product_codes: Sequence[str] = (),
    value_column: str = "val_real_ipca_brl",
):
    """Annual PEVS production total (backs overviewTS)."""
    settings = get_settings()
    table = sqlbuild.table_ref(settings, "bq_serving_dataset", "serving_pevs_annual")
    sql, params = sqlbuild.production_overview(
        table,
        year_start=year_start,
        year_end=year_end,
        product_codes=tuple(product_codes),
        value_column=value_column,
    )
    return run_query(sql, params)


@cache.memoize()
def fetch_production_by_uf(
    year_start: int | None = None,
    year_end: int | None = None,
    product_codes: Sequence[str] = (),
    value_column: str = "val_real_ipca_brl",
):
    """PEVS production aggregated by UF (backs ufData)."""
    settings = get_settings()
    table = sqlbuild.table_ref(settings, "bq_serving_dataset", "serving_pevs_annual")
    sql, params = sqlbuild.production_by_uf(
        table,
        year_start=year_start,
        year_end=year_end,
        product_codes=tuple(product_codes),
        value_column=value_column,
    )
    return run_query(sql, params)


@cache.memoize()
def fetch_comex_seasonality(
    year_start: int | None = None,
    year_end: int | None = None,
    ncm_codes: Sequence[str] = (),
    flow: str | None = None,
):
    """Monthly COMEX value for the seasonality view (backs monthlyData)."""
    settings = get_settings()
    table = sqlbuild.table_ref(settings, "bq_serving_dataset", "serving_comex_seasonality")
    sql, params = sqlbuild.comex_seasonality(
        table,
        year_start=year_start,
        year_end=year_end,
        ncm_codes=tuple(ncm_codes),
        flow=flow,
    )
    return run_query(sql, params)


@cache.memoize()
def fetch_comex_overview(
    year_start: int | None = None,
    year_end: int | None = None,
    ncm_codes: Sequence[str] = (),
    flow: str | None = None,
):
    """Annual COMEX value + weight (backs overviewTS for COMEX)."""
    settings = get_settings()
    table = sqlbuild.table_ref(settings, "bq_serving_dataset", "serving_comex_annual")
    sql, params = sqlbuild.trade_overview(
        table,
        code_column="ncm_code",
        year_start=year_start,
        year_end=year_end,
        codes=tuple(ncm_codes),
        flow=flow,
    )
    return run_query(sql, params)


@cache.memoize()
def fetch_comtrade_overview(
    year_start: int | None = None,
    year_end: int | None = None,
    cmd_codes: Sequence[str] = (),
    flow: str | None = None,
):
    """Annual COMTRADE value + weight (backs overviewTS for COMTRADE)."""
    settings = get_settings()
    table = sqlbuild.table_ref(settings, "bq_serving_dataset", "serving_comtrade_annual")
    sql, params = sqlbuild.trade_overview(
        table,
        code_column="cmd_code",
        year_start=year_start,
        year_end=year_end,
        codes=tuple(cmd_codes),
        flow=flow,
    )
    return run_query(sql, params)


@cache.memoize()
def fetch_comex_by_uf(
    year_start: int | None = None,
    year_end: int | None = None,
    ncm_codes: Sequence[str] = (),
    flow: str | None = None,
):
    """COMEX value + weight aggregated by UF (backs ufData for COMEX)."""
    settings = get_settings()
    table = sqlbuild.table_ref(settings, "bq_serving_dataset", "serving_comex_annual")
    sql, params = sqlbuild.comex_by_uf(
        table,
        year_start=year_start,
        year_end=year_end,
        ncm_codes=tuple(ncm_codes),
        flow=flow,
    )
    return run_query(sql, params)


@cache.memoize()
def fetch_comex_partners(
    year_start: int | None = None,
    year_end: int | None = None,
    ncm_codes: Sequence[str] = (),
):
    """COMEX partner (country) ranking with export/import split (backs partnerData)."""
    settings = get_settings()
    table = sqlbuild.table_ref(settings, "bq_serving_dataset", "serving_comex_annual")
    sql, params = sqlbuild.trade_by_partner(
        table,
        partner_code_column="country_code",
        partner_name_column="country_name",
        code_column="ncm_code",
        year_start=year_start,
        year_end=year_end,
        codes=tuple(ncm_codes),
    )
    return run_query(sql, params)


@cache.memoize()
def fetch_comtrade_partners(
    year_start: int | None = None,
    year_end: int | None = None,
    cmd_codes: Sequence[str] = (),
):
    """COMTRADE partner ranking with export/import split (backs partnerData)."""
    settings = get_settings()
    table = sqlbuild.table_ref(settings, "bq_serving_dataset", "serving_comtrade_annual")
    sql, params = sqlbuild.trade_by_partner(
        table,
        partner_code_column="partner_code",
        partner_name_column="partner_name",
        code_column="cmd_code",
        year_start=year_start,
        year_end=year_end,
        codes=tuple(cmd_codes),
    )
    return run_query(sql, params)


@cache.memoize()
def fetch_comex_flows(
    year_start: int | None = None,
    year_end: int | None = None,
    ncm_codes: Sequence[str] = (),
    flow: str | None = None,
):
    """COMEX origin(UF)->destination(country) links (backs flowData for COMEX)."""
    settings = get_settings()
    table = sqlbuild.table_ref(settings, "bq_serving_dataset", "serving_comex_annual")
    sql, params = sqlbuild.trade_flows(
        table,
        origin_code_column="state_acronym",
        origin_name_column="state_name",
        dest_code_column="country_code",
        dest_name_column="country_name",
        code_column="ncm_code",
        year_start=year_start,
        year_end=year_end,
        codes=tuple(ncm_codes),
        flow=flow,
    )
    return run_query(sql, params)


@cache.memoize()
def fetch_comtrade_flows(
    year_start: int | None = None,
    year_end: int | None = None,
    cmd_codes: Sequence[str] = (),
    flow: str | None = None,
):
    """COMTRADE reporter->partner links (backs flowData for COMTRADE)."""
    settings = get_settings()
    table = sqlbuild.table_ref(settings, "bq_serving_dataset", "serving_comtrade_annual")
    sql, params = sqlbuild.trade_flows(
        table,
        origin_code_column="reporter_code",
        origin_name_column="reporter_name",
        dest_code_column="partner_code",
        dest_name_column="partner_name",
        code_column="cmd_code",
        year_start=year_start,
        year_end=year_end,
        codes=tuple(cmd_codes),
        flow=flow,
    )
    return run_query(sql, params)


@cache.memoize()
def fetch_quality_by_source(source: str | None = None):
    """data_quality_flag breakdown per source (backs the quality donut)."""
    settings = get_settings()
    table = sqlbuild.table_ref(settings, "bq_serving_dataset", "serving_quality_by_source")
    sql, params = sqlbuild.quality_by_source(table, source=source)
    return run_query(sql, params)


@cache.memoize()
def fetch_products(source: str):
    """Distinct product list for a source (backs `products`)."""
    table_name, code_col, name_col, _ = _product_source(source)
    settings = get_settings()
    table = sqlbuild.table_ref(settings, "bq_serving_dataset", table_name)
    sql, params = sqlbuild.products(table, code_column=code_col, name_column=name_col)
    return run_query(sql, params)


@cache.memoize()
def fetch_product_timeseries(
    source: str,
    year_start: int | None = None,
    year_end: int | None = None,
    codes: Sequence[str] = (),
    value_column: str | None = None,
):
    """Annual per-product series (value + native quantity) for a source (backs productTS)."""
    table_name, code_col, _, default_value = _product_source(source)
    settings = get_settings()
    table = sqlbuild.table_ref(settings, "bq_serving_dataset", table_name)
    sql, params = sqlbuild.product_timeseries(
        table,
        code_column=code_col,
        value_column=value_column or default_value,
        year_start=year_start,
        year_end=year_end,
        codes=tuple(codes),
    )
    return run_query(sql, params)


@cache.memoize()
def fetch_source_metadata(source: str | None = None):
    """Per-source provenance from gold_source_metadata (backs dataStore.meta)."""
    settings = get_settings()
    table = sqlbuild.table_ref(settings, "bq_gold_dataset", "gold_source_metadata")
    sql, params = sqlbuild.source_metadata(table, source=source)
    return run_query(sql, params)


# Cross-source metric -> (mart, measure column, flow, code column, brazil_only).
# COMEX is Brazil's own customs (no reporter concept). COMTRADE is global: the
# per-country metrics filter reporter = Brazil; world_exp sums over all reporters.
# exp_price is NOT here — the UI derives it as exp_value / exp_weight.
_CROSS_METRICS = {
    "mdic_comex:exp_value": ("serving_comex_annual", "val_yearfx_usd", "export", "ncm_code", False),
    "mdic_comex:imp_value": ("serving_comex_annual", "val_yearfx_usd", "import", "ncm_code", False),
    "mdic_comex:exp_weight": ("serving_comex_annual", "net_weight_kg", "export", "ncm_code", False),
    "un_comtrade:exp_value": (
        "serving_comtrade_annual",
        "val_yearfx_usd",
        "export",
        "cmd_code",
        True,
    ),
    "un_comtrade:imp_value": (
        "serving_comtrade_annual",
        "val_yearfx_usd",
        "import",
        "cmd_code",
        True,
    ),
    "un_comtrade:world_exp": (
        "serving_comtrade_annual",
        "val_yearfx_usd",
        "export",
        "cmd_code",
        False,
    ),
}


def _cross_metric(metric: str) -> tuple[str, str, str, str, bool]:
    try:
        return _CROSS_METRICS[metric]
    except KeyError:
        raise ValueError(
            f"unknown cross metric {metric!r}; choose one of {sorted(_CROSS_METRICS)}"
        ) from None


@cache.memoize()
def fetch_cross_series(
    metric: str,
    year_start: int | None = None,
    year_end: int | None = None,
    codes: Sequence[str] = (),
):
    """Annual single-metric series for the cross-source view (backs crossSeries).

    ``codes`` optionally narrows to a commodity (per-source code) for market share.
    Brazil's COMTRADE share is exp_value (reporter=Brazil) ÷ world_exp (all reporters).
    ``exp_price`` is not served here — it is derived UI-side as exp_value / exp_weight.
    """
    table_name, measure, flow, code_column, brazil_only = _cross_metric(metric)
    settings = get_settings()
    table = sqlbuild.table_ref(settings, "bq_serving_dataset", table_name)
    sql, params = sqlbuild.cross_annual(
        table,
        measure_column=measure,
        flow=flow,
        code_column=code_column,
        codes=tuple(codes),
        reporter_column="reporter_iso_a3" if brazil_only else None,
        reporter_value=settings.comtrade_brazil_iso if brazil_only else None,
        year_start=year_start,
        year_end=year_end,
    )
    return run_query(sql, params)


@cache.memoize(timeout=DEFAULT_CLASSIFICATION_TTL)
def fetch_current_classifications():
    """Live current classification per commodity (from the SCD2 view).

    Short TTL (``Settings.cache_classification_timeout``, default 30s, bound by
    ``init_cache`` onto this function's writable ``cache_timeout``) + explicit
    invalidation on save: the writing instance sees the edit instantly, other
    instances converge within the TTL — so this scales across Cloud Run instances
    on per-process SimpleCache, no shared Redis required.
    """
    settings = get_settings()
    table = sqlbuild.table_ref(settings, "bq_serving_dataset", "dim_commodity_scd2")
    sql, params = sqlbuild.current_classifications(table)
    return run_query(sql, params)
