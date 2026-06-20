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
  * ``fetch_current_code_industrialization`` uses a SHORT TTL
    (``CACHE_CLASSIFICATION_TIMEOUT``, default 30s) AND is explicitly invalidated
    by the curation writer. The invalidation makes a curation edit instant on the
    writing instance; the short TTL bounds cross-instance staleness to that window
    (eventual consistency) — which is what lets multiple instances run on
    per-process SimpleCache for free.

There is no global lock and no in-memory Gold DataFrame: state lives in BigQuery,
results are cached, and the process stays stateless and horizontally scalable.

Return-value contract (TRI-STATE — callers must handle all three):
  * most readers return a DataFrame (possibly empty) for a known source/filter;
  * the per-source quality readers (``fetch_quality_timeseries`` /
    ``fetch_quality_by_product``) return ``None`` for an UNKNOWN/unsupported source
    (not in ``_GOLD_TABLE`` / ``_GOLD_PRODUCT``) — a deliberate "this source has no
    such reader", distinct from "the query ran and was empty";
  * the curation reads (``fetch_current_*`` / ``fetch_curators`` /
    ``fetch_banco_metadata``) RAISE ``NotFound`` when the backing table does not
    exist yet, which the seam catches and treats as "nothing configured".
The webapi serializers normalize ``None`` and an empty DataFrame identically (see
``serializers._empty``), so a ``None`` from the quality readers is safe; the
distinction is preserved (rather than flattened to an empty frame) to keep the
"unknown source" signal explicit for any non-serializer caller.
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
    """Execute a parameterized query and return the result as a DataFrame.

    Applies a ``maximum_bytes_billed`` ceiling (``Settings.bq_max_bytes_billed``)
    so the /api serving path can't run an unbounded scan — a pathological filter
    or a cold Bronze read is FAILED by BigQuery (visibly) rather than silently
    billing a runaway query. ``None``/0 disables the cap.
    """
    cfg = get_settings()
    job_config = bigquery.QueryJobConfig(query_parameters=params)
    if cfg.bq_max_bytes_billed:
        job_config.maximum_bytes_billed = cfg.bq_max_bytes_billed
    job = _client().query(sql, job_config=job_config)
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
    "ibge_pam": (
        "serving_pam_annual",
        "product_code",
        "product_description",
        "val_real_ipca_brl",
    ),
    "ibge_ppm": (
        "serving_ppm_annual",
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


# Sources whose mart carries the stock|flow ``measure_kind`` discriminator (only the
# livestock survey today). fetch_products surfaces it so the UI can split the herd
# (stock) from animal-product flows (eggs/milk) that share the ``contagem`` family.
_MEASURE_KIND_SOURCES = {"ibge_ppm"}


# Production sources whose marts are COLUMN-IDENTICAL (PEVS shape: product_code,
# state_acronym, family, qty_native, val_*). fetch_production_* are generic over
# them — PAM rides them with no per-source SQL because serving_pam_annual matches
# serving_pevs_annual's schema. Trade marts are NOT here (different shape).
_PRODUCTION_MART = {
    "ibge_pevs": "serving_pevs_annual",
    "ibge_pam": "serving_pam_annual",
    "ibge_ppm": "serving_ppm_annual",
}


def _production_mart(source: str) -> str:
    try:
        return _PRODUCTION_MART[source]
    except KeyError:
        raise ValueError(
            f"unknown production source {source!r}; choose one of {sorted(_PRODUCTION_MART)}"
        ) from None


@cache.memoize()
def fetch_production_overview(
    year_start: int | None = None,
    year_end: int | None = None,
    product_codes: Sequence[str] = (),
    value_column: str = "val_real_ipca_brl",
    source: str = "ibge_pevs",
    uf_codes: Sequence[str] = (),
):
    """Annual production total for a PEVS-shaped source (backs overviewTS).

    ``uf_codes`` optionally narrows to the producing UFs (cross-source per-UF scoping).
    """
    settings = get_settings()
    table = sqlbuild.table_ref(settings, "bq_serving_dataset", _production_mart(source))
    sql, params = sqlbuild.production_overview(
        table,
        year_start=year_start,
        year_end=year_end,
        product_codes=tuple(product_codes),
        value_column=value_column,
        uf_codes=tuple(uf_codes),
    )
    return run_query(sql, params)


@cache.memoize()
def fetch_production_by_uf(
    year_start: int | None = None,
    year_end: int | None = None,
    product_codes: Sequence[str] = (),
    value_column: str = "val_real_ipca_brl",
    source: str = "ibge_pevs",
    latest_year_only: bool = True,
):
    """Production aggregated by UF for a PEVS-shaped source (backs ufData).

    ``latest_year_only`` (default True) pins the choropleth to the latest year in
    the active window; the export-coefficient by-UF reader passes False for the
    window-cumulative sum it needs.
    """
    settings = get_settings()
    table = sqlbuild.table_ref(settings, "bq_serving_dataset", _production_mart(source))
    sql, params = sqlbuild.production_by_uf(
        table,
        year_start=year_start,
        year_end=year_end,
        product_codes=tuple(product_codes),
        value_column=value_column,
        latest_year_only=latest_year_only,
    )
    return run_query(sql, params)


@cache.memoize()
def fetch_production_by_uf_yearly(
    year_start: int | None = None,
    year_end: int | None = None,
    product_codes: Sequence[str] = (),
    value_column: str = "val_real_ipca_brl",
    source: str = "ibge_pevs",
):
    """Production by (UF, year) for a PEVS-shaped source (backs the ano × UF heatmap)."""
    settings = get_settings()
    table = sqlbuild.table_ref(settings, "bq_serving_dataset", _production_mart(source))
    sql, params = sqlbuild.production_by_uf_yearly(
        table,
        year_start=year_start,
        year_end=year_end,
        product_codes=tuple(product_codes),
        value_column=value_column,
    )
    return run_query(sql, params)


@cache.memoize()
def fetch_productivity(
    product_code: str,
    source: str = "ibge_pam",
    year_start: int | None = None,
    year_end: int | None = None,
):
    """Production + harvested/planted area by (year, UF) for one crop, from a
    PAM-shaped mart (backs ViewProductivity). Yield is recomputed downstream.
    ``year_start``/``year_end`` scope the window to the view's active period filter."""
    settings = get_settings()
    table = sqlbuild.table_ref(settings, "bq_serving_dataset", _production_mart(source))
    sql, params = sqlbuild.productivity(
        table, product_code=product_code, year_start=year_start, year_end=year_end
    )
    return run_query(sql, params)


@cache.memoize()
def fetch_comex_seasonality(
    year_start: int | None = None,
    year_end: int | None = None,
    ncm_codes: Sequence[str] = (),
    flow: str | None = None,
    uf_codes: Sequence[str] = (),
):
    """Monthly COMEX value for the seasonality view (backs monthlyData).

    ``uf_codes`` optionally narrows to the origin UFs (the mart now keeps
    ``state_acronym`` in its grain — P6 per-UF scoping)."""
    settings = get_settings()
    table = sqlbuild.table_ref(settings, "bq_serving_dataset", "serving_comex_seasonality")
    sql, params = sqlbuild.comex_seasonality(
        table,
        year_start=year_start,
        year_end=year_end,
        ncm_codes=tuple(ncm_codes),
        flow=flow,
        uf_codes=tuple(uf_codes),
    )
    return run_query(sql, params)


@cache.memoize()
def fetch_comex_months_per_year():
    """Distinct months present per year from the COMEX seasonality mart (backs the
    partial-latest-year signal in source-meta). Cheap year×month aggregate, cached."""
    settings = get_settings()
    table = sqlbuild.table_ref(settings, "bq_serving_dataset", "serving_comex_seasonality")
    sql, params = sqlbuild.months_present_per_year(table)
    return run_query(sql, params)


@cache.memoize()
def fetch_comex_overview(
    year_start: int | None = None,
    year_end: int | None = None,
    ncm_codes: Sequence[str] = (),
    flow: str | None = None,
    value_column: str = "val_yearfx_usd",
):
    """Annual COMEX value + weight (backs overviewTS for COMEX).

    ``value_column`` picks the currency×correction measure (the seam resolves it
    from the active conventions; default USD). The mart carries the full BRL/USD/EUR
    matrix, so a BRL/EUR display serves the REAL column.
    """
    settings = get_settings()
    table = sqlbuild.table_ref(settings, "bq_serving_dataset", "serving_comex_annual")
    sql, params = sqlbuild.trade_overview(
        table,
        code_column="ncm_code",
        year_start=year_start,
        year_end=year_end,
        codes=tuple(ncm_codes),
        flow=flow,
        value_column=value_column,
    )
    return run_query(sql, params)


@cache.memoize()
def fetch_comtrade_overview(
    year_start: int | None = None,
    year_end: int | None = None,
    cmd_codes: Sequence[str] = (),
    flow: str | None = None,
    value_column: str = "val_yearfx_usd",
):
    """Annual COMTRADE value + weight (backs overviewTS for COMTRADE).

    ``value_column`` picks the currency×correction measure (default USD); the mart
    carries the full BRL/USD/EUR matrix so BRL/EUR serves the REAL column.
    """
    settings = get_settings()
    table = sqlbuild.table_ref(settings, "bq_serving_dataset", "serving_comtrade_annual")
    sql, params = sqlbuild.trade_overview(
        table,
        code_column="cmd_code",
        year_start=year_start,
        year_end=year_end,
        codes=tuple(cmd_codes),
        flow=flow,
        value_column=value_column,
    )
    return run_query(sql, params)


@cache.memoize()
def fetch_comex_by_uf(
    year_start: int | None = None,
    year_end: int | None = None,
    ncm_codes: Sequence[str] = (),
    flow: str | None = None,
    value_column: str = "val_yearfx_usd",
    latest_year_only: bool = True,
):
    """COMEX value + weight aggregated by UF (backs ufData for COMEX).

    ``value_column`` picks the currency×correction measure (default USD; the mart
    carries the full BRL/USD/EUR matrix). ``total_weight_kg`` (raw kg) is always
    present for export_coefficient regardless of which value column is summed.
    ``latest_year_only`` (default True) pins the choropleth to the latest year in
    the active window; the export-coefficient by-UF reader passes False for the
    window-cumulative sum it needs.
    """
    settings = get_settings()
    table = sqlbuild.table_ref(settings, "bq_serving_dataset", "serving_comex_annual")
    sql, params = sqlbuild.comex_by_uf(
        table,
        year_start=year_start,
        year_end=year_end,
        ncm_codes=tuple(ncm_codes),
        flow=flow,
        value_column=value_column,
        latest_year_only=latest_year_only,
    )
    return run_query(sql, params)


@cache.memoize()
def fetch_comex_by_uf_yearly(
    year_start: int | None = None,
    year_end: int | None = None,
    ncm_codes: Sequence[str] = (),
    flow: str | None = None,
    value_column: str = "val_yearfx_usd",
):
    """COMEX value by (UF, year) (backs the ano × UF heatmap for COMEX).

    ``value_column`` picks the currency×correction measure (default USD; the mart
    carries the full BRL/USD/EUR matrix).
    """
    settings = get_settings()
    table = sqlbuild.table_ref(settings, "bq_serving_dataset", "serving_comex_annual")
    sql, params = sqlbuild.comex_by_uf_yearly(
        table,
        year_start=year_start,
        year_end=year_end,
        ncm_codes=tuple(ncm_codes),
        flow=flow,
        value_column=value_column,
    )
    return run_query(sql, params)


@cache.memoize()
def fetch_comex_partners(
    year_start: int | None = None,
    year_end: int | None = None,
    ncm_codes: Sequence[str] = (),
    uf_codes: Sequence[str] = (),
    rank_by: str = "value",
):
    """COMEX partner (country) ranking with export/import split (backs partnerData).

    ``uf_codes`` optionally narrows to the origin UFs (``state_acronym``); empty =
    no UF filter. COMTRADE has no origin-UF column, so its partner reader omits it.
    ``rank_by`` ∈ {value, weight, price} picks the server-side ORDER BY dimension.
    """
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
        uf_codes=tuple(uf_codes),
        rank_by=rank_by,
    )
    return run_query(sql, params)


