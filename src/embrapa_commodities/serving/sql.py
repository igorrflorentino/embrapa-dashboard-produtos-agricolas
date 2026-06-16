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
# falling back to BRL.
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
# ``state_acronym`` is the UF-of-origin column the COMEX trade marts expose, used
# by the optional UF filter on the flow/partner readers (the filter VALUES stay
# bound — only this identifier is interpolated).
ALLOWED_FILTER_COLUMNS = frozenset({"product_code", "ncm_code", "cmd_code", "state_acronym"})

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
        "partner_iso_a3",
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


def _latest_year_condition(table: str, conditions: list[str]) -> str:
    """A predicate pinning ``reference_year`` to the MAX year under the SAME filters.

    The single-snapshot by-UF readers (``production_by_uf`` / ``comex_by_uf``) back
    a choropleth the UI labels as the latest year and compares against a latest-year
    national KPI — so they must aggregate ONE year, not cumulate the whole
    ``[year_start, year_end]`` window (which inflated every UF tile by the number of
    covered years). "Latest" honours the active period filter: the correlated
    subquery re-applies the same ``conditions`` (year bounds + product/code filters),
    so a user-scoped 2020-2022 request pins to 2022, not the table-wide max.

    The filter VALUES are still bound once (the outer query and the subquery share
    the SAME ``params`` list) — only the table identifier (already validated upstream)
    is interpolated.
    """
    inner = _where(conditions)
    return f"reference_year = (select max(reference_year) from `{table}` {inner})"


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
    latest_year_only: bool = True,
) -> tuple[str, list]:
    """Production aggregated by UF from ``serving_pevs_annual`` (backs ufData).

    By default scoped to the LATEST year within the active ``[year_start, year_end]``
    window (``latest_year_only=True``), NOT cumulated over the whole window: the
    choropleth this backs is labelled — and compared against a latest-year national
    KPI — as a single year, so summing every covered year inflated each UF by the
    number of covered years. ``ufYearly`` (``production_by_uf_yearly``) keeps the
    full per-year history. ``latest_year_only=False`` restores the window-cumulative
    sum, which the export-coefficient by-UF reader needs (it compares production and
    export accumulated over the SAME common-year window).

    Quantities are split by ``family`` so they are only ever summed WITHIN a unit
    family (the same rule the marts enforce): ``q_mass`` sums ``qty_base`` (t) of
    the 'massa' family, ``q_vol`` sums ``qty_base`` (m³) of 'volume'. qty_base —
    not qty_native — is the only summable quantity across a family's mixed-unit
    codes. The serializer scales them to mil t / mi m³.
    """
    value_column = _validate_column(value_column, ALLOWED_VALUE_COLUMNS, "value_column")
    conditions: list[str] = []
    params: list = []
    _year_bounds(conditions, params, year_start, year_end)
    _in_array(conditions, params, "product_code", "product_codes", product_codes)
    if latest_year_only:
        # Pin to the latest year under the same filters (correlated subquery reuses
        # the same bound params) — appended last so the subquery's WHERE excludes it.
        conditions.append(_latest_year_condition(table, conditions))
    sql = f"""
        select
            state_acronym,
            any_value(state_name)   as state_name,
            any_value(region)       as region,
            any_value(region_abbrev) as region_abbrev,
            sum({value_column})     as total_value,
            sum(case when family = 'massa'  then qty_base end) as q_mass,
            sum(case when family = 'volume' then qty_base end) as q_vol
        from `{table}`
        {_where(conditions)}
        group by state_acronym
        order by total_value desc
    """
    return sql, params


def production_by_uf_yearly(
    table: str,
    *,
    year_start: int | None = None,
    year_end: int | None = None,
    product_codes: Sequence[str] = (),
    value_column: str = "val_real_ipca_brl",
) -> tuple[str, list]:
    """Production by (UF, year) from ``serving_pevs_annual`` (backs the ano × UF heatmap).

    The year-grained companion to :func:`production_by_uf`: it adds
    ``reference_year`` to the grain so the geography heatmap renders REAL per-UF
    history instead of fabricating it from the national curve. Quantities are
    split by ``family`` (``q_mass`` = ``qty_base`` t of 'massa', ``q_vol`` = m³ of
    'volume') so they are only ever summed WITHIN a unit family — the same rule
    :func:`production_by_uf` follows.
    """
    value_column = _validate_column(value_column, ALLOWED_VALUE_COLUMNS, "value_column")
    conditions: list[str] = []
    params: list = []
    _year_bounds(conditions, params, year_start, year_end)
    _in_array(conditions, params, "product_code", "product_codes", product_codes)
    sql = f"""
        select
            state_acronym,
            reference_year,
            any_value(state_name)    as state_name,
            any_value(region)        as region,
            any_value(region_abbrev) as region_abbrev,
            sum({value_column})      as total_value,
            sum(case when family = 'massa'  then qty_base end) as q_mass,
            sum(case when family = 'volume' then qty_base end) as q_vol
        from `{table}`
        {_where(conditions)}
        group by state_acronym, reference_year
        order by state_acronym, reference_year
    """
    return sql, params


