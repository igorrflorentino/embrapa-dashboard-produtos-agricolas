"""Two-phase Bronze pipeline for IBGE PAM (Produção Agrícola Municipal, SIDRA 5457).

PAM is the *second* IBGE/SIDRA source. It shares the heavy lifting with PEVS —
the same generic SIDRA client (``fetch_sidra_dataframe``: per-state parallelism +
recursive period-halving) and the same all-STRING Bronze schema
(``ibge.pipeline._bronze_schema``) — but reads its OWN ``pam_*`` settings and
writes to its OWN Bronze table and raw-zone segment (``dataset='pam'``), so a
PEVS ``--from-raw`` replay can never pick up PAM archives and vice versa.

Phase 1 (``extract_raw``) fetches the SIDRA response (filtered by the API query:
table 5457, classification 782, crop products, year window) and archives it
verbatim to ``raw/ibge/pam/``. Phase 2 (``bronze_from_raw``) reads it back,
stamps ``ingestion_timestamp`` and appends to BigQuery Bronze. ``--from-raw``
rebuilds Bronze from that archive without re-querying SIDRA. Delta-by-default:
a routine run re-fetches only the recent (still-revisable) window — PAM, like
PEVS, only revises recent years. See ``PLANS/raw_zone_architecture.md``.

This module deliberately parallels ``ibge.pipeline`` rather than refactoring it
into a shared engine: that module is the LIVE production PEVS path with a test
suite coupled to its internals, so the lean, zero-regression choice is to reuse
its stable primitives and own the thin orchestration here.
"""

from __future__ import annotations

import logging
import time

import pandas as pd
from google.cloud import bigquery, storage

from embrapa_commodities import observability
from embrapa_commodities.config import Settings, get_credentials
from embrapa_commodities.core import land_raw, list_raw, read_raw
from embrapa_commodities.gcp.bigquery import (
    ensure_dataset,
    latest_reference_year,
    load_dataframe,
)
from embrapa_commodities.ibge.client import fetch_sidra_dataframe
from embrapa_commodities.ibge.pipeline import _bronze_schema, _order_by_fetched_at

logger = logging.getLogger(__name__)

# Observability / log tag — distinguishes PAM events from PEVS ('ibge') in the
# monitor and event logs.
PIPELINE = "ibge_pam"

# Both PEVS and PAM are IBGE/SIDRA sources, so they share source='ibge' in the
# raw zone; the DATASET segment is what isolates them: raw/ibge/pam/ vs
# raw/ibge/pevs/. list_raw(source='ibge', dataset=RAW_DATASET) only ever sees
# this source's archives.
SOURCE = "ibge"
RAW_DATASET = "pam"

# PAM is municipality-grained like PEVS; the SIDRA client emits the same
# snake_case columns, so the clustering key is identical.
CLUSTERING_FIELDS = ["municipio_codigo", "ano", "variavel_codigo"]


def _basename(settings: Settings) -> str:
    """Raw object basename encoding the crops + window — re-running the same
    config overwrites a single object (idempotent extract)."""
    return (
        f"products_{'_'.join(settings.pam_product_codes_list)}_"
        f"{settings.pam_start_year}_{settings.pam_end_year}"
    )


def extract_raw(settings: Settings, *, storage_client: storage.Client) -> str | None:
    """Phase 1: fetch SIDRA 5457 and archive the verbatim response. Returns the
    raw basename, or ``None`` when SIDRA had no rows (nothing archived)."""
    if settings.pam_start_year is None:
        raise RuntimeError(
            "PAM_START_YEAR is empty. Run `embrapa discover ibge-periods "
            f"--table-id {settings.pam_table_id}` to find the first available year."
        )
    product_codes = settings.pam_product_codes_list
    started = time.monotonic()
    logger.info(
        "Ingesting PAM table=%s classification=%s products=%s years=%d-%d",
        settings.pam_table_id,
        settings.pam_classification_id,
        product_codes,
        settings.pam_start_year,
        settings.pam_end_year,
    )
    df = fetch_sidra_dataframe(
        table_id=settings.pam_table_id,
        start_year=settings.pam_start_year,
        end_year=settings.pam_end_year,
        classification=settings.pam_classification_id,
        products=product_codes,
        geo_level="n6",
        # Fetch only the 5 substantive variables, not v/all — table 5457's 3 extra
        # "percentual" series would push a dense state past SIDRA's cell limit.
        variables=settings.pam_variable_codes,
    )
    if df.empty:
        # SIDRA had nothing — almost always PAM_END_YEAR set past the latest
        # published year. Skip so the raw zone / Bronze don't accumulate empties.
        observability.emit(
            "ingest_empty",
            pipeline=PIPELINE,
            start_year=settings.pam_start_year,
            end_year=settings.pam_end_year,
            duration_s=round(time.monotonic() - started, 2),
        )
        logger.warning(
            "PAM ingest skipped: SIDRA returned no rows for %d-%d — usually "
            "PAM_END_YEAR is ahead of the latest published PAM year, an "
            "expected state that resolves itself once IBGE publishes the new "
            "year. Do NOT pin PAM_END_YEAR to the latest published year: once "
            "Bronze reaches it, the nightly delta skips entirely and stops "
            "absorbing PAM revisions of recent years (END must float ahead).",
            settings.pam_start_year,
            settings.pam_end_year,
        )
        return None

    basename = _basename(settings)
    land_raw(
        df.astype(str),
        settings=settings,
        storage_client=storage_client,
        source=SOURCE,
        dataset=RAW_DATASET,
        basename=basename,
        provenance={
            "source": "ibge-sidra",
            "table_id": settings.pam_table_id,
            "classification": settings.pam_classification_id,
            "products": ",".join(product_codes),
            "start_year": str(settings.pam_start_year),
            "end_year": str(settings.pam_end_year),
        },
    )
    return basename


