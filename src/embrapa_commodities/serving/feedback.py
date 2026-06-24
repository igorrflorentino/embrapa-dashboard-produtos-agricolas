"""User feedback writer — the backend of the dashboard's "Reportar problema" button.

Append-only log of researcher-submitted feedback (bug / dúvida / sugestão), mirroring
the curation-log pattern: a typed BigQuery table in the ``research_inputs`` dataset, the
author taken from the IAP-verified header (never the service account), parameterized
DML. After the write, the report is best-effort forwarded to GitHub as an issue when
``feedback_github_repo`` + ``feedback_github_token`` are both configured — the
"loop fechado". The forward is non-fatal: a failure (or no configuration) is logged and
swallowed so it never blocks, nor loses, the durable BigQuery write. The dashboard runs
fully decoupled from the GitHub side.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Mapping

from google.cloud import bigquery

from embrapa_commodities.config import Settings, get_settings
from embrapa_commodities.gcp.bigquery import ensure_dataset
from embrapa_commodities.gcp.clients import resolve_bq_client
from embrapa_commodities.serving import sql as sqlbuild
from embrapa_commodities.serving.iap import author_email_from_headers

logger = logging.getLogger(__name__)

# Free-text caps — cheap guards against a runaway paste bloating the immutable audit
# row, not content restrictions (the message is open-vocabulary by design).
MAX_MESSAGE_LEN = 5000
MAX_URL_LEN = 4000
MAX_UA_LEN = 1000
MAX_VIEW_LEN = 200
MAX_BANCO_LEN = 100
MAX_VERSION_LEN = 50

# The UI offers exactly these report types; anything else is rejected (→ 400).
FEEDBACK_CATEGORIES = ("bug", "duvida", "sugestao")

_GITHUB_API = "https://api.github.com"
_GITHUB_TIMEOUT = (3.05, 8)  # (connect, read) seconds

# Explicit schema — autodetect is never used (it drifts silently across runs).
# `view_id` (not `view`) sidesteps the BigQuery reserved word.
FEEDBACK_LOG_SCHEMA = [
    bigquery.SchemaField("feedback_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("category", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("message", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("url", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("view_id", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("banco", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("app_version", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("browser_info", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("submitted_by", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("submitted_at", "TIMESTAMP", mode="REQUIRED"),
    bigquery.SchemaField("issue_url", "STRING", mode="NULLABLE"),
]


class FeedbackValidationError(ValueError):
    """Empty/over-length message or bad category — the route maps it to HTTP 400."""


def _clip(value: str | None, limit: int) -> str | None:
    """Trim + length-cap an optional free-text field; '' → None (stored as NULL)."""
    if not value:
        return None
    value = value.strip()
    return value[:limit] or None


def _validate(category: str, message: str) -> str:
    message = (message or "").strip()
    if not message:
        raise FeedbackValidationError("message is required")
    if len(message) > MAX_MESSAGE_LEN:
        raise FeedbackValidationError(f"message exceeds {MAX_MESSAGE_LEN} characters")
    if category not in FEEDBACK_CATEGORIES:
        raise FeedbackValidationError(f"category must be one of {', '.join(FEEDBACK_CATEGORIES)}")
    return message


def ensure_feedback_log_table(
    settings: Settings | None = None,
    client: bigquery.Client | None = None,
) -> str:
    """Create the feedback-log dataset + table if missing (idempotent, auto-heal)."""
    cfg = settings or get_settings()
    bq = client or resolve_bq_client(cfg)
    table_fqn = sqlbuild.table_ref(cfg, "bq_research_inputs_dataset", cfg.bq_feedback_log_table)
    ensure_dataset(bq, f"{cfg.gcp_project_id}.{cfg.bq_research_inputs_dataset}", cfg.bq_location)
    table = bigquery.Table(table_fqn, schema=FEEDBACK_LOG_SCHEMA)
    table.clustering_fields = ["category"]
    bq.create_table(table, exists_ok=True)
    logger.info("Feedback log ready at %s", table_fqn)
    return table_fqn


def _forward_to_github(
    cfg: Settings,
    *,
    category: str,
    message: str,
    submitted_by: str,
    url: str | None,
    view_id: str | None,
    banco: str | None,
) -> str | None:
    """Open a GitHub issue for the report ("loop fechado"). Best-effort: returns the
    issue URL on success, or None when GitHub is not configured or the call fails
    (logged, never raised — the feedback is already safe in BigQuery)."""
    repo, token = cfg.feedback_github_repo, cfg.feedback_github_token
    if not (repo and token):
        return None
    # Lazy import: keep the optional integration out of the webapi import path.
    import requests

    title = f"[Feedback/{category}] {message.splitlines()[0][:80]}"
    body = [
        message,
        "",
        "---",
        f"- **Reportado por:** {submitted_by}",
        f"- **Categoria:** {category}",
    ]
    if view_id:
        body.append(f"- **Perspectiva:** {view_id}")
    if banco:
        body.append(f"- **Banco:** {banco}")
    if url:
        body.append(f"- **Reproduzir:** {url}")
    body.append("\n_Aberto automaticamente pelo canal de feedback do dashboard._")
    try:
        resp = requests.post(
            f"{_GITHUB_API}/repos/{repo}/issues",
            json={"title": title, "body": "\n".join(body), "labels": ["feedback", category]},
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=_GITHUB_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json().get("html_url")
    except Exception as exc:
        logger.warning("Feedback → GitHub issue failed (repo=%s, %s): %s", repo, category, exc)
        return None


def record_feedback(
    *,
    category: str,
    message: str,
    headers: Mapping[str, str],
    url: str | None = None,
    view: str | None = None,
    banco: str | None = None,
    app_version: str | None = None,
    browser_info: str | None = None,
    settings: Settings | None = None,
    client: bigquery.Client | None = None,
) -> dict:
    """Append one feedback report and best-effort open a GitHub issue.

    ``headers`` is the inbound request's headers; the author email is read from the
    IAP-verified header (never the service account). Raises :class:`FeedbackValidationError`
    (→ 400) on an empty/over-length message or bad category, and ``PermissionError`` /
    ``InvalidIapAssertionError`` (→ 401/403) when no trustworthy identity is present.
    Returns the row as written (including the GitHub ``issue_url`` when forwarded).
    """
    category = (category or "bug").strip().lower()
    message = _validate(category, message)
    cfg = settings or get_settings()
    url = _clip(url, MAX_URL_LEN)
    view_id = _clip(view, MAX_VIEW_LEN)
    banco = _clip(banco, MAX_BANCO_LEN)
    app_version = _clip(app_version, MAX_VERSION_LEN)
    browser_info = _clip(browser_info, MAX_UA_LEN)

    # Identity first — a missing/forged author raises here, before any write.
    submitted_by = author_email_from_headers(
        headers, dev_fallback=cfg.curation_dev_author, audience=cfg.iap_audience
    )
    feedback_id = uuid.uuid4().hex
    bq = client or resolve_bq_client(cfg)
    table_fqn = sqlbuild.table_ref(cfg, "bq_research_inputs_dataset", cfg.bq_feedback_log_table)
    ensure_feedback_log_table(cfg, bq)

    issue_url = _forward_to_github(
        cfg,
        category=category,
        message=message,
        submitted_by=submitted_by,
        url=url,
        view_id=view_id,
        banco=banco,
    )

    sql = f"""
        insert into `{table_fqn}`
            (feedback_id, category, message, url, view_id, banco, app_version,
             browser_info, submitted_by, submitted_at, issue_url)
        values
            (@feedback_id, @category, @message, @url, @view_id, @banco, @app_version,
             @browser_info, @submitted_by, current_timestamp(), @issue_url)
    """
    params = [
        bigquery.ScalarQueryParameter("feedback_id", "STRING", feedback_id),
        bigquery.ScalarQueryParameter("category", "STRING", category),
        bigquery.ScalarQueryParameter("message", "STRING", message),
        bigquery.ScalarQueryParameter("url", "STRING", url),
        bigquery.ScalarQueryParameter("view_id", "STRING", view_id),
        bigquery.ScalarQueryParameter("banco", "STRING", banco),
        bigquery.ScalarQueryParameter("app_version", "STRING", app_version),
        bigquery.ScalarQueryParameter("browser_info", "STRING", browser_info),
        bigquery.ScalarQueryParameter("submitted_by", "STRING", submitted_by),
        bigquery.ScalarQueryParameter("issue_url", "STRING", issue_url),
    ]
    bq.query(sql, job_config=bigquery.QueryJobConfig(query_parameters=params)).result()
    logger.info(
        "feedback (%s) by %s%s", category, submitted_by, f" → {issue_url}" if issue_url else ""
    )
    return {
        "feedback_id": feedback_id,
        "category": category,
        "message": message,
        "url": url,
        "view": view_id,
        "banco": banco,
        "submitted_by": submitted_by,
        "issue_url": issue_url,
    }