@cache.memoize()
def fetch_comtrade_partners(
    year_start: int | None = None,
    year_end: int | None = None,
    cmd_codes: Sequence[str] = (),
    rank_by: str = "value",
):
    """COMTRADE partner ranking with export/import split (backs partnerData).

    ``rank_by`` ∈ {value, weight, price} picks the server-side ORDER BY dimension.
    """
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
        # Pin the reporter to Brazil: the mart is multi-reporter (incl. the
        # all-reporters years), so without this the ranking would sum Brazil's
        # bilateral flows together with every other reporter's under each partner.
        reporter_column="reporter_iso_a3",
        reporter_value=settings.comtrade_brazil_iso,
        rank_by=rank_by,
    )
    return run_query(sql, params)


@cache.memoize()
def fetch_products_by_uf(
    *,
    table_key: str,
    code_column: str,
    name_column: str,
    year_start: int | None = None,
    year_end: int | None = None,
    codes: Sequence[str] = (),
    uf_codes: Sequence[str] = (),
    value_column: str = "val_yearfx_usd",
    flow: str | None = None,
):
    """Per-product ranking within a UF selection (backs the 'Base de dados' per-UF
    product breakdown). ``table_key`` + columns are internal literals the seam picks
    per banco (PEVS production / COMEX export); the SQL builder validates each
    interpolated identifier against its allowlist."""
    settings = get_settings()
    table = sqlbuild.table_ref(settings, "bq_serving_dataset", table_key)
    sql, params = sqlbuild.products_by_uf(
        table,
        code_column=code_column,
        name_column=name_column,
        year_start=year_start,
        year_end=year_end,
        codes=tuple(codes),
        uf_codes=tuple(uf_codes),
        value_column=value_column,
        flow=flow,
    )
    return run_query(sql, params)


