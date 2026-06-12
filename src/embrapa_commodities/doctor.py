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


def _check_pam(settings: Settings) -> CheckResult:
    """SIDRA metadata endpoint responds for the configured PAM table (5457)."""
    url = SIDRA_METADATA_URL.format(table_id=settings.pam_table_id)
    try:
        response = requests.get(url, timeout=PROBE_TIMEOUT_S)
        response.raise_for_status()
        return CheckResult("IBGE PAM reachable", True, f"t{settings.pam_table_id} 200 OK")
    except Exception as exc:
        return CheckResult("IBGE PAM reachable", False, str(exc)[:120])


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


def _check_comex(settings: Settings) -> CheckResult:
    """The Comex Stat file host serves a recent year's export file.

    A HEAD against ``EXP_<end_year>.csv`` verifies reachability without pulling
    the (100+ MB) body. Note: this host is blocked on Claude Code on the web —
    it only passes from a network with the MDIC domain reachable.
    """
    from embrapa_commodities.comex.client import FILE_PREFIX, _ca_bundle

    flow = settings.comex_flows_list[0] if settings.comex_flows_list else "export"
    prefix = FILE_PREFIX.get(flow, "EXP")
    url = f"{settings.comex_csv_base_url.rstrip('/')}/{prefix}_{settings.comex_end_year}.csv"
    try:
        # The host omits its TLS intermediate — reuse the client's certifi+vendored
        # CA bundle so the probe verifies the same way the real download does.
        response = requests.head(
            url, timeout=PROBE_TIMEOUT_S, allow_redirects=True, verify=_ca_bundle()
        )
        response.raise_for_status()
        return CheckResult(
            "COMEX reachable", True, f"{prefix}_{settings.comex_end_year}.csv 200 OK"
        )
    except Exception as exc:
        return CheckResult("COMEX reachable", False, str(exc)[:120])


def _check_comtrade(settings: Settings) -> CheckResult:
    """UN Comtrade reachable + whether the API key is configured.

    The Reporters reference (keyless) confirms connectivity; the keyed ingest
    additionally needs COMTRADE_API_KEY — a missing key is a soft warning (the
    source is optional), not a hard failure.
    """
    from embrapa_commodities.comtrade.client import REPORTERS_REF_URL

    try:
        # The reference host serves this static file over GET only — it 404s on
        # HEAD — so probe with a streamed GET and don't drain the body.
        response = requests.get(
            REPORTERS_REF_URL, timeout=PROBE_TIMEOUT_S, allow_redirects=True, stream=True
        )
        response.close()
        response.raise_for_status()
    except Exception as exc:
        return CheckResult("COMTRADE reachable", False, str(exc)[:120])
    if not settings.comtrade_api_key:
        return CheckResult(
            "COMTRADE reachable", True, "⚠ API 200 OK but COMTRADE_API_KEY unset (keyed ingest)"
        )
    return CheckResult("COMTRADE reachable", True, "API 200 OK; key configured")


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


# ★ Extension point: each (dataset_attr, table) is an object the dashboard BFF
# reads. _check_serving_marts iterates over this list. dim_commodity_scd2
# (the SCD2 curation view) is DELIBERATELY excluded: it is gated by
# `enable_curation` (make dbt-build-curation), so its absence is expected in a
# standard build and would raise a false alarm here.
SERVING_TARGETS: list[tuple[str, str]] = [
    ("bq_serving_dataset", "serving_pevs_annual"),
    ("bq_serving_dataset", "serving_pam_annual"),
    ("bq_serving_dataset", "serving_comex_annual"),
    ("bq_serving_dataset", "serving_comex_seasonality"),
    ("bq_serving_dataset", "serving_comtrade_annual"),
    ("bq_serving_dataset", "serving_quality_by_source"),
    ("bq_gold_dataset", "gold_source_metadata"),
]


def _check_serving_marts(settings: Settings) -> CheckResult:
    """Report whether the serving objects the dashboard BFF reads exist + are populated.

    A deploy-readiness gate for the data layer: the dashboard's ``gateway.fetch_*``
    readers query these marts (+ ``gold_source_metadata`` for provenance). Informational
    like ``_check_bronze_tables`` — a fresh project has none until ``make dbt-build-prod``
    builds them, so a missing mart is reported (with the fix) rather than failing doctor.
    ``num_rows`` is populated for the materialized marts and ``None`` for the
    ``gold_source_metadata`` view (existence-only there).
    """
    try:
        client = bigquery.Client(
            project=settings.gcp_project_id,
            location=settings.bq_location,
            credentials=get_credentials(settings),
        )
        present: list[str] = []
        missing: list[str] = []
        empty: list[str] = []
        for dataset_attr, table in SERVING_TARGETS:
            dataset = getattr(settings, dataset_attr)
            fqn = f"{settings.gcp_project_id}.{dataset}.{table}"
            try:
                tbl = client.get_table(fqn)
            except NotFound:
                missing.append(table)
                continue
            present.append(table)
            if tbl.num_rows == 0:  # 0 only for an empty materialized mart; None for views
                empty.append(table)
        parts: list[str] = []
        if missing:
            parts.append(f"missing={missing} (run `make dbt-build-prod`)")
        if empty:
            parts.append(f"⚠ empty={empty}")
        if not missing and not empty:
            parts.append(f"all present + populated: {present}")
        elif present:
            parts.append(f"present={present}")
        return CheckResult("Serving marts", True, "; ".join(parts))
    except Exception as exc:
        return CheckResult("Serving marts", False, str(exc)[:120])


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

# ★ Extension point: to register a new source, add it here +
# in BRONZE_TARGETS above. For sources without a public API (e.g. SEFAZ NFe via
# bulk download), the "check" can be a stub that returns
# CheckResult(name, ok=True, detail="no public probe"). See
# docs/adding_a_data_source.md.
SOURCE_CHECKS: list[tuple[str, Callable[[Settings], CheckResult]]] = [
    ("ibge", _check_ibge),
    ("pam", _check_pam),
    ("bcb", _check_bcb),
    ("comex", _check_comex),
    ("comtrade", _check_comtrade),
]

# ★ Extension point: each (dataset_attr, table_attr) references a field
# in Settings. _check_bronze_tables iterates over this list.
BRONZE_TARGETS: list[tuple[str, str]] = [
    ("bq_bronze_ibge_dataset", "bq_bronze_ibge_table"),
    ("bq_bronze_pam_dataset", "bq_bronze_pam_table"),
    ("bq_bronze_bcb_dataset", "bq_bronze_bcb_inflation_table"),
    ("bq_bronze_bcb_dataset", "bq_bronze_bcb_currency_table"),
    ("bq_bronze_comex_dataset", "bq_bronze_comex_flows_table"),
    ("bq_bronze_comtrade_dataset", "bq_bronze_comtrade_flows_table"),
]

_POSTCHECKS: list[tuple[str, Callable[[Settings], CheckResult]]] = [
    ("bronze", _check_bronze_tables),
    ("serving", _check_serving_marts),
    ("backup", _check_backup_freshness),
]

# Total ordering of the checks. Each block can be extended without changing this alias.
CHECKS = _INFRA_CHECKS + SOURCE_CHECKS + _POSTCHECKS


def run_all(settings: Settings | None = None) -> list[CheckResult]:
    """Execute every probe and return the results in the same order as CHECKS."""
    settings = settings or get_settings()
    return [fn(settings) for _, fn in CHECKS]
