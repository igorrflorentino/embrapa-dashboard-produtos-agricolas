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
from datetime import UTC, date, datetime

import pandas as pd
from google.cloud import bigquery, storage

from embrapa_commodities.bcb.client import fetch_series
from embrapa_commodities.config import Settings, get_credentials
from embrapa_commodities.core import land_raw, list_raw, read_raw
from embrapa_commodities.gcp.bigquery import ensure_dataset, latest_reference_date, load_dataframe

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
    # Verbatim: no ingestion_timestamp here — that is a Bronze concept stamped in
    # Phase 2, so the raw archive holds exactly what the SGS API returned.
    return pd.concat(frames, ignore_index=True)


CLUSTERING_FIELDS = ["series_code", "reference_date_str"]


def extract_raw(
    spec: BcbSeriesSpec,
    settings: Settings,
    *,
    storage_client: storage.Client,
    bq_client: bigquery.Client,
    table_fqn: str,
    full: bool,
) -> str | None:
    """Phase 1: delta-fetch the SGS window and archive it as a run-stamped raw object.

    Returns the raw basename, or ``None`` when a delta fetch found nothing new.
    BCB is incremental, so each fetch is a recent overlap window — the raw object
    is run-stamped (``<kind>/<run_ts>``) and *appended*, building a verbatim
    audit trail rather than overwriting one object (which would keep only the
    latest window). ``--from-raw`` replays the whole trail.
    """
    df = extract(spec, settings, bq_client, table_fqn, full=full)
    if df.empty:
        return None
    # Label the object by the window actually archived, not the configured one. In
    # delta mode each series fetches only its recent overlap window (and different
    # series may start at different years), so the configured bcb_start_year would
    # claim a span the object doesn't contain. The years sit in the last 4 chars of
    # the dd/mm/yyyy reference_date_str — min/max over them is the verbatim range.
    years = df["reference_date_str"].str[-4:]
    window_start, window_end = years.min(), years.max()
    run_ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    basename = f"{run_ts}_{window_start}_{window_end}"
    land_raw(
        df,
        settings=settings,
        storage_client=storage_client,
        source="bcb",
        dataset=spec.kind,
        basename=basename,
        provenance={
            "source": f"bcb-sgs-{spec.kind}",
            "series": ",".join(spec.series_map(settings)),
            "window": f"{window_start}-{window_end}",
            "mode": "full" if full else "delta",
        },
    )
    return basename


def bronze_from_raw(
    spec: BcbSeriesSpec,
    settings: Settings,
    basenames: list[str],
    *,
    storage_client: storage.Client,
    bq_client: bigquery.Client,
    destination: str,
) -> str:
    """Phase 2: read each raw object, stamp ingestion_timestamp, append to Bronze.

    Multiple ``basenames`` (``--from-raw`` replaying the trail) are appended in
    order; Silver dedupes on the ``(series_code, reference_date_str)`` natural
    key, so overlapping windows collapse to the latest reading.
    """
    for basename in basenames:
        df = read_raw(
            storage_client, settings=settings, source="bcb", dataset=spec.kind, basename=basename
        )
        df["ingestion_timestamp"] = pd.Timestamp.now(tz=UTC)
        load_dataframe(
            bq_client,
            df,
            destination,
            spec.schema,
            time_partitioning_field="ingestion_timestamp",
            clustering_fields=CLUSTERING_FIELDS,
        )
    return destination


def run(
    spec: BcbSeriesSpec, settings: Settings, *, full: bool = False, from_raw: bool = False
) -> str:
    """Extract→raw (Phase 1) then raw→Bronze (Phase 2). Returns destination, or ``""``.

    ``ensure_dataset`` runs before the extract because the delta-start lookup
    queries the Bronze table. ``from_raw`` skips the SGS fetch and rebuilds
    Bronze from the whole archived raw trail (re-derive without re-fetching).
    """
    creds = get_credentials(settings)
    bq_client = bigquery.Client(
        project=settings.gcp_project_id, location=settings.bq_location, credentials=creds
    )
    storage_client = storage.Client(project=settings.gcp_project_id, credentials=creds)
    dataset_id = f"{settings.gcp_project_id}.{settings.bq_bronze_bcb_dataset}"
    ensure_dataset(bq_client, dataset_id, settings.bq_location)
    destination = f"{dataset_id}.{spec.table(settings)}"

    if from_raw:
        basenames = list_raw(storage_client, settings=settings, source="bcb", dataset=spec.kind)
        if not basenames:
            logger.info("BCB %s --from-raw: no raw archived.", spec.kind)
            return ""
    else:
        basename = extract_raw(
            spec,
            settings,
            storage_client=storage_client,
            bq_client=bq_client,
            table_fqn=destination,
            full=full,
        )
        if basename is None:
            return ""
        basenames = [basename]

    return bronze_from_raw(
        spec,
        settings,
        basenames,
        storage_client=storage_client,
        bq_client=bq_client,
        destination=destination,
    )
