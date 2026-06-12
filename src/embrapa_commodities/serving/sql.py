"""Parameterized BigQuery SQL builders for the serving marts.

Every builder returns ``(sql, params)`` where ``params`` is a list of
``bigquery`` query-parameter objects. The dashboard's callbacks pass user
filters straight through as ``@param`` bindings — never string-formatted into
the SQL — so a malicious filter value can't alter the query (no SQL injection).

The one value that *cannot* be a bind parameter is a column identifier (you
cannot parameterize an identifier in standard SQL). The measure a chart sums is
chosen by the UI, so it is validated against :data:`ALLOWED_VALUE_COLUMNS`
before being interpolated — an allowlist, not escaping.

Pure module: builds strings and parameter objects, performs no I/O.
"""

from __future__ import annotations

from collections.abc import Sequence

from google.cloud import bigquery

# Measures a chart may sum. Interpolated as an identifier (cannot be a bind
# param), so it MUST be validated against this allowlist first.
#
# EUR columns are served (the PEVS/PAM marts carry them — real BCB BRL/EUR
# series), so effective_value_column() resolves EUR server-side instead of
# falling back to BRL. CNY is intentionally absent: gold val_*_cny are all NULL
# (no BCB BRL/CNY series), so no _cny column may be selected.
ALLOWED_VALUE_COLUMNS = frozenset(
    {
        "val_yearfx_brl",
        "val_yearfx_usd",
        "val_yearfx_eur",
        "val_real_ipca_brl",
        "val_real_ipca_usd",
        "val_real_ipca_eur",
        "val_real_igpm_brl",
        "val_real_igpm_eur",
        "val_real_igpdi_brl",
        "val_real_igpdi_eur",
        "net_weight_kg",
        "qty_base",
    }
)


def table_ref(settings, dataset_attr: str, table: str) -> str:
    """Build a fully-qualified `project.dataset.table` reference from settings."""
    project = settings.gcp_project_id
    dataset = getattr(settings, dataset_attr)
    return f"{project}.{dataset}.{table}"


def _validate_column(column: str, allowed: frozenset[str], kind: str) -> str:
    """Guard an interpolated identifier against an allowlist.

    Measure / filter / dimension / product columns cannot be bind parameters, so
    an allowlist — not escaping — is what keeps each one injection-safe.
    """
    if column not in allowed:
        raise ValueError(f"{kind} {column!r} is not allowed; choose one of {sorted(allowed)}")
    return column


def _year_bounds(
    conditions: list[str],
    params: list[bigquery.ScalarQueryParameter],
    year_start: int | None,
    year_end: int | None,
) -> None:
    if year_start is not None:
        conditions.append("reference_year >= @year_start")
        params.append(bigquery.ScalarQueryParameter("year_start", "INT64", year_start))
    if year_end is not None:
        conditions.append("reference_year <= @year_end")
        params.append(bigquery.ScalarQueryParameter("year_end", "INT64", year_end))


# Columns a filter may constrain with `IN UNNEST`. Like value_column, a column
# IDENTIFIER cannot be a bind parameter, so it is interpolated into the SQL and
# therefore MUST be validated against this allowlist. Every builder passes an
# internal literal today; this guarantees a future caller cannot interpolate a
# user-derived identifier (defense-in-depth — there is no current injection path).
ALLOWED_FILTER_COLUMNS = frozenset({"product_code", "ncm_code", "cmd_code"})

# Dimension columns the trade builders interpolate into SELECT / GROUP BY (origin,
# destination, partner — which differ by source: UF/country for COMEX,
# reporter/partner for COMTRADE). Same rule as value_column: an identifier cannot
# be bound, so each is validated against this allowlist before interpolation.
ALLOWED_DIMENSION_COLUMNS = frozenset(
    {
        "state_acronym",
        "state_name",
        "country_code",
        "country_name",
        "reporter_code",
        "reporter_name",
        "reporter_iso_a3",
        "partner_code",
        "partner_name",
    }
)


# Product key + label columns the products / productTS builders interpolate (one
# pair per source). Same allowlist rule as the other identifiers.
ALLOWED_PRODUCT_COLUMNS = frozenset(
    {
        "product_code",
        "product_description",
        "ncm_code",
        "ncm_description",
        "cmd_code",
        "cmd_description",
    }
)


