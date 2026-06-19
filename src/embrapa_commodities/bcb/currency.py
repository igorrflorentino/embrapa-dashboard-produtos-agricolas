"""Bronze pipeline for BCB foreign-exchange series — codes configurable via .env.

Thin variant over the generic BCB SGS pipeline in :mod:`bcb.series`: only the
delta overlap, the ``currency`` label column and the Bronze schema differ from
the inflation variant. NOTE: the overlap is YEAR-GRANULAR (it computes a start
*year*, not a precise day window) — see ``_fx_overlap_start_year`` — so a delta
run re-fetches from the start of the current calendar year (or the prior year
when the last load is in January), i.e. up to a FULL YEAR of daily PTAX, not
"30 days". Size the unattended Cloud Run deadline for that, not the nominal window.
"""

from __future__ import annotations

from datetime import date

from google.cloud import bigquery

from embrapa_commodities.bcb.series import BcbSeriesSpec
from embrapa_commodities.bcb.series import run as _run
from embrapa_commodities.config import Settings

BRONZE_SCHEMA: list[bigquery.SchemaField] = [
    bigquery.SchemaField("series_code", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("currency", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("reference_date_str", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("value_str", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("ingestion_timestamp", "TIMESTAMP", mode="REQUIRED"),
]


def _fx_overlap_start_year(last: date) -> int:
    """Year-granular rewind: re-fetch from the start of the last load's year, or
    the PRIOR year when that load is in January (so a few-day overlap still
    crosses the year boundary). The nominal "30 days" is only the intent — the
    real re-fetch is up to a full year of daily PTAX. Strictly an over-fetch, so
    it never under-covers a revision."""
    return (last.year - 1) if last.month == 1 else last.year


SPEC = BcbSeriesSpec(
    kind="currency",
    label_column="currency",
    series_map=lambda s: s.currency_series_map,
    table=lambda s: s.bq_bronze_bcb_currency_table,
    config_env="BCB_CURRENCY_SERIES",
    schema=BRONZE_SCHEMA,
    overlap_start_year=_fx_overlap_start_year,
)


def run(settings: Settings, *, full: bool = False, from_raw: bool = False) -> str:
    return _run(SPEC, settings, full=full, from_raw=from_raw)
