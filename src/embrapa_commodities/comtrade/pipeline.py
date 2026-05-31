"""Two-phase, chunked, resumable Bronze pipeline for UN Comtrade.

The keyed API is pre-filtered by query (our HS codes, reporter batch, flows,
years), so — like IBGE — the fetched frame *is* the Bronze content; Phase 1
archives it verbatim to the raw zone, Phase 2 stamps ingestion_timestamp and
loads BigQuery. See ``PLANS/comtrade_flows.md``.

Chunk = ``(year, reporter-batch)`` → one API call. Resumable: a past-year chunk
whose raw already exists is skipped; the latest year is always re-fetched (UN
Comtrade revises recent years). So a daily-quota interruption just leaves the
un-archived chunks for the next run — no lost work, no duplication beyond what
Silver dedupes.
"""

from __future__ import annotations

import logging
from datetime import UTC

import pandas as pd
from google.cloud import bigquery, storage

from embrapa_commodities.comtrade import client
from embrapa_commodities.config import Settings, get_credentials
from embrapa_commodities.core import land_raw, raw_provenance, read_raw
from embrapa_commodities.gcp.bigquery import ensure_dataset, load_dataframe

logger = logging.getLogger(__name__)

RAW_DATASET = "comtrade_flows"

# Reporters per (year) chunk = one raw archive object. The keyed per-call cap is
# enforced separately by client.fetch_chunk_adaptive (which splits/recurses within
# a chunk), so this only controls raw-file / resume granularity, not call size.
REPORTER_BATCH_SIZE = 8

# Bronze layout: the curated API columns (all STRING) + the typed timestamp.
BRONZE_STRING_COLUMNS: list[str] = list(client.BRONZE_COLUMNS)
CLUSTERING_FIELDS: list[str] = ["reporterCode", "partnerCode", "cmdCode", "refYear"]


def bronze_schema() -> list[bigquery.SchemaField]:
    schema = [bigquery.SchemaField(col, "STRING", mode="NULLABLE") for col in client.BRONZE_COLUMNS]
    schema.append(bigquery.SchemaField("ingestion_timestamp", "TIMESTAMP", mode="REQUIRED"))
    return schema


# Keyed on the scope tuple (not a bare list) so a different COMTRADE_CMD_CODES in
# the same process resolves independently instead of reusing the first run's HS6 list.
_CMD_CODES_CACHE: dict[tuple[str, ...], list[str]] = {}


def resolve_cmd_codes(settings: Settings) -> list[str]:
    """The HS6 leaf codes to request, expanded from the configured scope
    (``comtrade_cmd_codes``, e.g. ``0801``/``44``) via the public HS reference.
    Cached per scope so the HS reference is fetched once per scope, not per chunk."""
    scope = tuple(settings.comtrade_cmd_map)
    if scope not in _CMD_CODES_CACHE:
        _CMD_CODES_CACHE[scope] = client.list_hs6_codes(list(scope))
    return _CMD_CODES_CACHE[scope]


def _reporter_batches(reporters: list[str]) -> list[list[str]]:
    return [
        reporters[i : i + REPORTER_BATCH_SIZE]
        for i in range(0, len(reporters), REPORTER_BATCH_SIZE)
    ]


def _basename(year: int, batch_index: int) -> str:
    """Raw object basename for a (year, reporter-batch) chunk — e.g. ``2022_r03``."""
    return f"{year}_r{batch_index:02d}"


def plan_chunks(settings: Settings, reporters: list[str]) -> list[tuple[int, int, list[str]]]:
    """Every ``(year, batch_index, reporter_batch)`` to fetch, year-then-batch."""
    batches = _reporter_batches(reporters)
    return [
        (year, idx, batch)
        for year in range(settings.comtrade_start_year, settings.comtrade_end_year + 1)
        for idx, batch in enumerate(batches)
    ]


