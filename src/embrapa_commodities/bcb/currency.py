"""Bronze pipeline for BCB foreign-exchange series — codes configurable via .env.

Thin variant over the generic BCB SGS pipeline in :mod:`bcb.series`: only the
30-day delta overlap, the ``currency`` label column and the Bronze schema differ
from the inflation variant.
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
    """FX is daily, so a 30-day overlap is plenty: rewind to the prior year only
    when the last load is in January (30 days back crosses the year boundary)."""
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