def _in_array(
    conditions: list[str],
    params: list[bigquery.ArrayQueryParameter],
    column: str,
    param_name: str,
    values: Sequence[str],
) -> None:
    if values:
        _validate_column(column, ALLOWED_FILTER_COLUMNS, "filter column")
        conditions.append(f"{column} IN UNNEST(@{param_name})")
        params.append(bigquery.ArrayQueryParameter(param_name, "STRING", list(values)))


def _where(conditions: list[str]) -> str:
    return f"where {' and '.join(conditions)}" if conditions else ""


def _flow(
    conditions: list[str],
    params: list[bigquery.ScalarQueryParameter],
    flow: str | None,
) -> None:
    """Optional `flow = @flow` predicate ('export' / 'import'), bound as a param."""
    if flow is not None:
        conditions.append("flow = @flow")
        params.append(bigquery.ScalarQueryParameter("flow", "STRING", flow))


def production_overview(
    table: str,
    *,
    year_start: int | None = None,
    year_end: int | None = None,
    product_codes: Sequence[str] = (),
    value_column: str = "val_real_ipca_brl",
) -> tuple[str, list]:
    """Annual production total from ``serving_pevs_annual`` (backs overviewTS)."""
    value_column = _validate_column(value_column, ALLOWED_VALUE_COLUMNS, "value_column")
    conditions: list[str] = []
    params: list = []
    _year_bounds(conditions, params, year_start, year_end)
    _in_array(conditions, params, "product_code", "product_codes", product_codes)
    sql = f"""
        select
            reference_year,
            sum({value_column}) as total_value,
            sum(source_rows)    as source_rows
        from `{table}`
        {_where(conditions)}
        group by reference_year
        order by reference_year
    """
    return sql, params


def production_by_uf(
    table: str,
    *,
    year_start: int | None = None,
    year_end: int | None = None,
    product_codes: Sequence[str] = (),
    value_column: str = "val_real_ipca_brl",
) -> tuple[str, list]:
    """Production aggregated by UF from ``serving_pevs_annual`` (backs ufData)."""
    value_column = _validate_column(value_column, ALLOWED_VALUE_COLUMNS, "value_column")
    conditions: list[str] = []
    params: list = []
    _year_bounds(conditions, params, year_start, year_end)
    _in_array(conditions, params, "product_code", "product_codes", product_codes)
    sql = f"""
        select
            state_acronym,
            any_value(state_name)   as state_name,
            any_value(region)       as region,
            any_value(region_abbrev) as region_abbrev,
            sum({value_column})     as total_value
        from `{table}`
        {_where(conditions)}
        group by state_acronym
        order by total_value desc
    """
    return sql, params


def comex_seasonality(
    table: str,
    *,
    year_start: int | None = None,
    year_end: int | None = None,
    ncm_codes: Sequence[str] = (),
    flow: str | None = None,
) -> tuple[str, list]:
    """Monthly COMEX value from ``serving_comex_seasonality`` (backs monthlyData)."""
    conditions: list[str] = []
    params: list = []
    _year_bounds(conditions, params, year_start, year_end)
    _in_array(conditions, params, "ncm_code", "ncm_codes", ncm_codes)
    _flow(conditions, params, flow)
    sql = f"""
        select
            reference_year,
            reference_month,
            any_value(month_abbr_pt) as month_abbr_pt,
            sum(val_yearfx_usd)      as total_value_usd
        from `{table}`
        {_where(conditions)}
        group by reference_year, reference_month
        order by reference_year, reference_month
    """
    return sql, params


def current_classifications(table: str) -> tuple[str, list]:
    """Live current classification per commodity from ``dim_commodity_scd2``.

    The result of this query is the ONLY serving cache that a curation write
    invalidates (the marts are unaffected by a reclassification). The UI LEFT
    JOINs the serving marts to this set on ``commodity_id`` at render time.
    """
    sql = f"""
        select
            commodity_id,
            processing_stage,
            edited_by,
            valid_from
        from `{table}`
        where is_current
        order by commodity_id
    """
    return sql, []


def current_code_industrialization(table: str) -> tuple[str, list]:
    """Live current industrialization level per (source, code) from
    ``dim_code_industrialization_scd2``.

    The finer-grained companion to :func:`current_classifications`. The UI LEFT
    JOINs the Gold code universe (DISTINCT source/code) to this set on
    (source, code); an unmatched code is "a classificar". Invalidated on a
    per-code curation write, same as the commodity-level classification cache.
    """
    sql = f"""
        select
            source,
            code,
            industrialization_level,
            edited_by,
            valid_from
        from `{table}`
        where is_current
        order by source, code
    """
    return sql, []


