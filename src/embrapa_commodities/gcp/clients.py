"""Shared GCP client construction for the ingestion pipelines.

Every pipeline's ``run`` builds the SAME BigQuery + GCS clients from the
impersonated credentials, unless a caller injects its own (the batch CLI reuses
one client across chunks; tests pass fakes). This was copied verbatim into all
four pipelines (comex/comtrade as ``_resolve_clients``, ibge/pam inline); factor
it here so the credential/location wiring lives in exactly one place.

This is pure client construction — it touches none of the resume / at-least-once
ingestion semantics (those stay per-source in each pipeline's chunk processing).
"""

from __future__ import annotations

from google.cloud import bigquery, storage

from embrapa_commodities.config import Settings, get_credentials


def resolve_clients(
    settings: Settings,
    bq_client: bigquery.Client | None = None,
    storage_client: storage.Client | None = None,
) -> tuple[bigquery.Client, storage.Client]:
    """Build the BigQuery + GCS clients from impersonated creds, unless injected."""
    creds = get_credentials(settings)
    bq_client = bq_client or bigquery.Client(
        project=settings.gcp_project_id, location=settings.bq_location, credentials=creds
    )
    storage_client = storage_client or storage.Client(
        project=settings.gcp_project_id, credentials=creds
    )
    return bq_client, storage_client
