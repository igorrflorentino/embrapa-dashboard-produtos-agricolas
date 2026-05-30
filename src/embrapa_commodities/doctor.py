"""Health-check probes for the local environment.

Run via ``embrapa doctor`` to validate ADC, GCP access, .env parsing, and
upstream API reachability in ~10 seconds — useful before kicking off a
long ingest so credential/connectivity issues surface immediately instead
of mid-run.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

import google.auth
import requests
from google.cloud import bigquery, storage
from google.cloud.exceptions import NotFound

from embrapa_commodities.bcb.client import SGS_URL
from embrapa_commodities.config import Settings, get_credentials, get_settings
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


def _check_inflation_pivot_codes(settings: Settings) -> CheckResult:
    """Each Gold inflation pivot code must be present in BCB_INFLATION_SERIES.

    The Gold ``val_real_{ipca,igpm,igpdi}_*`` columns are built from these codes
    (read by dbt via ``env_var``). A pivot code that is not among the ingested
    series → those columns silently come out NULL. Catch the drift here instead
    of discovering empty real-value columns downstream in Looker / Gold consumers.
    """
    try:
        available = set(settings.inflation_series_map)
        missing = {
            label: code
            for label, code in settings.inflation_pivot_codes.items()
            if code not in available
        }
        if missing:
            return CheckResult(
                "Inflation pivot codes",
                False,
                f"not in BCB_INFLATION_SERIES: {missing} "
                f"(available={sorted(available)}) → Gold val_real_* would be NULL",
            )
        return CheckResult(
            "Inflation pivot codes",
            True,
            f"{settings.inflation_pivot_codes} all present",
        )
    except Exception as exc:
        return CheckResult("Inflation pivot codes", False, str(exc)[:120])


def _check_adc(settings: Settings) -> CheckResult:
    """Application Default Credentials are present; reports impersonation target when set."""
    try:
        _credentials, project = google.auth.default()
        if settings.gcp_impersonation_sa:
            detail = f"project={project or '?'} → impersonating {settings.gcp_impersonation_sa}"
        else:
            detail = f"project={project or '?'}"
        return CheckResult("ADC credentials", True, detail)
    except Exception as exc:
        return CheckResult(
            "ADC credentials",
            False,
            f"{exc} (run `gcloud auth application-default login`)",
        )


def _check_bq(settings: Settings) -> CheckResult:
    """The configured GCP project is reachable for BigQuery."""
    try:
        creds = get_credentials(settings)
        client = bigquery.Client(
            project=settings.gcp_project_id, location=settings.bq_location, credentials=creds
        )
        sa = client.get_service_account_email()
        return CheckResult("BigQuery reachable", True, f"sa={sa}")
    except Exception as exc:
        return CheckResult("BigQuery reachable", False, str(exc)[:120])


def _check_gcs(settings: Settings) -> CheckResult:
    """The landing bucket is accessible (or will be created lazily on first ingest)."""
    try:
        creds = get_credentials(settings)
        client = storage.Client(project=settings.gcp_project_id, credentials=creds)
        # list_blobs requires only storage.objects.list (included in objectViewer).
        # bucket.exists() needs storage.buckets.get which objectViewer does not grant.
        try:
            next(client.list_blobs(settings.gcs_bucket, max_results=1), None)
            return CheckResult("GCS bucket", True, f"gs://{settings.gcs_bucket} (exists)")
        except NotFound:
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
    """Report whether Bronze tables already exist (informational, never fails).

    Iterates ``BRONZE_TARGETS`` so new sources extend the check by appending a
    single tuple — see ``docs/adding_a_data_source.md``.
    """
    try:
        client = bigquery.Client(
            project=settings.gcp_project_id,
            location=settings.bq_location,
            credentials=get_credentials(settings),
        )
        targets = [
            (getattr(settings, dataset_attr), getattr(settings, table_attr))
            for dataset_attr, table_attr in BRONZE_TARGETS
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


# `embrapa backup-gold` lays down prefixes shaped `backups/run=YYYYMMDDTHHMMSSZ/...`.
# The trailing slash is important — without it `list_blobs(delimiter="/")` would
# return individual blob names instead of the `run=*/` directory prefixes.
_BACKUP_PREFIX = "backups/"
_BACKUP_RUN_RE = re.compile(r"^backups/run=(\d{8}T\d{6}Z)/$")


def _check_backup_freshness(settings: Settings) -> CheckResult:
    """Warn when the most recent Gold snapshot is older than BACKUP_STALENESS_DAYS.

    Fails (ok=False) when no snapshot exists at all — that means the operator
    has never run ``make dbt-build-prod-with-backup`` (or its CLI equivalent),
    which is a real gap for any project past its first prod build.

    Stale (older than threshold) is reported with ok=True + a ⚠ marker so it
    doesn't flip `doctor` to exit-1 — matching the soft-warning pattern in
    `_check_bronze_tables`.
    """
    try:
        creds = get_credentials(settings)
        client = storage.Client(project=settings.gcp_project_id, credentials=creds)
        # delimiter="/" turns this into a directory listing: blobs.prefixes
        # yields the run=*/ prefixes themselves, not the individual parquet
        # parts beneath them. Far cheaper than enumerating every shard.
        blobs = client.list_blobs(settings.gcs_bucket, prefix=_BACKUP_PREFIX, delimiter="/")
        # Iterating the page iterator is what populates `prefixes` — the
        # google-cloud-storage client only fetches them lazily.
        _ = list(blobs)
        run_prefixes = list(getattr(blobs, "prefixes", []) or [])

        timestamps: list[datetime] = []
        for prefix in run_prefixes:
            match = _BACKUP_RUN_RE.match(prefix)
            if not match:
                continue
            try:
                ts = datetime.strptime(match.group(1), "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)
            except ValueError:
                continue
            timestamps.append(ts)

        if not timestamps:
            return CheckResult(
                "Gold backup freshness",
                False,
                f"no snapshot under gs://{settings.gcs_bucket}/{_BACKUP_PREFIX} "
                "(run `make dbt-build-prod-with-backup`)",
            )

        latest = max(timestamps)
        age_days = (datetime.now(UTC) - latest).days
        latest_str = latest.strftime("%Y-%m-%d %H:%M UTC")
        threshold = settings.backup_staleness_days
        if age_days > threshold:
            return CheckResult(
                "Gold backup freshness",
                True,  # warn, not fail — matches _check_bronze_tables semantics
                f"⚠ stale: latest={latest_str} ({age_days}d ago > {threshold}d threshold)",
            )
        return CheckResult(
            "Gold backup freshness",
            True,
            f"latest={latest_str} ({age_days}d ago, threshold={threshold}d)",
        )
    except Exception as exc:
        return CheckResult("Gold backup freshness", False, str(exc)[:120])


_INFRA_CHECKS: list[tuple[str, Callable[[Settings], CheckResult]]] = [
    ("env", _check_env),
    ("inflation-codes", _check_inflation_pivot_codes),
    ("adc", _check_adc),
    ("bq", _check_bq),
    ("gcs", _check_gcs),
]

# ★ Ponto de extensão: para registrar uma nova fonte, acrescente aqui +
# em BRONZE_TARGETS acima. Para fontes sem API pública (ex. SEFAZ NFe via
# download em lote), o "check" pode ser um stub que retorna
# CheckResult(name, ok=True, detail="sem probe público"). Veja
# docs/adding_a_data_source.md.
SOURCE_CHECKS: list[tuple[str, Callable[[Settings], CheckResult]]] = [
    ("ibge", _check_ibge),
    ("bcb", _check_bcb),
]

# ★ Ponto de extensão: cada (dataset_attr, table_attr) referencia um campo
# em Settings. _check_bronze_tables itera sobre esta lista.
BRONZE_TARGETS: list[tuple[str, str]] = [
    ("bq_bronze_ibge_dataset", "bq_bronze_ibge_table"),
    ("bq_bronze_bcb_dataset", "bq_bronze_bcb_inflation_table"),
    ("bq_bronze_bcb_dataset", "bq_bronze_bcb_currency_table"),
]

_POSTCHECKS: list[tuple[str, Callable[[Settings], CheckResult]]] = [
    ("bronze", _check_bronze_tables),
    ("backup", _check_backup_freshness),
]

# Ordem total dos checks. Cada bloco pode ser estendido sem mudar este alias.
CHECKS = _INFRA_CHECKS + SOURCE_CHECKS + _POSTCHECKS


def run_all(settings: Settings | None = None) -> list[CheckResult]:
    """Execute every probe and return the results in the same order as CHECKS."""
    settings = settings or get_settings()
    return [fn(settings) for _, fn in CHECKS]
