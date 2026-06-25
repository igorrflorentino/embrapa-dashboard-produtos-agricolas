"""Shared infrastructure for researcher-authored inputs persisted to the
``research_inputs`` BigQuery dataset.

This is the NEUTRAL layer common to BOTH researcher-facing features, so neither
"owns" the shared plumbing:
  * **Curadoria** (catalog — what enters/exits the dashboard): ``serving/curation.py``.
  * **Engenharia de Atributos** (derived columns from researcher input):
    ``serving/attribute_engineering.py`` (the per-code industrialization +
    customs×flow market-nature writers; currently FROZEN).

It owns the cross-cutting primitives: BigQuery client resolution, the
append-only idempotency helpers (``change_id``), the free-text length caps, the
curator ALLOWLIST table, and the operator-editable banco-metadata override table.
Schemas are always EXPLICIT — autodetect drifts silently across runs.
"""

from __future__ import annotations

import logging
import uuid

from google.cloud import bigquery

from embrapa_commodities.config import Settings, get_settings
from embrapa_commodities.gcp.bigquery import ensure_dataset
from embrapa_commodities.gcp.clients import resolve_bq_client
from embrapa_commodities.serving import sql as sqlbuild

logger = logging.getLogger(__name__)

# Free-text length caps. Open-vocabulary fields (an industrialization level / note
# / market label) are intentionally NOT allowlisted — a researcher may coin
# arbitrary labels (an allowlist would break that UX). These caps are a cheap
# guard against an absurdly large value (a runaway paste / malformed client)
# bloating an immutable audit row, not a content restriction.
MAX_STAGE_LEN = 200
MAX_NOTE_LEN = 2000

# The curator ALLOWLIST — who may POST an edit (authorization, distinct from IAP
# authentication). Console-managed: add/remove a curator by INSERT/DELETE here, no
# redeploy. Empty/absent table → no allowlist (any IAP-authenticated caller may write).
CURATORS_SCHEMA = [
    bigquery.SchemaField("email", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("added_by", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("added_at", "TIMESTAMP", mode="NULLABLE"),
]

# Sparse per-banco metadata overrides (one row per banco the operator has touched).
# Every override column is NULLABLE — a NULL means "keep the registry default".
BANCO_METADATA_SCHEMA = [
    bigquery.SchemaField("banco_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("maturity", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("maturity_note", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("maturity_date", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("cobertura_years", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("cobertura_atualizacao", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("cobertura_granularidade", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("updated_by", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("updated_at", "TIMESTAMP", mode="NULLABLE"),
]


def _bq_client(settings: Settings) -> bigquery.Client:
    return resolve_bq_client(settings)


def ensure_curators_table(
    settings: Settings | None = None,
    client: bigquery.Client | None = None,
) -> str:
    """Create the curator allowlist table if missing; return its FQN. Idempotent.

    Tiny (one row per curator), so no clustering. Manage rows in the BigQuery
    Console (or via SQL) to control who may curate — no redeploy needed.
    """
    cfg = settings or get_settings()
    bq = client or _bq_client(cfg)
    table_fqn = sqlbuild.table_ref(cfg, "bq_research_inputs_dataset", cfg.bq_curators_table)
    ensure_dataset(bq, f"{cfg.gcp_project_id}.{cfg.bq_research_inputs_dataset}", cfg.bq_location)
    bq.create_table(bigquery.Table(table_fqn, schema=CURATORS_SCHEMA), exists_ok=True)
    logger.info("Curators allowlist table ready at %s", table_fqn)
    return table_fqn


def ensure_banco_metadata_table(
    settings: Settings | None = None,
    client: bigquery.Client | None = None,
) -> str:
    """Create the operator-editable banco-metadata override table if missing.

    Idempotent; returns its FQN. Tiny (one row per overridden banco), so no
    clustering. Manage rows in the BigQuery Console (or via SQL) to flip a banco's
    maturity / note / coverage with no redeploy — e.g.::

        MERGE `<project>.research_inputs.banco_metadata` t
        USING (SELECT 'un_comtrade' banco_id, 'estavel' maturity) s
        ON t.banco_id = s.banco_id
        WHEN MATCHED THEN UPDATE SET maturity = s.maturity, updated_at = CURRENT_TIMESTAMP()
        WHEN NOT MATCHED THEN INSERT (banco_id, maturity, updated_at)
            VALUES (s.banco_id, s.maturity, CURRENT_TIMESTAMP());
    """
    cfg = settings or get_settings()
    bq = client or _bq_client(cfg)
    table_fqn = sqlbuild.table_ref(cfg, "bq_research_inputs_dataset", cfg.bq_banco_metadata_table)
    ensure_dataset(bq, f"{cfg.gcp_project_id}.{cfg.bq_research_inputs_dataset}", cfg.bq_location)
    bq.create_table(bigquery.Table(table_fqn, schema=BANCO_METADATA_SCHEMA), exists_ok=True)
    logger.info("Banco metadata override table ready at %s", table_fqn)
    return table_fqn


def _resolve_change_id(change_id: str | None) -> tuple[str, bool]:
    """Return ``(change_id, client_supplied)``. A non-empty client value is the
    IDEMPOTENCY KEY (a retried/double-clicked save reuses it); when absent we mint
    a fresh uuid (which can never pre-exist, so it needs no dedupe check)."""
    cleaned = (change_id or "").strip()
    return (cleaned, True) if cleaned else (uuid.uuid4().hex, False)


def _change_id_seen(bq: bigquery.Client, table_fqn: str, change_id: str) -> bool:
    """True when a row with this client-supplied ``change_id`` already exists in
    the log — the dedupe guard that makes a retried write a no-op. The lookup is a
    single-key scan on a clustered table (cheap). NOTE: this is a best-effort
    SELECT-then-INSERT, not a transaction — two near-simultaneous retries on
    DIFFERENT instances could still both insert. That's acceptable: both rows are
    byte-identical and the SCD2 view collapses them by latest edit, so the worst
    case is one redundant audit row, never a wrong current value."""
    sql = f"select 1 from `{table_fqn}` where change_id = @change_id limit 1"
    params = [bigquery.ScalarQueryParameter("change_id", "STRING", change_id)]
    job = bq.query(sql, job_config=bigquery.QueryJobConfig(query_parameters=params))
    return any(True for _ in job.result())