@cache.memoize()
def fetch_comex_flows(
    year_start: int | None = None,
    year_end: int | None = None,
    ncm_codes: Sequence[str] = (),
    flow: str | None = None,
    uf_codes: Sequence[str] = (),
):
    """COMEX origin(UF)->destination(country) links (backs flowData for COMEX).

    ``uf_codes`` optionally narrows the Sankey to those origin UFs
    (``state_acronym``); empty = no UF filter.
    """
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
        uf_codes=tuple(uf_codes),
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
        # Pin the reporter to Brazil so the Sankey shows Brazil's own export/import
        # links, not every reporter's flows blended (the all-reporters years would
        # otherwise surface non-Brazil origin nodes in a Brazil-perspective view).
        reporter_column="reporter_iso_a3",
        reporter_value=settings.comtrade_brazil_iso,
    )
    return run_query(sql, params)


@cache.memoize()
def fetch_quality_by_source(source: str | None = None):
    """data_quality_flag breakdown per source (backs the quality donut)."""
    settings = get_settings()
    table = sqlbuild.table_ref(settings, "bq_serving_dataset", "serving_quality_by_source")
    sql, params = sqlbuild.quality_by_source(table, source=source)
    return run_query(sql, params)


# Source → its comprehensive Gold table (the year-grained quality scan reads here,
# since the serving marts aren't year×flag). Matches gold_source_metadata.gold_table.
_GOLD_TABLE = {
    "ibge_pevs": "gold_pevs_production",
    "ibge_pam": "gold_pam_production",
    "ibge_ppm": "gold_ppm_production",
    "mdic_comex": "gold_comex_flows",
    "un_comtrade": "gold_comtrade_flows",
}


