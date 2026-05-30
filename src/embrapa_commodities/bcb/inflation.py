"""Bronze pipeline for BCB inflation indices — codes configurable via .env.

Thin variant over the generic BCB SGS pipeline in :mod:`bcb.series`: only the
12-month delta overlap, the ``series_name`` label column and the Bronze schema
differ from the FX variant.
"""

from __future__ import annotations

from google.cloud import bigquery

from embrapa_commodities.bcb.series import BcbSeriesSpec
from embrapa_commodities.bcb.series import run as _run
from embrapa_commodities.config import Settings

# Overlap (in months) re-fetched on each delta run to absorb BCB revisions
# without missing them. BCB occasionally re-publishes the trailing few months
# of IPCA (preliminary → final reading).
DELTA_OVERLAP_MONTHS = 12

BRONZE_SCHEMA: list[bigquery.SchemaField] = [
    bigquery.SchemaField("series_code", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("series_name", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("reference_date_str", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("value_str", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("ingestion_timestamp", "TIMESTAMP", mode="REQUIRED"),
]

SPEC = BcbSeriesSpec(
    kind="inflation",
    label_column="series_name",
    series_map=lambda s: s.inflation_series_map,
    table=lambda s: s.bq_bronze_bcb_inflation_table,
    config_env="BCB_INFLATION_SERIES",
    schema=BRONZE_SCHEMA,
    # Monthly granularity: the 12-month overlap always rewinds a full year.
    overlap_start_year=lambda last: last.year - (DELTA_OVERLAP_MONTHS // 12),
)


def run(settings: Settings, *, full: bool = False) -> str:
    return _run(SPEC, settings, full=full)
