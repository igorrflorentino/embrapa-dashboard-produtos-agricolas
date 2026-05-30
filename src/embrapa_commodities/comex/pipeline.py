"""Bronze pipeline for MDIC Comex Stat foreign-trade flows.

The shape is genuinely different from BCB SGS (per-year CSV files, a
``(flow, year)`` delta unit instead of a ``reference_date`` rewind), so this
writes its own ``run`` rather than bending a :class:`BcbSeriesSpec` onto it
(see ``docs/adding_a_data_source.md`` step 2). The GCS-land + BQ-load tail is
still delegated to :func:`embrapa_commodities.core.land_and_load`.

Delta model: re-fetch the current year on every run (the MDIC revises the
running year monthly) and skip past years already present in Bronze. ``--full``
ignores the delta and re-fetches the whole ``COMEX_START_YEAR..COMEX_END_YEAR``
window for both flows.
"""

from __future__ import annotations

import logging
from datetime import UTC

import pandas as pd
from google.cloud import bigquery, storage
from google.cloud.exceptions import NotFound

from embrapa_commodities.comex import client
from embrapa_commodities.config import Settings, get_credentials
from embrapa_commodities.core import land_and_load
from embrapa_commodities.gcp.bigquery import ensure_dataset

logger = logging.getLogger(__name__)

# Bronze layout: flow + the raw source columns (all STRING) + the typed
# ingestion timestamp. Order here is the on-table column order.
BRONZE_STRING_COLUMNS: list[str] = ["flow", *client.SOURCE_COLUMNS]

# Clustering mirrors the columns Silver dedupes / filters on most. BigQuery
# caps clustering at 4 columns, so the full natural key
# (flow, CO_ANO, CO_MES, CO_NCM, CO_PAIS, SG_UF_NCM) is trimmed to the four
# most selective for typical product×year×country queries.
CLUSTERING_FIELDS: list[str] = ["flow", "CO_NCM", "CO_ANO", "CO_PAIS"]


def bronze_schema() -> list[bigquery.SchemaField]:
    """``flow`` + raw STRING columns + typed ``ingestion_timestamp``.

    All source columns are NULLABLE: export rows legitimately lack
    ``VL_FRETE``/``VL_SEGURO``, and a raw feed may carry blank fields elsewhere.
    """
    schema = [bigquery.SchemaField("flow", "STRING", mode="REQUIRED")]
    schema += [
        bigquery.SchemaField(col, "STRING", mode="NULLABLE") for col in client.SOURCE_COLUMNS
    ]
    schema.append(bigquery.SchemaField("ingestion_timestamp", "TIMESTAMP", mode="REQUIRED"))
    return schema


def loaded_years(bq_client: bigquery.Client, table_fqn: str, flow: str) -> set[int]:
    """Distinct ``CO_ANO`` already in Bronze for ``flow``. Empty if no table yet."""
    sql = f"select distinct CO_ANO as y from `{table_fqn}` where flow = @flow"
    try:
        rows = bq_client.query(
            sql,
            job_config=bigquery.QueryJobConfig(
                query_parameters=[bigquery.ScalarQueryParameter("flow", "STRING", flow)]
            ),
        ).result()
    except NotFound:
        return set()
    years: set[int] = set()
    for row in rows:
        try:
            years.add(int(row.y))
        except (TypeError, ValueError):
            continue
    return years


def plan_chunks(
    settings: Settings, bq_client: bigquery.Client, table_fqn: str, *, full: bool
) -> list[tuple[str, int]]:
    """The ``(flow, year)`` pairs to fetch this run, in flow-then-year order.

    Full mode: the whole configured window for every flow. Delta mode: the
    current (end) year always, plus any past year not yet in Bronze.
    """
    start, end = settings.comex_start_year, settings.comex_end_year
    chunks: list[tuple[str, int]] = []
    for flow in settings.comex_flows_list:
        if full:
            years = range(start, end + 1)
        else:
            loaded = loaded_years(bq_client, table_fqn, flow)
            years = [y for y in range(start, end + 1) if y == end or y not in loaded]
        chunks.extend((flow, year) for year in years)
    return chunks


def ingest_one(
    settings: Settings,
    flow: str,
    year: int,
    *,
    storage_client: storage.Client,
    bq_client: bigquery.Client,
    table_fqn: str,
) -> str:
    """Download → filter → land one (flow, year) file. Returns destination or ``""``.

    Empty (no configured products in that year/flow) short-circuits before any
    GCS/BQ write so Bronze never accumulates empty Parquet.
    """
    df = client.fetch_flow_year(
        settings.comex_csv_base_url,
        flow,
        year,
        ncm_codes=set(settings.comex_ncm_map),
        chapter_codes=set(settings.comex_chapter_map),
    )
    if df.empty:
        logger.info("Comex %s %d: no configured products, skipping.", flow, year)
        return ""

    # NaN (reindexed import-only columns on export, or blank source fields)
    # must land as SQL NULL, not the literal string "nan".
    df = df.astype(object).where(pd.notna(df), None)
    df.insert(0, "flow", flow)
    df["ingestion_timestamp"] = pd.Timestamp.now(tz=UTC)
    df = df[[*BRONZE_STRING_COLUMNS, "ingestion_timestamp"]]

    return land_and_load(
        df,
        settings=settings,
        storage_client=storage_client,
        bq_client=bq_client,
        source="comex",
        table=settings.bq_bronze_comex_flows_table,
        object_basename=f"{client.FILE_PREFIX[flow]}_{year}",
        destination=table_fqn,
        schema=bronze_schema(),
        clustering_fields=CLUSTERING_FIELDS,
    )


def ensure_destination(settings: Settings, bq_client: bigquery.Client) -> str:
    """Create the Bronze dataset if needed and return the table FQN.

    Runs before any extract because the delta lookup queries the Bronze table.
    """
    dataset_id = f"{settings.gcp_project_id}.{settings.bq_bronze_comex_dataset}"
    ensure_dataset(bq_client, dataset_id, settings.bq_location)
    return f"{dataset_id}.{settings.bq_bronze_comex_flows_table}"


def run(
    settings: Settings,
    *,
    full: bool = False,
    storage_client: storage.Client | None = None,
    bq_client: bigquery.Client | None = None,
) -> str:
    """Ingest every planned (flow, year) chunk. Returns the last destination, or ``""``.

    Single-shot entry point used by ``ingest all`` / the INGESTS registry. The
    hand-written ``ingest comex`` command drives the same ``plan_chunks`` /
    ``ingest_one`` helpers itself so it can emit per-chunk monitor events.
    """
    creds = get_credentials(settings)
    bq_client = bq_client or bigquery.Client(
        project=settings.gcp_project_id, location=settings.bq_location, credentials=creds
    )
    storage_client = storage_client or storage.Client(
        project=settings.gcp_project_id, credentials=creds
    )
    table_fqn = ensure_destination(settings, bq_client)

    last_destination = ""
    for flow, year in plan_chunks(settings, bq_client, table_fqn, full=full):
        destination = ingest_one(
            settings,
            flow,
            year,
            storage_client=storage_client,
            bq_client=bq_client,
            table_fqn=table_fqn,
        )
        if destination:
            last_destination = destination
    return last_destination