@cache.memoize()
def fetch_quality_timeseries(source: str):
    """data_quality_flag counts per year for a source (backs quality-over-time).

    Returns ``None`` for an unknown/unsupported source (the deliberate tri-state
    documented in the module docstring); the serializers treat that as empty.
    """
    table_name = _GOLD_TABLE.get(source)
    if table_name is None:
        return None
    settings = get_settings()
    table = sqlbuild.table_ref(settings, "bq_gold_dataset", table_name)
    sql, params = sqlbuild.quality_timeseries(table)
    return run_query(sql, params)


# Source → its Gold product (code, name) columns.
_GOLD_PRODUCT = {
    "ibge_pevs": ("product_code", "product_description"),
    "ibge_pam": ("product_code", "product_description"),
    "ibge_ppm": ("product_code", "product_description"),
    "mdic_comex": ("ncm_code", "ncm_description"),
    "un_comtrade": ("cmd_code", "cmd_description"),
}


@cache.memoize()
def fetch_comtrade_cpc_value(codes: tuple = ()):
    """COMTRADE trade value by (customs procedure × flow × year), from Bronze
    (the only place the customs dimension survives). Backs the market-nature
    analysis. ``codes`` optionally narrows to one commodity's HS codes."""
    settings = get_settings()
    table = sqlbuild.table_ref(
        settings, "bq_bronze_comtrade_dataset", settings.bq_bronze_comtrade_flows_table
    )
    sql, params = sqlbuild.comtrade_cpc_value(table, codes=codes)
    return run_query(sql, params)


