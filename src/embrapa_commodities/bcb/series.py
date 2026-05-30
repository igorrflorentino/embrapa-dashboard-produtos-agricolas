"""Generic BCB SGS series → Bronze pipeline.

The inflation and currency pipelines are the *same* pipeline with two knobs:
the label column attached to each row (``series_name`` vs ``currency``) and the
delta-overlap rewind rule (12-month for monthly inflation, 30-day for daily
FX). Each defines a :class:`BcbSeriesSpec` and delegates the extract + land/load
mechanics here, so the loop, the rename, the empty-in-delta short-circuit and
the canonical-column projection live in one place.

Scope: this generic is specific to **BCB SGS** series (the ``data``/``valor``
shape, the ``reference_date_str`` natural key, the per-series delta lookup). A
genuinely different source — a non-SGS API, event-grained data, a different
natural key — should write its own pipeline rather than bend a spec onto this.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date

import pandas as pd
from google.cloud import bigquery, storage

from embrapa_commodities.bcb.client import fetch_series
from embrapa_commodities.config import Settings, get_credentials
from embrapa_commodities.core import land_and_load
from embrapa_commodities.gcp.bigquery import ensure_dataset, latest_reference_date

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BcbSeriesSpec:
    """The per-variant knobs that distinguish two otherwise-identical pipelines.

    ``kind`` names the variant for logs and the GCS object basename
    (``<kind>_<from>_<to>.parquet``). ``label_column`` is the second Bronze
    column carrying the human label from the series map. ``series_map`` and
    ``table`` are read off ``Settings`` at call time. ``config_env`` names the
    env var for the empty-config error. ``overlap_start_year`` maps the last
    loaded date to the delta rewind year — the one genuinely source-specific
    line (inflation always rewinds a year; FX only when the last load is in
    January, since 30 days back from January crosses into the prior year).
    """

    kind: str
    label_column: str
    series_map: Callable[[Settings], dict[str, str]]
    table: Callable[[Settings], str]
    config_env: str
    schema: list[bigquery.SchemaField]
    overlap_start_year: Callable[[date], int]


def effective_start_year(
    spec: BcbSeriesSpec,
    bq_client: bigquery.Client,
    table_fqn: str,
    code: str,
    configured_start: int,
) -> int:
    """Pick a start year: ``max(configured, spec.overlap_start_year(last))`` so a
    delta run re-fetches only the recent overlap window, not the whole history.

    Returns ``configured_start`` unchanged when the series has no prior data.
    """
    last = latest_reference_date(bq_client, table_fqn, code)
    if last is None:
        return configured_start
    return max(configured_start, spec.overlap_start_year(last))


def extract(
    spec: BcbSeriesSpec,
    settings: Settings,
    bq_client: bigquery.Client,
    table_fqn: str,
    *,
    full: bool,
) -> pd.DataFrame:
    """Fetch every configured series, tag it, and project the Bronze columns.

    In delta mode an empty fetch means "nothing new" → returns an empty frame.
    In full mode an empty fetch is a real failure → raises.
    """
    series_map = spec.series_map(settings)
    if not series_map:
        raise RuntimeError(f"{spec.config_env} is empty.")

    frames: list[pd.DataFrame] = []
    for code, label in series_map.items():
        start = (
            settings.bcb_start_year
            if full
            else effective_start_year(spec, bq_client, table_fqn, code, settings.bcb_start_year)
        )
        logger.info(
            "BCB %s %s: fetching %d-%d (%s)",
            spec.kind,
            code,
            start,
            settings.bcb_end_year,
            "full" if full else "delta",
        )
        df = fetch_series(code, start, settings.bcb_end_year)
        if df.empty:
            continue
        df = df.rename(columns={"data": "reference_date_str", "valor": "value_str"})
        df["series_code"] = code
        df[spec.label_column] = label
        frames.append(df[["series_code", spec.label_column, "reference_date_str", "value_str"]])
    if not frames:
        # In delta mode, an empty fetch just means "nothing new" — not an error.
        if not full:
            logger.info("BCB %s: no new rows since last ingest.", spec.kind)
            return pd.DataFrame()
        raise RuntimeError(f"BCB returned no {spec.kind} data for the configured window.")
    combined = pd.concat(frames, ignore_index=True)
    combined["ingestion_timestamp"] = pd.Timestamp.now(tz=UTC)
    return combined


def run(spec: BcbSeriesSpec, settings: Settings, *, full: bool = False) -> str:
    """Extract → land in GCS → load into Bronze. Returns destination, or ``""``.

    ``ensure_dataset`` runs before the extract because the delta-start lookup
    queries the Bronze table; the GCS-land + BQ-load tail is delegated to
    :func:`embrapa_commodities.core.land_and_load`.
    """
    creds = get_credentials(settings)
    bq_client = bigquery.Client(
        project=settings.gcp_project_id, location=settings.bq_location, credentials=creds
    )
    dataset_id = f"{settings.gcp_project_id}.{settings.bq_bronze_bcb_dataset}"
    ensure_dataset(bq_client, dataset_id, settings.bq_location)
    table = spec.table(settings)
    destination = f"{dataset_id}.{table}"

    df = extract(spec, settings, bq_client, destination, full=full)
    if df.empty:
        return ""

    storage_client = storage.Client(project=settings.gcp_project_id, credentials=creds)
    return land_and_load(
        df,
        settings=settings,
        storage_client=storage_client,
        bq_client=bq_client,
        source="bcb",
        table=table,
        object_basename=f"{spec.kind}_{settings.bcb_start_year}_{settings.bcb_end_year}",
        destination=destination,
        schema=spec.schema,
        clustering_fields=["series_code", "reference_date_str"],
    )