def bronze_from_raw(
    settings: Settings,
    basenames: list[str],
    *,
    storage_client: storage.Client,
    bq_client: bigquery.Client,
) -> str:
    """Phase 2: read each raw SIDRA archive, stamp ingestion_timestamp, append to Bronze.

    Multiple ``basenames`` (``--from-raw`` replaying the delta trail) are appended
    in the order given — the caller orders them oldest-fetch-first (see
    ``ibge.pipeline._order_by_fetched_at``) so Silver's dedup on the natural key
    by ``ingestion_timestamp desc`` collapses overlapping windows to the newest
    *extract*, not to whichever basename happened to sort last.
    """
    dataset_id = f"{settings.gcp_project_id}.{settings.bq_bronze_pam_dataset}"
    destination = f"{dataset_id}.{settings.bq_bronze_pam_table}"
    for basename in basenames:
        df = read_raw(
            storage_client, settings=settings, source=SOURCE, dataset=RAW_DATASET, basename=basename
        )
        df = df.astype(str)
        df["ingestion_timestamp"] = pd.Timestamp.now(tz="UTC")
        load_dataframe(
            bq_client,
            df,
            destination,
            _bronze_schema(list(df.columns)),
            time_partitioning_field="ingestion_timestamp",
            clustering_fields=CLUSTERING_FIELDS,
        )
        observability.emit(
            "ingest_loaded", pipeline=PIPELINE, rows=len(df), destination=destination
        )
    return destination


def _delta_start_year(settings: Settings, bq_client: bigquery.Client) -> Settings | None:
    """Re-window ``settings`` to a recent delta start so a routine run re-fetches
    only the latest (still-revisable) years, not the whole configured history.

    PAM only revises recent years, so refetching the last few absorbs revisions
    and picks up a newly published year, while the heavy full-history request
    (which can blow the SIDRA slow-byte deadline) is reserved for ``--full``.

    Returns ``settings`` unchanged when Bronze has no data yet (cold table →
    full). Returns ``None`` — a logged clean no-op — when Bronze is already at or
    past ``pam_end_year``: there is no newer year to fetch, and the naive
    ``last_year - overlap`` could otherwise land *after* ``end_year`` and produce
    an inverted (empty) period list. The effective start is also clamped to never
    exceed ``end_year`` for the same reason.
    """
    table_fqn = (
        f"{settings.gcp_project_id}.{settings.bq_bronze_pam_dataset}.{settings.bq_bronze_pam_table}"
    )
    last_year = latest_reference_year(bq_client, table_fqn)
    if last_year is None:
        return settings
    if last_year >= settings.pam_end_year:
        logger.info(
            "PAM delta: Bronze already at year %d (>= PAM_END_YEAR %d) — "
            "nothing new to fetch, skipping. Raise PAM_END_YEAR or use --full "
            "to force a re-fetch.",
            last_year,
            settings.pam_end_year,
        )
        return None
    floor = settings.pam_start_year if settings.pam_start_year is not None else 0
    # Clamp to <= end_year so the window can never invert (start > end).
    effective_start = min(
        max(floor, last_year - settings.pam_delta_overlap_years), settings.pam_end_year
    )
    logger.info(
        "PAM delta: re-fetching %d-%d (latest Bronze year %d, overlap %d).",
        effective_start,
        settings.pam_end_year,
        last_year,
        settings.pam_delta_overlap_years,
    )
    return settings.model_copy(update={"pam_start_year": effective_start})


def run(
    settings: Settings,
    *,
    full: bool = False,
    from_raw: bool = False,
    storage_client: storage.Client | None = None,
    bq_client: bigquery.Client | None = None,
) -> str:
    """Extract→raw (Phase 1) then raw→Bronze (Phase 2). Returns destination, or ``""``.

    Delta by default: re-fetches only the recent overlap window (see
    ``_delta_start_year``). ``full`` re-fetches the whole configured window.
    ``from_raw`` rebuilds Bronze from the archived raw trail without re-querying
    SIDRA. Optional clients let a batch caller reuse one client across runs.
    """
    creds = get_credentials(settings)
    storage_client = storage_client or storage.Client(
        project=settings.gcp_project_id, credentials=creds
    )
    bq_client = bq_client or bigquery.Client(
        project=settings.gcp_project_id, location=settings.bq_location, credentials=creds
    )
    dataset_id = f"{settings.gcp_project_id}.{settings.bq_bronze_pam_dataset}"
    ensure_dataset(bq_client, dataset_id, settings.bq_location)

    if from_raw:
        basenames = list_raw(storage_client, settings=settings, source=SOURCE, dataset=RAW_DATASET)
        if not basenames:
            logger.warning("PAM --from-raw: no raw archived for dataset %s.", RAW_DATASET)
            return ""
        # Replay oldest-fetch-first so the newest extract wins Silver dedup.
        basenames = _order_by_fetched_at(
            basenames,
            storage_client=storage_client,
            settings=settings,
            source=SOURCE,
            dataset=RAW_DATASET,
        )
    else:
        if not full:
            delta_settings = _delta_start_year(settings, bq_client)
            if delta_settings is None:
                # Bronze already current — clean no-op (see _delta_start_year).
                return ""
            settings = delta_settings
        basename = extract_raw(settings, storage_client=storage_client)
        if basename is None:
            return ""
        basenames = [basename]

    return bronze_from_raw(settings, basenames, storage_client=storage_client, bq_client=bq_client)