# ── Trade marts (serving_comex_annual / serving_comtrade_annual) ──────────────
# Raw US$/kg sums; the snapshot layer scales to display magnitudes (÷1e9, ÷1e6)
# per frontend_data_contract.md §2. ``code_column`` is ncm_code (COMEX) or
# cmd_code (COMTRADE); the origin/destination/partner dimensions differ by source
# and are passed as validated identifiers.


def trade_overview(
    table: str,
    *,
    code_column: str,
    year_start: int | None = None,
    year_end: int | None = None,
    codes: Sequence[str] = (),
    flow: str | None = None,
) -> tuple[str, list]:
    """Annual trade value + weight from a trade annual mart (backs overviewTS)."""
    conditions: list[str] = []
    params: list = []
    _year_bounds(conditions, params, year_start, year_end)
    _in_array(conditions, params, code_column, "codes", codes)
    _flow(conditions, params, flow)
    sql = f"""
        select
            reference_year,
            sum(val_yearfx_usd) as total_value_usd,
            sum(net_weight_kg)  as total_weight_kg,
            sum(source_rows)    as source_rows
        from `{table}`
        {_where(conditions)}
        group by reference_year
        order by reference_year
    """
    return sql, params


def comex_by_uf(
    table: str,
    *,
    year_start: int | None = None,
    year_end: int | None = None,
    ncm_codes: Sequence[str] = (),
    flow: str | None = None,
) -> tuple[str, list]:
    """COMEX value + weight by UF from ``serving_comex_annual`` (backs ufData for COMEX)."""
    conditions: list[str] = []
    params: list = []
    _year_bounds(conditions, params, year_start, year_end)
    _in_array(conditions, params, "ncm_code", "ncm_codes", ncm_codes)
    _flow(conditions, params, flow)
    sql = f"""
        select
            state_acronym,
            any_value(state_name)    as state_name,
            any_value(region)        as region,
            any_value(region_abbrev) as region_abbrev,
            sum(val_yearfx_usd)      as total_value_usd,
            sum(net_weight_kg)       as total_weight_kg
        from `{table}`
        {_where(conditions)}
        group by state_acronym
        order by total_value_usd desc
    """
    return sql, params


def trade_by_partner(
    table: str,
    *,
    partner_code_column: str,
    partner_name_column: str,
    code_column: str,
    year_start: int | None = None,
    year_end: int | None = None,
    codes: Sequence[str] = (),
) -> tuple[str, list]:
    """Partner ranking with export/import split (backs partnerData).

    COMEX: partner = country_*; COMTRADE: partner = partner_*. The World partner is
    already dropped upstream (Silver), so no extra filter is needed for COMTRADE.
    """
    partner_code_column = _validate_column(
        partner_code_column, ALLOWED_DIMENSION_COLUMNS, "dimension column"
    )
    partner_name_column = _validate_column(
        partner_name_column, ALLOWED_DIMENSION_COLUMNS, "dimension column"
    )
    conditions: list[str] = []
    params: list = []
    _year_bounds(conditions, params, year_start, year_end)
    _in_array(conditions, params, code_column, "codes", codes)
    sql = f"""
        select
            {partner_code_column}                                  as partner_code,
            any_value({partner_name_column})                       as partner_name,
            sum(case when flow = 'export' then val_yearfx_usd end) as exp_value_usd,
            sum(case when flow = 'import' then val_yearfx_usd end) as imp_value_usd,
            sum(val_yearfx_usd)                                    as value_usd
        from `{table}`
        {_where(conditions)}
        group by {partner_code_column}
        order by value_usd desc
    """
    return sql, params


def trade_flows(
    table: str,
    *,
    origin_code_column: str,
    origin_name_column: str,
    dest_code_column: str,
    dest_name_column: str,
    code_column: str,
    year_start: int | None = None,
    year_end: int | None = None,
    codes: Sequence[str] = (),
    flow: str | None = None,
) -> tuple[str, list]:
    """Origin->destination links for the Sankey (backs flowData).

    COMEX: origin = UF (state), dest = country. COMTRADE: origin = reporter,
    dest = partner. ``value_usd`` is raw ``val_yearfx_usd``.
    """
    origin_code_column = _validate_column(
        origin_code_column, ALLOWED_DIMENSION_COLUMNS, "dimension column"
    )
    origin_name_column = _validate_column(
        origin_name_column, ALLOWED_DIMENSION_COLUMNS, "dimension column"
    )
    dest_code_column = _validate_column(
        dest_code_column, ALLOWED_DIMENSION_COLUMNS, "dimension column"
    )
    dest_name_column = _validate_column(
        dest_name_column, ALLOWED_DIMENSION_COLUMNS, "dimension column"
    )
    conditions: list[str] = []
    params: list = []
    _year_bounds(conditions, params, year_start, year_end)
    _in_array(conditions, params, code_column, "codes", codes)
    _flow(conditions, params, flow)
    sql = f"""
        select
            {origin_code_column}             as origin_code,
            any_value({origin_name_column})  as origin_name,
            {dest_code_column}               as dest_code,
            any_value({dest_name_column})    as dest_name,
            sum(val_yearfx_usd)              as value_usd
        from `{table}`
        {_where(conditions)}
        group by {origin_code_column}, {dest_code_column}
        order by value_usd desc
    """
    return sql, params


