"""Cached, parameterized reads against the BigQuery serving marts.

Each public ``fetch_*`` function is the read half of one chart family: it builds
a parameterized query (``serving.sql``), runs it on BigQuery, and returns a small
Pandas DataFrame. The functions are decorated with ``@cache.memoize()`` so a
repeated (filters) combination is answered from cache instead of re-querying
BigQuery — the round-trip the stateless dashboard would otherwise pay on every
identical callback.

Caching policy:
  * Mart reads (``fetch_production_*``, ``fetch_comex_seasonality``) are
    TTL-only — the marts change solely on the nightly dbt rebuild.
  * ``fetch_current_classifications`` is explicitly invalidated by the curation
    writer on every save (see ``serving.curation``), because that data CAN change
    between rebuilds.

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


@cache.memoize()
def fetch_current_classifications():
    """Live current classification per commodity (from the SCD2 view).

    Invalidated by ``serving.curation.record_processing_stage`` on every save.
    """
    settings = get_settings()
    table = sqlbuild.table_ref(settings, "bq_serving_dataset", "dim_commodity_scd2")
    sql, params = sqlbuild.current_classifications(table)
    return run_query(sql, params)