def productivity(
    table: str,
    *,
    product_code: str,
    year_start: int | None = None,
    year_end: int | None = None,
) -> tuple[str, list]:
    """Production (t) + planted/harvested area (ha) by (year, UF) for ONE crop,
    from a PAM-shaped mart (``serving_pam_annual``; backs ViewProductivity).

    Yield (kg/ha) is a RATIO — not summable — so it is deliberately NOT aggregated
    here; the seam recomputes it as ``production_kg / area_harvested_ha`` at each
    grain it needs (national per year, per UF for the latest year). ``product_code``
    is bound as a parameter (one crop at a time, picked by the view's selector).
    ``year_start``/``year_end`` apply the view's active period filter."""
    conditions: list[str] = ["product_code = @product_code"]
    params: list = [bigquery.ScalarQueryParameter("product_code", "STRING", product_code)]
    _year_bounds(conditions, params, year_start, year_end)
    sql = f"""
        select
            reference_year,
            state_acronym,
            any_value(state_name)        as state_name,
            any_value(region)            as region,
            any_value(region_abbrev)     as region_abbrev,
            sum(qty_native)              as production_t,
            sum(area_planted_ha)         as area_planted_ha,
            sum(area_harvested_ha)       as area_harvested_ha
        from `{table}`
        {_where(conditions)}
        group by reference_year, state_acronym
        order by reference_year, state_acronym
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


def months_present_per_year(table: str) -> tuple[str, list]:
    """Distinct ``reference_month`` count per ``reference_year`` from a monthly mart
    (``serving_comex_seasonality``; backs the partial-latest-year signal).

    A monthly-sourced banco's most recent year is often INCOMPLETE (e.g. COMEX
    publishes through the current month), so a headline YoY that compares a partial
    latest year against a full prior year over-reads as a crash/boom. The seam turns
    this (year → months) map into ``monthsInLatestYear`` / ``latestYearComplete`` /
    ``latestCompleteYear`` in source-meta so the frontend can compute YoY against the
    last COMPLETE year (or label the partial one). Cheap year×month aggregate, cached.
    """
    sql = f"""
        select
            reference_year,
            count(distinct reference_month) as n_months
        from `{table}`
        group by reference_year
        order by reference_year
    """
    return sql, []


def current_code_industrialization(table: str) -> tuple[str, list]:
    """Live current industrialization level per (source, code) from
    ``dim_code_industrialization_scd2``.

    The result of this query is the ONLY serving cache that a curation write
    invalidates (the marts are unaffected by a reclassification). The UI LEFT
    JOINs the Gold code universe (DISTINCT source/code) to this set on
    (source, code); an unmatched code is "a classificar".
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
    value_column: str = "val_yearfx_usd",
) -> tuple[str, list]:
    """Annual trade value + weight from a trade annual mart (backs overviewTS).

    ``value_column`` picks the currency×correction measure — the trade marts now
    carry the full {nominal, real IPCA/IGP-M/IGP-DI} × {BRL, USD, EUR} set (the
    real year-FX / deflated values, NULL pre-1994), so a BRL/EUR display serves the
    REAL column instead of the frontend cross-converting USD via a mock FX rate. The
    output alias stays ``total_value_usd`` (the seam renames it to ``total_value``)
    so the serializer is currency-agnostic regardless of which column is summed.
    """
    value_column = _validate_column(value_column, ALLOWED_VALUE_COLUMNS, "value_column")
    conditions: list[str] = []
    params: list = []
    _year_bounds(conditions, params, year_start, year_end)
    _in_array(conditions, params, code_column, "codes", codes)
    _flow(conditions, params, flow)
    sql = f"""
        select
            reference_year,
            sum({value_column}) as total_value_usd,
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
    value_column: str = "val_yearfx_usd",
    latest_year_only: bool = True,
) -> tuple[str, list]:
    """COMEX value + weight by UF from ``serving_comex_annual`` (backs ufData for COMEX).

    By default scoped to the LATEST year within the active ``[year_start, year_end]``
    window (``latest_year_only=True``), NOT cumulated over the whole window — same
    reasoning as :func:`production_by_uf`: the choropleth is a single labelled year
    compared against a latest-year national KPI. ``latest_year_only=False`` restores
    the window-cumulative sum the export-coefficient by-UF reader needs.

    ``q_mass``/``q_vol`` sum ``qty_base`` (t / m³) per ``family`` — the family-split,
    summable quantity (the same basis the snapshot overview uses), so the COMEX
    geography map can render real mass/volume. ``total_weight_kg`` (raw kg) is kept
    for export_coefficient, which works in kg. ``value_column`` picks the
    currency×correction measure (BRL/USD/EUR — the real columns the mart now carries);
    the alias stays ``total_value_usd`` (the seam renames it ``total_value``).
    """
    value_column = _validate_column(value_column, ALLOWED_VALUE_COLUMNS, "value_column")
    conditions: list[str] = []
    params: list = []
    _year_bounds(conditions, params, year_start, year_end)
    _in_array(conditions, params, "ncm_code", "ncm_codes", ncm_codes)
    _flow(conditions, params, flow)
    if latest_year_only:
        # Pin to the latest year under the same filters (correlated subquery reuses
        # the same bound params) — appended last so the subquery's WHERE excludes it.
        conditions.append(_latest_year_condition(table, conditions))
    sql = f"""
        select
            state_acronym,
            any_value(state_name)    as state_name,
            any_value(region)        as region,
            any_value(region_abbrev) as region_abbrev,
            sum({value_column})      as total_value_usd,
            sum(net_weight_kg)       as total_weight_kg,
            sum(case when family = 'massa'  then qty_base end) as q_mass,
            sum(case when family = 'volume' then qty_base end) as q_vol
        from `{table}`
        {_where(conditions)}
        group by state_acronym
        order by total_value_usd desc
    """
    return sql, params


def comex_by_uf_yearly(
    table: str,
    *,
    year_start: int | None = None,
    year_end: int | None = None,
    ncm_codes: Sequence[str] = (),
    flow: str | None = None,
    value_column: str = "val_yearfx_usd",
) -> tuple[str, list]:
    """COMEX value by (UF, year) from ``serving_comex_annual`` (backs the ano × UF heatmap).

    The year-grained companion to :func:`comex_by_uf`: same per-family ``qty_base``
    split, with ``reference_year`` added to the grain so the COMEX geography heatmap
    renders real per-UF history. ``total_value_usd`` (renamed by the seam to
    ``total_value``) is the choropleth/heatmap measure. ``value_column`` picks the
    currency×correction measure (BRL/USD/EUR — the real columns the mart now carries).
    """
    value_column = _validate_column(value_column, ALLOWED_VALUE_COLUMNS, "value_column")
    conditions: list[str] = []
    params: list = []
    _year_bounds(conditions, params, year_start, year_end)
    _in_array(conditions, params, "ncm_code", "ncm_codes", ncm_codes)
    _flow(conditions, params, flow)
    sql = f"""
        select
            state_acronym,
            reference_year,
            any_value(state_name)    as state_name,
            any_value(region)        as region,
            any_value(region_abbrev) as region_abbrev,
            sum({value_column})      as total_value_usd,
            sum(case when family = 'massa'  then qty_base end) as q_mass,
            sum(case when family = 'volume' then qty_base end) as q_vol
        from `{table}`
        {_where(conditions)}
        group by state_acronym, reference_year
        order by state_acronym, reference_year
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
    uf_codes: Sequence[str] = (),
) -> tuple[str, list]:
    """Partner ranking with export/import split (backs partnerData).

    COMEX: partner = country_*; COMTRADE: partner = partner_*. The World partner is
    already dropped upstream (Silver), so no extra filter is needed for COMTRADE.

    ``uf_codes`` optionally narrows to the origin UFs (``state_acronym``) — only the
    COMEX mart carries that column, so the COMTRADE caller leaves it empty (its
    origin is a reporter country, not a Brazilian UF). Empty/absent = no filter.
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
    _in_array(conditions, params, "state_acronym", "uf_codes", uf_codes)
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
    uf_codes: Sequence[str] = (),
) -> tuple[str, list]:
    """Origin->destination links for the Sankey (backs flowData).

    COMEX: origin = UF (state), dest = country. COMTRADE: origin = reporter,
    dest = partner. ``value_usd`` is raw ``val_yearfx_usd``.

    ``uf_codes`` optionally narrows to the origin UFs (``state_acronym``) — only the
    COMEX mart carries that column, so the COMTRADE caller leaves it empty (its
    origin is a reporter country, not a Brazilian UF). Empty/absent = no filter.
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
    _in_array(conditions, params, "state_acronym", "uf_codes", uf_codes)
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
    promote to a serving mart (preserving customsCode) when this gets hot.

    Bronze is append-only with at-least-once load semantics, so this query must
    apply the same cleaning ``silver_comtrade_flows`` does (it bypasses Silver):
    keep only the latest ingestion batch per (refYear, reporterCode) — without it
    the summed value inflates with every re-ingestion — then dedup on the natural
    key, collapsing the duplicate-qtyUnitCode variants that carry an identical
    ``primaryValue``; and drop the World partner aggregate and legacy HS4 rows
    (both double-count).

    Byte budget: this reader runs under ``maximum_bytes_billed`` and a growing
    Bronze can trip the ceiling and hard-fail the market-nature chart. The lever is
    **column projection** — ``latest_batch`` selects only the columns the dedup
    needs (Bronze is a wide all-STRING table), not ``select *``. BigQuery bills by
    columns/partitions read, so projecting the ~12 needed columns is the real
    saving. Crucially, projection does **not** change which generation the window
    picks, so the predicates stay AFTER batch selection (in ``deduplicated``),
    byte-for-byte mirroring ``silver_comtrade_flows`` — including its retraction
    semantics (a re-published reporter-year that drops rows correctly retires the
    prior generation). (A serving mart preserving ``customsCode`` is still the
    proper fix when this gets hot.)"""
    conditions = [
        "customsCode != 'C00'",
        "customsCode is not null",
        "partnerCode != '0'",  # World aggregate — summing it double-counts partners
        "length(cmdCode) = 6",  # HS6 leaves only — a legacy HS4 row double-counts
    ]
    params: list = []
    if codes:
        conditions.append("cmdCode IN UNNEST(@cmd_codes)")
        params.append(bigquery.ArrayQueryParameter("cmd_codes", "STRING", list(codes)))
    sql = f"""
        with latest_batch as (
            -- Each Bronze load stamps a (year × reporter-batch) chunk with ONE
            -- ingestion_timestamp; a re-published reporter-year REPLACES the
            -- previous generation. Keep only the newest generation per
            -- (refYear, reporterCode). Project an EXPLICIT column list (never
            -- `select *`): BigQuery bills by columns read, Bronze is a wide
            -- all-STRING table, and this reader runs under maximum_bytes_billed —
            -- so reading only the ~12 columns the dedup needs is what keeps a
            -- growing Bronze from tripping the ceiling. Predicates are applied
            -- AFTER this window (in `deduplicated`), so batch selection is
            -- byte-for-byte identical to silver_comtrade_flows.
            select
                customsCode, flowCode, refYear, reporterCode, partnerCode,
                partner2Code, cmdCode, mosCode, motCode, qtyUnitCode,
                primaryValue, ingestion_timestamp
            from `{table}`
            qualify ingestion_timestamp
                = max(ingestion_timestamp) over (partition by refYear, reporterCode)
        ),
        deduplicated as (
            -- Same predicates + dedup key/ordering as silver_comtrade_flows, applied
            -- AFTER batch selection: drop the C00 customs aggregate, the World
            -- partner aggregate, and legacy HS4 rows; then collapse the duplicate
            -- qtyUnitCode variants (identical primaryValue) keeping the real unit.
            select customsCode, flowCode, refYear, primaryValue
            from latest_batch
            {_where(conditions)}
            qualify row_number() over (
                partition by
                    refYear, reporterCode, partnerCode, partner2Code,
                    cmdCode, flowCode, customsCode, mosCode, motCode
                -- Same key + ordering as silver_comtrade_flows: NOT partitioned
                -- by qtyUnitCode (its variants duplicate the value) — recency
                -- first, real-unit-over-'-1' as the tiebreaker.
                order by ingestion_timestamp desc, (qtyUnitCode = '-1')
            ) = 1
        )
        select
            customsCode                         as customs_code,
            flowCode                            as flow_code,
            safe_cast(refYear as int64)         as reference_year,
            sum(safe_cast(primaryValue as float64)) as value_usd
        from deduplicated
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
    """Annual per-product series — value + quantities (backs productTS).

    ``total_qty_native`` is the statistical quantity in ``unit_native``;
    ``total_qty_base`` is the family base unit (t for massa, m³ for volume) and
    is the ONE the snapshot scales for display — native units differ per code
    (kg vs t NCMs in COMEX), so only the base quantity is summable/scalable.
    ``family`` rides along for the UI.
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
            sum(qty_base)       as total_qty_base,
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
    a commodity (per-source code) for market share. ``reporter_*`` pins a geo column
    (reporter_iso_a3 OR partner_iso_a3) to one country (Brazil) for the per-country
    COMTRADE metrics — exp/imp_value filter the reporter, partner_exp the partner;
    ``world_exp`` omits it to sum over every reporter. (``exp_price`` is derived
    UI-side as value ÷ weight, so it has no builder.)
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