@cache.memoize(timeout=DEFAULT_CLASSIFICATION_TTL)
def fetch_curators():
    """Distinct curator emails from the allowlist table (research_inputs.<curators>).

    Short TTL (like the classification reads) so a Console add/remove takes effect
    within the window. Raises NotFound when the table doesn't exist — the seam
    treats that as 'no allowlist configured'. Bounded by maximum_bytes_billed.
    """
    settings = get_settings()
    table = sqlbuild.table_ref(settings, "bq_research_inputs_dataset", settings.bq_curators_table)
    sql = f"select distinct lower(trim(email)) as email from `{table}` where email is not null"
    return run_query(sql, [])


@cache.memoize(timeout=DEFAULT_CLASSIFICATION_TTL)
def fetch_banco_metadata(banco_id: str):
    """Operator-editable maturity/coverage overrides for one banco
    (research_inputs.<banco_metadata>). Short TTL (like the curators read) so a
    Console flip — e.g. beta→estavel — takes effect within the window. Raises
    NotFound when the table doesn't exist — the seam treats that as 'no overrides'
    and uses the registry defaults. Bounded by maximum_bytes_billed."""
    settings = get_settings()
    table = sqlbuild.table_ref(
        settings, "bq_research_inputs_dataset", settings.bq_banco_metadata_table
    )
    sql = (
        "select maturity, maturity_note, maturity_date, cobertura_years, "
        "cobertura_atualizacao, cobertura_granularidade "
        f"from `{table}` where banco_id = @banco_id limit 1"
    )
    params = [bigquery.ScalarQueryParameter("banco_id", "STRING", banco_id)]
    return run_query(sql, params)


@cache.memoize(timeout=DEFAULT_CLASSIFICATION_TTL)
def fetch_current_flow_market():
    """Current (customs_code, flow_code) → market from the flow-market log.
    Raises if the log table doesn't exist yet (no pair classified) — the seam
    catches it and treats it as an empty mapping."""
    settings = get_settings()
    table = sqlbuild.table_ref(
        settings, "bq_research_inputs_dataset", settings.bq_flow_market_log_table
    )
    sql, params = sqlbuild.current_flow_market(table)
    return run_query(sql, params)


@cache.memoize()
def fetch_quality_by_product(source: str):
    """data_quality_flag counts per product for a source (backs per-product FlagBars).

    Returns ``None`` for an unknown/unsupported source (the deliberate tri-state
    documented in the module docstring); the serializers treat that as empty.
    """
    table_name = _GOLD_TABLE.get(source)
    cols = _GOLD_PRODUCT.get(source)
    if table_name is None or cols is None:
        return None
    settings = get_settings()
    table = sqlbuild.table_ref(settings, "bq_gold_dataset", table_name)
    sql, params = sqlbuild.quality_by_product(table, code_column=cols[0], name_column=cols[1])
    return run_query(sql, params)


@cache.memoize()
def fetch_products(source: str):
    """Distinct product list for a source (backs `products`)."""
    table_name, code_col, name_col, _ = _product_source(source)
    settings = get_settings()
    table = sqlbuild.table_ref(settings, "bq_serving_dataset", table_name)
    sql, params = sqlbuild.products(
        table,
        code_column=code_col,
        name_column=name_col,
        with_measure_kind=source in _MEASURE_KIND_SOURCES,
    )
    return run_query(sql, params)


@cache.memoize()
def fetch_product_timeseries(
    source: str,
    year_start: int | None = None,
    year_end: int | None = None,
    codes: Sequence[str] = (),
    value_column: str | None = None,
    uf_codes: Sequence[str] = (),
    flow: str | None = None,
):
    """Annual per-product series (value + native quantity) for a source (backs productTS).

    ``uf_codes`` optionally narrows to the producing/origin UFs (cross-source per-UF
    scoping: PEVS mass/volume + farm-gate price). ``flow`` narrows trade sources to
    one direction (export/import); production sources must leave it ``None`` (their
    marts have no ``flow`` column).
    """
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
        uf_codes=tuple(uf_codes),
        flow=flow,
    )
    return run_query(sql, params)