def quality_timeseries(table: str) -> tuple[str, list]:
    """data_quality_flag counts per year, straight from a Gold table (backs the
    quality-over-time charts). A small year×flag aggregate — cheap columnar scan,
    memoized by flask-caching. The serving layer has no year-grained quality mart,
    so this reads Gold directly (the same source ``serving_quality_by_source``
    aggregates); promote to a mart if it ever gets hot."""
    sql = f"""
        select
            reference_year,
            data_quality_flag,
            count(*) as n
        from `{table}`
        group by reference_year, data_quality_flag
        order by reference_year
    """
    return sql, []


def comtrade_cpc_value(table: str, *, codes: Sequence[str] = ()) -> tuple[str, list]:
    """Trade value by (customs procedure × flow × year) from the COMTRADE **Bronze**
    (the Gold sums the customs dimension away, so the procedure detail only exists
    here). Excludes the ``C00`` aggregate (it is the total of the specific
    procedures — summing it would double-count). Optional ``codes`` filters to one
    commodity's HS codes (cmdCode). Bronze is all-STRING → ``safe_cast`` the
    measure + year. A bigger scan than a serving mart but cached + secondary;
    promote to a serving mart (preserving customsCode) when this gets hot."""
    conditions = ["customsCode != 'C00'", "customsCode is not null"]
    params: list = []
    if codes:
        conditions.append("cmdCode IN UNNEST(@cmd_codes)")
        params.append(bigquery.ArrayQueryParameter("cmd_codes", "STRING", list(codes)))
    sql = f"""
        select
            customsCode                         as customs_code,
            flowCode                            as flow_code,
            safe_cast(refYear as int64)         as reference_year,
            sum(safe_cast(primaryValue as float64)) as value_usd
        from `{table}`
        {_where(conditions)}
        group by customs_code, flow_code, reference_year
        order by reference_year
    """
    return sql, params


def current_flow_market(table: str) -> tuple[str, list]:
    """Current (customs_code, flow_code) → market from the append-only flow-market
    log: the latest edit per pair (a cleared market = empty string is dropped)."""
    sql = f"""
        select customs_code, flow_code, market, edited_by, edited_at
        from (
            select *, row_number() over (
                partition by customs_code, flow_code order by edited_at desc
            ) as rn
            from `{table}`
        )
        where rn = 1 and market != ''
    """
    return sql, []


def quality_by_product(table: str, *, code_column: str, name_column: str) -> tuple[str, list]:
    """data_quality_flag counts per product, from a Gold table (backs the
    per-product quality FlagBars). Same cheap-aggregate rationale as
    :func:`quality_timeseries`. ``code_column``/``name_column`` are validated
    identifiers (one pair per source)."""
    code_column = _validate_column(code_column, ALLOWED_PRODUCT_COLUMNS, "product column")
    name_column = _validate_column(name_column, ALLOWED_PRODUCT_COLUMNS, "product column")
    sql = f"""
        select
            {code_column}            as code,
            any_value({name_column}) as name,
            data_quality_flag,
            count(*)                 as n
        from `{table}`
        group by {code_column}, data_quality_flag
    """
    return sql, []


def quality_by_source(
    table: str,
    *,
    source: str | None = None,
) -> tuple[str, list]:
    """data_quality_flag breakdown from ``serving_quality_by_source`` (backs quality)."""
    conditions: list[str] = []
    params: list = []
    if source is not None:
        conditions.append("source = @source")
        params.append(bigquery.ScalarQueryParameter("source", "STRING", source))
    sql = f"""
        select
            source,
            data_quality_flag,
            n_rows,
            share
        from `{table}`
        {_where(conditions)}
        order by n_rows desc
    """
    return sql, params


