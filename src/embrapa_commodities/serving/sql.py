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
ALLOWED_VALUE_COLUMNS = frozenset(
    {
        "val_yearfx_brl",
        "val_yearfx_usd",
        "val_real_ipca_brl",
        "val_real_ipca_usd",
        "val_real_igpm_brl",
        "val_real_igpdi_brl",
        "net_weight_kg",
        "qty_base",
    }
)


def table_ref(settings, dataset_attr: str, table: str) -> str:
    """Build a fully-qualified `project.dataset.table` reference from settings."""
    project = settings.gcp_project_id
    dataset = getattr(settings, dataset_attr)
    return f"{project}.{dataset}.{table}"


def _validate_value_column(value_column: str) -> str:
    if value_column not in ALLOWED_VALUE_COLUMNS:
        raise ValueError(
            f"value_column {value_column!r} is not allowed; "
            f"choose one of {sorted(ALLOWED_VALUE_COLUMNS)}"
        )
    return value_column


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


def _in_array(
    conditions: list[str],
    params: list[bigquery.ArrayQueryParameter],
    column: str,
    param_name: str,
    values: Sequence[str],
) -> None:
    if values:
        conditions.append(f"{column} IN UNNEST(@{param_name})")
        params.append(bigquery.ArrayQueryParameter(param_name, "STRING", list(values)))


def _where(conditions: list[str]) -> str:
    return f"where {' and '.join(conditions)}" if conditions else ""


def production_overview(
    table: str,
    *,
    year_start: int | None = None,
    year_end: int | None = None,
    product_codes: Sequence[str] = (),
    value_column: str = "val_real_ipca_brl",
) -> tuple[str, list]:
    """Annual production total from ``serving_pevs_annual`` (backs overviewTS)."""
    value_column = _validate_value_column(value_column)
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
    value_column = _validate_value_column(value_column)
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
    if flow is not None:
        conditions.append("flow = @flow")
        params.append(bigquery.ScalarQueryParameter("flow", "STRING", flow))
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
