"""Bronze pipeline for BCB inflation indices — codes configurable via .env.

Thin variant over the generic BCB SGS pipeline in :mod:`bcb.series`: only the
delta overlap, the ``series_name`` label column and the Bronze schema differ
from the FX variant. NOTE: the overlap is YEAR-GRANULAR (it computes a start
*year*, not a precise month window) — see ``overlap_start_year`` below — so a
delta run re-fetches from the start of the prior calendar year, i.e. up to ~24
months for a December load, not exactly "12 months".
"""

from __future__ import annotations

from google.cloud import bigquery

from embrapa_commodities.bcb.series import BcbSeriesSpec
from embrapa_commodities.bcb.series import run as _run
from embrapa_commodities.config import Settings

# Nominal overlap (in months) re-fetched on each delta run to absorb BCB
# revisions without missing them — BCB occasionally re-publishes the trailing
# few months of IPCA (preliminary → final reading). NOTE: this is only the FLOOR;
# overlap_start_year rounds it down to a whole-year rewind (start of last.year-1),
# so the real re-fetch is up to ~24 months. It is strictly an OVER-fetch, so it
# never under-covers a revision.
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


def run(settings: Settings, *, full: bool = False, from_raw: bool = False) -> str:
    return _run(SPEC, settings, full=full, from_raw=from_raw)
