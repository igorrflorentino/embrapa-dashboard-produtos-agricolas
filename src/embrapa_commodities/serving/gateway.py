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