# ── products / productTS — uniform across the three annual marts ──────────────
# All three marts (serving_{pevs,comex,comtrade}_annual) carry the same
# family/unit_native/base_unit/qty_native/qty_base set, so these two builders work
# for any source by swapping the code/name columns. ``unit`` = base_unit (the
# normalised unit), ``unit_native`` = the source label that qty_native is in.


def products(table: str, *, code_column: str, name_column: str) -> tuple[str, list]:
    """Distinct product list ``(code, name, unit, unit_native, family)`` (backs `products`)."""
    code_column = _validate_column(code_column, ALLOWED_PRODUCT_COLUMNS, "product column")
    name_column = _validate_column(name_column, ALLOWED_PRODUCT_COLUMNS, "product column")
    sql = f"""
        select
            {code_column}            as code,
            any_value({name_column}) as name,
            any_value(base_unit)     as unit,
            any_value(unit_native)   as unit_native,
            any_value(family)        as family
        from `{table}`
        group by {code_column}
        order by {code_column}
    """
    return sql, []


def product_timeseries(
    table: str,
    *,
    code_column: str,
    value_column: str = "val_yearfx_usd",
    year_start: int | None = None,
    year_end: int | None = None,
    codes: Sequence[str] = (),
) -> tuple[str, list]:
    """Annual per-product series — value + native quantity (backs productTS).

    ``total_qty_native`` is the statistical quantity in ``unit_native`` (the
    snapshot scales it per the contract); ``family`` rides along for the UI.
    """
    code_column = _validate_column(code_column, ALLOWED_PRODUCT_COLUMNS, "product column")
    value_column = _validate_column(value_column, ALLOWED_VALUE_COLUMNS, "value_column")
    conditions: list[str] = []
    params: list = []
    _year_bounds(conditions, params, year_start, year_end)
    _in_array(conditions, params, code_column, "codes", codes)
    sql = f"""
        select
            {code_column}       as code,
            reference_year,
            sum({value_column}) as total_value,
            sum(qty_native)     as total_qty_native,
            any_value(family)   as family
        from `{table}`
        {_where(conditions)}
        group by {code_column}, reference_year
        order by {code_column}, reference_year
    """
    return sql, params


def source_metadata(table: str, *, source: str | None = None) -> tuple[str, list]:
    """Per-source provenance from ``gold_source_metadata`` (backs dataStore.meta)."""
    conditions: list[str] = []
    params: list = []
    if source is not None:
        conditions.append("source = @source")
        params.append(bigquery.ScalarQueryParameter("source", "STRING", source))
    sql = f"""
        select
            source,
            gold_table,
            cadence,
            year_start,
            year_end,
            total_rows,
            products_total,
            ufs_total,
            last_refresh
        from `{table}`
        {_where(conditions)}
        order by source
    """
    return sql, params


def cross_annual(
    table: str,
    *,
    measure_column: str,
    flow: str | None = None,
    code_column: str | None = None,
    codes: Sequence[str] = (),
    reporter_column: str | None = None,
    reporter_value: str | None = None,
    year_start: int | None = None,
    year_end: int | None = None,
) -> tuple[str, list]:
    """Annual single-measure series for the cross-source view (backs crossSeries points).

    Raw magnitude (the snapshot scales ÷1e9 / ÷1e6). ``codes`` optionally narrows to
    a commodity (per-source code) for market share. ``reporter_*`` restricts to one
    reporting country (Brazil) for the per-country COMTRADE metrics; ``world_exp``
    omits it to sum over every reporter. (``exp_price`` is derived UI-side as
    value ÷ weight, so it has no builder.)
    """
    measure_column = _validate_column(measure_column, ALLOWED_VALUE_COLUMNS, "value_column")
    conditions: list[str] = []
    params: list = []
    _year_bounds(conditions, params, year_start, year_end)
    if code_column is not None:
        _in_array(conditions, params, code_column, "codes", codes)
    _flow(conditions, params, flow)
    if reporter_value is not None:
        reporter_column = _validate_column(
            reporter_column, ALLOWED_DIMENSION_COLUMNS, "dimension column"
        )
        conditions.append(f"{reporter_column} = @reporter")
        params.append(bigquery.ScalarQueryParameter("reporter", "STRING", reporter_value))
    sql = f"""
        select
            reference_year,
            sum({measure_column}) as value
        from `{table}`
        {_where(conditions)}
        group by reference_year
        order by reference_year
    """
    return sql, params