def sync_raw(
    settings: Settings,
    year: int,
    batch_index: int,
    reporters: list[str],
    *,
    storage_client: storage.Client,
    force: bool = False,
) -> bool:
    """Phase 1: fetch one (year, reporter-batch) chunk and archive it. Returns
    ``True`` if (re)fetched, ``False`` if skipped (past-year chunk already raw).

    The latest configured year is always re-fetched (Comtrade revises it);
    ``force`` re-fetches everything.
    """
    basename = _basename(year, batch_index)
    is_latest = year == settings.comtrade_end_year
    if not force and not is_latest:
        stored = raw_provenance(
            storage_client,
            settings=settings,
            source="comtrade",
            dataset=RAW_DATASET,
            basename=basename,
        )
        if stored is not None:
            logger.info("Comtrade %s: raw exists, skipping.", basename)
            return False

    cmd_codes = resolve_cmd_codes(settings)
    # Adaptive: a single dense reporter can exceed the per-call cap at HS6, so the
    # client splits/recurses (reporters→flows→cmd) and concatenates — the frame
    # below is the complete chunk regardless of how many sub-calls it took.
    df = client.fetch_chunk_adaptive(
        settings.comtrade_api_base_url,
        settings.comtrade_api_key,
        reporters=reporters,
        years=[year],
        cmd_codes=cmd_codes,
        flows=settings.comtrade_flows_list,
    )
    if df.empty:
        logger.info("Comtrade %s: no rows.", basename)
        return False
    land_raw(
        df,
        settings=settings,
        storage_client=storage_client,
        source="comtrade",
        dataset=RAW_DATASET,
        basename=basename,
        provenance={
            "source": "un-comtrade",
            "year": str(year),
            "reporters": str(len(reporters)),
            "cmd_scope": ",".join(settings.comtrade_cmd_map),
            "cmd_hs6_count": str(len(cmd_codes)),
            "flows": ",".join(settings.comtrade_flows_list),
        },
    )
    return True


def bronze_one(
    settings: Settings,
    year: int,
    batch_index: int,
    *,
    storage_client: storage.Client,
    bq_client: bigquery.Client,
    table_fqn: str,
) -> str:
    """Phase 2: read the raw chunk, stamp ingestion_timestamp, load Bronze."""
    basename = _basename(year, batch_index)
    df = read_raw(
        storage_client, settings=settings, source="comtrade", dataset=RAW_DATASET, basename=basename
    )
    if df.empty:
        return ""
    df = df.astype(object).where(pd.notna(df), None)
    df = df[BRONZE_STRING_COLUMNS]
    df["ingestion_timestamp"] = pd.Timestamp.now(tz=UTC)

    load_dataframe(
        bq_client,
        df,
        table_fqn,
        bronze_schema(),
        time_partitioning_field="ingestion_timestamp",
        clustering_fields=CLUSTERING_FIELDS,
    )
    return table_fqn


def has_raw(
    settings: Settings, year: int, batch_index: int, *, storage_client: storage.Client
) -> bool:
    return (
        raw_provenance(
            storage_client,
            settings=settings,
            source="comtrade",
            dataset=RAW_DATASET,
            basename=_basename(year, batch_index),
        )
        is not None
    )


def ensure_destination(settings: Settings, bq_client: bigquery.Client) -> str:
    dataset_id = f"{settings.gcp_project_id}.{settings.bq_bronze_comtrade_dataset}"
    ensure_dataset(bq_client, dataset_id, settings.bq_location)
    return f"{dataset_id}.{settings.bq_bronze_comtrade_flows_table}"


def run(
    settings: Settings,
    *,
    full: bool = False,
    from_raw: bool = False,
    storage_client: storage.Client | None = None,
    bq_client: bigquery.Client | None = None,
) -> str:
    """Sync raw (Phase 1) then load Bronze (Phase 2), chunk by (year, batch).

    Resumable: re-running picks up only chunks not yet archived (+ the latest
    year). ``from_raw`` rebuilds Bronze from archived raw without calling the API.
    """
    if not settings.comtrade_api_key:
        raise RuntimeError(
            "COMTRADE_API_KEY is empty — set it in .env (free key from comtradedeveloper.un.org)."
        )
    creds = get_credentials(settings)
    bq_client = bq_client or bigquery.Client(
        project=settings.gcp_project_id, location=settings.bq_location, credentials=creds
    )
    storage_client = storage_client or storage.Client(
        project=settings.gcp_project_id, credentials=creds
    )
    table_fqn = ensure_destination(settings, bq_client)

    reporters = (
        client.list_reporters()
        if settings.comtrade_reporters.strip().lower() == "all"
        else [c.strip() for c in settings.comtrade_reporters.split(",") if c.strip()]
    )

    last_destination = ""
    for year, batch_index, reporter_batch in plan_chunks(settings, reporters):
        if from_raw:
            if not has_raw(settings, year, batch_index, storage_client=storage_client):
                continue
        elif not sync_raw(
            settings, year, batch_index, reporter_batch, storage_client=storage_client, force=full
        ):
            continue
        destination = bronze_one(
            settings,
            year,
            batch_index,
            storage_client=storage_client,
            bq_client=bq_client,
            table_fqn=table_fqn,
        )
        if destination:
            last_destination = destination
    return last_destination
