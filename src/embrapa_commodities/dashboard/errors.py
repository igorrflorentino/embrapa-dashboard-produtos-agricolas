"""Dashboard error handling — cause inference, payload construction, and UI overlay.

Extracted from ``app.py`` during the 2026-05 audit to reduce that module's
cyclomatic complexity.  ``build_error_payload`` is the public API; page
callbacks import it to wrap exceptions into the ``global-error`` ``dcc.Store``.
"""

from __future__ import annotations

import traceback
from typing import TYPE_CHECKING

from dash import dcc, html

if TYPE_CHECKING:
    pass

# ── Cause-inference heuristic ────────────────────────────────────────────

# Data-driven pattern list, same style as monitor._DIAGNOSIS_PATTERNS.
# Each entry: (checker, message).  *checker* receives (exc_name_lower,
# msg_lower, module) and returns True if the pattern matches.
_CAUSE_PATTERNS: list[tuple[str, str]] = [
    (
        "notfound_or_404",
        "Tabela, dataset ou location não encontrada no BigQuery. "
        "Verifique BQ_GOLD_DATASET (nome do dataset) e BQ_LOCATION "
        "(deve corresponder à região onde o dataset realmente está).",
    ),
    (
        "forbidden_or_403",
        "A service account não tem permissão para ler o BigQuery. "
        "Verifique as IAM bindings (bigquery.dataViewer + bigquery.jobUser).",
    ),
    (
        "badrequest_or_400",
        "O BigQuery rejeitou a query. Pode ser inconsistência de "
        "schema entre o que o dashboard espera e o que o dbt produziu.",
    ),
    (
        "key_or_attribute_error",
        "Coluna ou propriedade esperada não existe no DataFrame. "
        "O schema do Gold pode ter mudado sem o código acompanhar.",
    ),
    (
        "google_api_error",
        "Falha de comunicação ou autenticação com o BigQuery. "
        "Verifique credenciais (ADC localmente ou SA no Cloud Run).",
    ),
    (
        "network_error",
        "Falha de rede ao contatar o BigQuery.",
    ),
]

_FALLBACK_CAUSE = (
    "Causa não identificada automaticamente. Verifique os logs do "
    "Cloud Run para o traceback completo."
)


def _check_cause(exc: BaseException, pattern_id: str) -> bool:
    """Return True if *exc* matches the named pattern."""
    name = type(exc).__name__.lower()
    msg = str(exc).lower()
    module = type(exc).__module__

    if pattern_id == "notfound_or_404":
        return "notfound" in name or "404" in msg
    if pattern_id == "forbidden_or_403":
        return "forbidden" in name or "permission" in msg or "403" in msg
    if pattern_id == "badrequest_or_400":
        return "badrequest" in name or "400" in msg
    if pattern_id == "key_or_attribute_error":
        return type(exc).__name__ in {"KeyError", "AttributeError"}
    if pattern_id == "google_api_error":
        return "google.api_core" in module or "google.auth" in module
    if pattern_id == "network_error":
        return isinstance(exc, ConnectionError | TimeoutError)
    return False  # pragma: no cover


def infer_cause(exc: BaseException) -> str:
    """Heuristic to translate common errors into operator-friendly causes."""
    for pattern_id, message in _CAUSE_PATTERNS:
        if _check_cause(exc, pattern_id):
            return message
    return _FALLBACK_CAUSE


# ── Payload builder ──────────────────────────────────────────────────────


def build_error_payload(
    exc: BaseException,
    *,
    page: str,
    where: str,
    page_label_fn=None,
    health_recorder=None,
) -> dict[str, str]:
    """Structured error payload written to the global-error ``dcc.Store``.

    Also tees a copy into the health registry so it shows up on /status.
    ``page`` is a URL path; the label is resolved from the registry when
    possible, falling back to the raw path.

    Parameters
    ----------
    page_label_fn:
        Callable(path) → str.  Passed by ``app.py`` so this module doesn't
        need to import the source registry (avoids circular imports).
    health_recorder:
        Callable(payload) that records the error into the health store.
    """
    label = page_label_fn(page) if page_label_fn else page
    payload = {
        "page": label,
        "where": where,
        "type": type(exc).__name__,
        "message": str(exc) or "(sem mensagem)",
        "cause": infer_cause(exc),
        "traceback": traceback.format_exc(limit=20),
    }
    if health_recorder:
        health_recorder(payload)
    return payload


# ── Error overlay UI ─────────────────────────────────────────────────────


def build_error_screen(err: dict[str, str]) -> html.Div:
    """Full-screen blocking error overlay."""
    return html.Div(
        className="error-card",
        children=[
            html.Div(
                className="error-head",
                children=[
                    html.Span("!", className="error-bang"),
                    html.Div(
                        children=[
                            html.Div("Erro no dashboard", className="error-title"),
                            html.Div(
                                "O carregamento foi interrompido. O painel está congelado "
                                "para evitar exibir dados parciais ou incorretos.",
                                className="error-sub",
                            ),
                        ]
                    ),
                ],
            ),
            html.Div(
                className="error-grid",
                children=[
                    _error_row("Página", err.get("page", "—")),
                    _error_row("Onde", err.get("where", "—")),
                    _error_row("Tipo", err.get("type", "—")),
                    _error_row("Mensagem", err.get("message", "—"), mono=True),
                    _error_row("Causa provável", err.get("cause", "—")),
                ],
            ),
            html.Details(
                className="error-trace",
                children=[
                    html.Summary("Traceback completo"),
                    html.Pre(err.get("traceback", "")),
                ],
            ),
            html.Div(
                className="error-actions",
                children=html.Button(
                    "Recarregar página",
                    id="error-reload-btn",
                    n_clicks=0,
                    className="btn-primary",
                ),
            ),
        ],
    )


def _error_row(label: str, value: str, *, mono: bool = False) -> html.Div:
    return html.Div(
        className="error-row",
        children=[
            html.Div(label, className="error-row-label"),
            html.Div(
                value,
                className="error-row-value" + (" mono" if mono else ""),
            ),
        ],
    )