@cache.memoize()
def fetch_source_metadata(source: str | None = None):
    """Per-source provenance from gold_source_metadata (backs dataStore.meta)."""
    settings = get_settings()
    table = sqlbuild.table_ref(settings, "bq_gold_dataset", "gold_source_metadata")
    sql, params = sqlbuild.source_metadata(table, source=source)
    return run_query(sql, params)


# Cross-source metric -> (mart, measure column, flow, code column, brazil_column).
# COMEX is Brazil's own customs (no reporter concept) → brazil_column None.
# COMTRADE is global: the per-country metrics pin ONE side to Brazil:
#   * exp_value/imp_value → reporter_iso_a3 = Brazil (Brazil's OWN declaration);
#   * partner_exp → partner_iso_a3 = Brazil on IMPORT rows (every OTHER country's
#     declaration of what it imported FROM Brazil — the trade-mirror's third line);
#   * world_exp → no Brazil filter (sum over all reporters).
# exp_price is NOT here — the UI derives it as exp_value / exp_weight.
_CROSS_METRICS = {
    "mdic_comex:exp_value": ("serving_comex_annual", "val_yearfx_usd", "export", "ncm_code", None),
    "mdic_comex:imp_value": ("serving_comex_annual", "val_yearfx_usd", "import", "ncm_code", None),
    "mdic_comex:exp_weight": ("serving_comex_annual", "net_weight_kg", "export", "ncm_code", None),
    "un_comtrade:exp_value": (
        "serving_comtrade_annual",
        "val_yearfx_usd",
        "export",
        "cmd_code",
        "reporter_iso_a3",
    ),
    "un_comtrade:imp_value": (
        "serving_comtrade_annual",
        "val_yearfx_usd",
        "import",
        "cmd_code",
        "reporter_iso_a3",
    ),
    "un_comtrade:partner_exp": (
        "serving_comtrade_annual",
        "val_yearfx_usd",
        "import",
        "cmd_code",
        "partner_iso_a3",
    ),
    "un_comtrade:world_exp": (
        "serving_comtrade_annual",
        "val_yearfx_usd",
        "export",
        "cmd_code",
        None,
    ),
}


def _cross_metric(metric: str) -> tuple[str, str, str, str, str | None]:
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
    uf_codes: Sequence[str] = (),
):
    """Annual single-metric series for the cross-source view (backs crossSeries).

    ``codes`` optionally narrows to a commodity (per-source code) for market share.
    Brazil's COMTRADE share is exp_value (reporter=Brazil) ÷ world_exp (all reporters);
    partner_exp pins partner=Brazil instead (the mirror perspective). ``exp_price``
    is not served here — it is derived UI-side as exp_value / exp_weight.

    ``uf_codes`` optionally narrows to the origin UFs (cross-source per-UF scoping).
    Only the COMEX mart carries ``state_acronym``, so the filter is applied ONLY for
    COMEX metrics; for COMTRADE metrics it is dropped (its origin is a reporter
    country, not a Brazilian UF), keeping the query valid and the series national.
    """
    table_name, measure, flow, code_column, brazil_column = _cross_metric(metric)
    settings = get_settings()
    table = sqlbuild.table_ref(settings, "bq_serving_dataset", table_name)
    uf = tuple(uf_codes) if table_name == "serving_comex_annual" else ()
    sql, params = sqlbuild.cross_annual(
        table,
        measure_column=measure,
        flow=flow,
        code_column=code_column,
        codes=tuple(codes),
        reporter_column=brazil_column,
        reporter_value=settings.comtrade_brazil_iso if brazil_column else None,
        year_start=year_start,
        year_end=year_end,
        uf_codes=uf,
    )
    return run_query(sql, params)


@cache.memoize(timeout=DEFAULT_CLASSIFICATION_TTL)
def fetch_current_code_industrialization():
    """Live current industrialization level per (source, code) from the SCD2 view.

    Short TTL (``Settings.cache_classification_timeout``, default 30s, bound by
    ``init_cache`` onto this function's writable ``cache_timeout``) + explicit
    invalidation on save: the writing instance sees the edit instantly, other
    instances converge within the TTL — so this scales across Cloud Run instances
    on per-process SimpleCache, no shared Redis required.
    """
    settings = get_settings()
    table = sqlbuild.table_ref(settings, "bq_serving_dataset", "dim_code_industrialization_scd2")
    sql, params = sqlbuild.current_code_industrialization(table)
    return run_query(sql, params)
