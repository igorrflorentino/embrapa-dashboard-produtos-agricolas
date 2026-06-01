"""Manual snapshot of Gold tables to GCS for cold-storage / academic conformance.

Triggered via ``embrapa backup-gold`` or ``make backup-gold`` — the latter is
also what ``make dbt-build-prod-with-backup`` chains after a prod dbt build.
Each backup lands at:

    gs://${GCS_BUCKET}/backups/run=<UTC-timestamp>/<table>/<table>-*.parquet

GCS lifecycle rules scoped to the ``backups/`` prefix transition objects to
Nearline at 30d and Coldline at 90d, then DELETE at 365d (see
``gcp/storage.py``) — old snapshots referencing dropped schemas aren't
restorable anyway. ``embrapa doctor`` raises when no snapshot exists and warns
when the latest is older than ``BACKUP_STALENESS_DAYS``.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from google.cloud import bigquery, storage

from embrapa_commodities.config import Settings, get_credentials
from embrapa_commodities.gcp.storage import ensure_bucket

logger = logging.getLogger(__name__)

BACKUP_PREFIX = "backups"


def _gold_tables(settings: Settings, bq_client: bigquery.Client) -> list[str]:
    """Lista as tabelas Gold a serem snapshotadas, derivada por introspecção do dataset.

    Substitui a antiga lista hardcoded — ela silenciou um bug real quando o
    commit a078a24 removeu 3 dos 4 modelos Gold do dbt sem ninguém atualizar
    o backup. Agora a verdade vem do BigQuery em tempo de execução.

    Filtros:
    - ``settings.backup_gold_prefix`` (default ``"gold_"``) exclui tabelas
      ad-hoc / temp que o operador possa ter criado para exploração.
    - ``table_type == "TABLE"`` exclui views (não há views Gold hoje, mas a
      guarda evita surpresa quando alguém adicionar uma).
    """
    dataset_ref = f"{settings.gcp_project_id}.{settings.bq_gold_dataset}"
    prefix = settings.backup_gold_prefix
    return sorted(
        f"{dataset_ref}.{t.table_id}"
        for t in bq_client.list_tables(dataset_ref)
        if t.table_id.startswith(prefix) and t.table_type == "TABLE"
    )


def run(settings: Settings) -> tuple[str, list[str]]:
    """Extract every Gold table to GCS Parquet. Returns (run_id, list of GCS URIs).

    Raises ``RuntimeError`` if the Gold dataset has no matching tables (typical
    when the user runs ``backup-gold`` before any ``make dbt-build-prod``).
    """
    creds = get_credentials(settings)
    storage_client = storage.Client(project=settings.gcp_project_id, credentials=creds)
    ensure_bucket(storage_client, settings.gcs_bucket, settings.bq_location)
    bq_client = bigquery.Client(
        project=settings.gcp_project_id, location=settings.bq_location, credentials=creds
    )

    table_fqns = _gold_tables(settings, bq_client)
    if not table_fqns:
        raise RuntimeError("No Gold tables found to back up. Run `make dbt-build-prod` first.")

    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    uris: list[str] = []

    for table_fqn in table_fqns:
        table_name = table_fqn.split(".")[-1]
        # Wildcard suffix is required so BigQuery can shard the export when
        # the table grows past a single-file limit (~1 GB Parquet).
        destination_uri = (
            f"gs://{settings.gcs_bucket}/{BACKUP_PREFIX}/run={run_id}/"
            f"{table_name}/{table_name}-*.parquet"
        )
        job_config = bigquery.ExtractJobConfig(
            destination_format=bigquery.DestinationFormat.PARQUET,
            # Snappy is the default for Parquet exports but stating it makes
            # the resulting object size predictable.
            compression="SNAPPY",
        )
        logger.info("Backing up %s → %s", table_fqn, destination_uri)
        extract_job = bq_client.extract_table(
            table_fqn,
            destination_uri,
            location=settings.bq_location,
            job_config=job_config,
        )
        extract_job.result()
        uris.append(destination_uri)

    return run_id, uris
