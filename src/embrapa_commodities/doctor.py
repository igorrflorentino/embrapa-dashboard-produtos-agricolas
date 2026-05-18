"""Health-check probes for the local environment.

Run via ``embrapa doctor`` to validate ADC, GCP access, .env parsing, and
upstream API reachability in ~10 seconds — useful before kicking off a
long ingest so credential/connectivity issues surface immediately instead
of mid-run.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass

import google.auth
import requests
from google.cloud import bigquery, storage
from google.cloud.exceptions import NotFound

from embrapa_commodities.bcb.client import SGS_URL
from embrapa_commodities.config import Settings, get_settings
from embrapa_commodities.discover import SIDRA_METADATA_URL

logger = logging.getLogger(__name__)

# All probes use the same short timeout — the whole `embrapa doctor` should
# finish in under ~15s even when something is broken.
PROBE_TIMEOUT_S = 10


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    detail: str


def _check_env(settings: Settings) -> CheckResult:
    """The .env parsed and the BCB code mappings are well-formed."""
    try:
        infl = settings.inflation_series_map
        curr = settings.currency_series_map
        products = settings.product_codes
        detail = (
            f"products={','.join(products)}  inflation={list(infl.keys())}  "
            f"currency={list(curr.keys())}"
        )
        return CheckResult(".env parsed", True, detail)
    except Exception as exc:
        return CheckResult(".env parsed", False, str(exc)[:120])


def _check_adc() -> CheckResult:
    """Application Default Credentials are present and resolve a project."""
    try:
        _credentials, project = google.auth.default()
        return CheckResult("ADC credentials", True, f"project={project or '?'}")
    except Exception as exc:
        return CheckResult(
            "ADC credentials",
            False,
            f"{exc} (run `gcloud auth application-default login`)",
        )


def _check_bq(settings: Settings) -> CheckResult:
    """The configured GCP project is reachable for BigQuery."""
    try:
        client = bigquery.Client(project=settings.gcp_project_id, location=settings.bq_location)
        sa = client.get_service_account_email()
        return CheckResult("BigQuery reachable", True, f"sa={sa}")
    except Exception as exc:
        return CheckResult("BigQuery reachable", False, str(exc)[:120])


def _check_gcs(settings: Settings) -> CheckResult:
    """The landing bucket exists (or can be created lazily on first ingest)."""
    try:
        client = storage.Client(project=settings.gcp_project_id)
        bucket = client.bucket(settings.gcs_bucket)
        exists = bucket.exists()
        if exists:
            return CheckResult("GCS bucket", True, f"gs://{settings.gcs_bucket} (exists)")
        return CheckResult(
            "GCS bucket",
            True,
            f"gs://{settings.gcs_bucket} (will be created on first ingest)",
        )
    except Exception as exc:
        return CheckResult("GCS bucket", False, str(exc)[:120])


def _check_ibge(settings: Settings) -> CheckResult:
    """SIDRA metadata endpoint responds for the configured table."""
    url = SIDRA_METADATA_URL.format(table_id=settings.ibge_table_id)
    try:
        response = requests.get(url, timeout=PROBE_TIMEOUT_S)
        response.raise_for_status()
        return CheckResult("IBGE SIDRA reachable", True, f"t{settings.ibge_table_id} 200 OK")
    except Exception as exc:
        return CheckResult("IBGE SIDRA reachable", False, str(exc)[:120])


def _check_bcb(settings: Settings) -> CheckResult:
    """BCB SGS responds for the first inflation series in .env."""
    try:
        code = next(iter(settings.inflation_series_map))
    except StopIteration:
        return CheckResult("BCB SGS reachable", False, "BCB_INFLATION_SERIES is empty")
    # Hit the URL pattern the real client uses, with a tiny 1-year window so
    # we just verify reachability, not data correctness.
    url = SGS_URL.format(code=code, start="01/01/2024", end="31/12/2024")
    try:
        response = requests.get(url, timeout=PROBE_TIMEOUT_S)
        response.raise_for_status()
        return CheckResult("BCB SGS reachable", True, f"sgs.{code} 200 OK")
    except Exception as exc:
        return CheckResult("BCB SGS reachable", False, str(exc)[:120])


def _check_bronze_tables(settings: Settings) -> CheckResult:
    """Report whether Bronze tables already exist (informational, never fails)."""
    try:
        client = bigquery.Client(project=settings.gcp_project_id, location=settings.bq_location)
        targets = [
            (settings.bq_bronze_ibge_dataset, settings.bq_bronze_ibge_table),
            (settings.bq_bronze_bcb_dataset, settings.bq_bronze_bcb_inflation_table),
            (settings.bq_bronze_bcb_dataset, settings.bq_bronze_bcb_currency_table),
        ]
        existing: list[str] = []
        missing: list[str] = []
        for dataset, table in targets:
            fqn = f"{settings.gcp_project_id}.{dataset}.{table}"
            try:
                client.get_table(fqn)
                existing.append(table)
            except NotFound:
                missing.append(table)
        if missing:
            detail = f"present={existing or '∅'}; missing={missing} (run ingest)"
        else:
            detail = f"all present: {existing}"
        return CheckResult("Bronze tables", True, detail)
    except Exception as exc:
        return CheckResult("Bronze tables", False, str(exc)[:120])


CHECKS: list[tuple[str, Callable[[Settings], CheckResult]]] = [
    ("env", _check_env),
    ("adc", lambda _: _check_adc()),
    ("bq", _check_bq),
    ("gcs", _check_gcs),
    ("ibge", _check_ibge),
    ("bcb", _check_bcb),
    ("bronze", _check_bronze_tables),
]


def run_all(settings: Settings | None = None) -> list[CheckResult]:
    """Execute every probe and return the results in the same order as CHECKS."""
    settings = settings or get_settings()
    return [fn(settings) for _, fn in CHECKS]
