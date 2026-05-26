"""Dash application factory.

Exposes the Flask WSGI app as ``server`` so Gunicorn / Cloud Run can target
``embrapa_commodities.dashboard.app:server``.

Architecture: the dashboard is **source-scoped**. The registry in
`data_sources.py` declares each upstream dataset and its views. URLs
look like ``/<source-id>/<view-id>`` — see the registry for the
canonical list. The only global page is ``/status``.

Error handling:
- Any exception during layout rendering or in a page callback writes a
  structured payload to the `global-error` `dcc.Store`.
- A separate callback paints a full-screen overlay over the dashboard when
  that store has a value, blocking interaction until the user reloads.
"""

from __future__ import annotations

import logging
import os
import traceback

from dash import Dash, Input, Output, dcc, html, no_update
from flask import jsonify

from embrapa_commodities.dashboard.components.shell import shell
from embrapa_commodities.dashboard.data_sources import (
    DEFAULT_SOURCE_ID,
    DataSource,
    build_registry,
)
from embrapa_commodities.dashboard.health import health
from embrapa_commodities.dashboard.pages import status as status_page
from embrapa_commodities.dashboard.theme import install_template

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ── Source registry — built at app startup ────────────────────────────────
DATA_SOURCES: dict[str, DataSource] = {}


def _default_source() -> DataSource:
    return DATA_SOURCES[DEFAULT_SOURCE_ID]


def _default_path() -> str:
    src = _default_source()
    return f"/{src.id}/{src.default_view().id}"


def _resolve(pathname: str) -> tuple[DataSource | None, object | None, str]:
    """Parse a request path into (source, view, canonical_path).

    Returns (None, None, path) for unknown or special-cased paths.
    """
    path = (pathname or "/").rstrip("/") or "/"
    if path == "/" or path == "":
        return None, None, "/"
    if path == "/status":
        return None, None, "/status"
    parts = path.strip("/").split("/")
    if not parts:
        return None, None, "/"
    source_id = parts[0]
    source = DATA_SOURCES.get(source_id)
    if source is None:
        return None, None, path
    if len(parts) == 1:
        # /<source> with no view → canonicalize to default view
        return source, source.default_view(), f"/{source.id}/{source.default_view().id}"
    view = source.find_view(parts[1])
    return source, view, path


def build_error_payload(
    exc: BaseException,
    *,
    page: str,
    where: str,
) -> dict[str, str]:
    """Structured error payload written to the global-error `dcc.Store`.

    Also tees a copy into the health registry so it shows up on /status.
    `page` is a URL path; the label is resolved from the registry when
    possible, falling back to the raw path.
    """
    payload = {
        "page": _page_label(page),
        "where": where,
        "type": type(exc).__name__,
        "message": str(exc) or "(sem mensagem)",
        "cause": _infer_cause(exc),
        "traceback": traceback.format_exc(limit=20),
    }
    health.record_error(payload)
    return payload


def _page_label(path: str) -> str:
    """Friendly label for an URL path, used in error overlays."""
    if path == "/status":
        return "Saúde do sistema"
    if path == "/":
        return "Início"
    src, view, _ = _resolve(path)
    if src is None:
        return path
    if view is None:
        return src.label
    return f"{src.label} · {view.label}"


def _infer_cause(exc: BaseException) -> str:
    """Heuristic to translate common errors into operator-friendly causes."""
    name = type(exc).__name__
    msg = str(exc).lower()
    module = type(exc).__module__

    if "notfound" in name.lower() or "404" in msg:
        return (
            "Tabela, dataset ou location não encontrada no BigQuery. "
            "Verifique BQ_GOLD_DATASET (nome do dataset) e BQ_LOCATION "
            "(deve corresponder à região onde o dataset realmente está)."
        )
    if "forbidden" in name.lower() or "permission" in msg or "403" in msg:
        return (
            "A service account não tem permissão para ler o BigQuery. "
            "Verifique as IAM bindings (bigquery.dataViewer + bigquery.jobUser)."
        )
    if "badrequest" in name.lower() or "400" in msg:
        return (
            "O BigQuery rejeitou a query. Pode ser inconsistência de "
            "schema entre o que o dashboard espera e o que o dbt produziu."
        )
    if name in {"KeyError", "AttributeError"}:
        return (
            "Coluna ou propriedade esperada não existe no DataFrame. "
            "O schema do Gold pode ter mudado sem o código acompanhar."
        )
    if "google.api_core" in module or "google.auth" in module:
        return (
            "Falha de comunicação ou autenticação com o BigQuery. "
            "Verifique credenciais (ADC localmente ou SA no Cloud Run)."
        )
    if isinstance(exc, ConnectionError | TimeoutError):
        return "Falha de rede ao contatar o BigQuery."
    return (
        "Causa não identificada automaticamente. Verifique os logs do "
        "Cloud Run para o traceback completo."
    )


def _build_dash() -> Dash:
    """Construct the Dash app, install theme, register all callbacks at startup."""
    # If we're executing this code, the container has booted and Python is up.
    health.stage_ok(
        "container",
        detail=f"Revision {os.environ.get('K_REVISION', 'local')}",
    )
    health.stage_started("dash_app")
    install_template()
    dash_app = Dash(
        __name__,
        title="Embrapa · Inteligência de Mercado · Commodities",
        update_title=None,
        suppress_callback_exceptions=True,
        meta_tags=[
            {"name": "viewport", "content": "width=device-width, initial-scale=1"},
            {
                "name": "description",
                "content": (
                    "Dashboard público da Embrapa com dados da Pesquisa da Extração "
                    "Vegetal e da Silvicultura (IBGE PEVS), corrigidos por IPCA, "
                    "IGP-M e câmbio (BCB)."
                ),
            },
        ],
    )

    dash_app.layout = html.Div(
        children=[
            dcc.Location(id="url", refresh=False),
            # page-level loading indicators — toggled by 03-loading.js
            html.Div(className="page-loading-bar"),
            html.Div(className="page-loading-block"),
            # global error store + always-mounted overlay
            dcc.Store(id="global-error", data=None, storage_type="memory"),
            html.Div(id="error-overlay", className="error-overlay hidden"),
            # the dashboard itself
            html.Div(id="page-container"),
        ]
    )
    health.stage_ok("dash_app", detail="Layout root + Store + overlay")

    # ── Build the source registry and register every view's callbacks at
    # startup. This is critical: prior versions registered page callbacks
    # lazily inside the route callback, but by then the client had already
    # fetched /_dash-dependencies and didn't know to dispatch them. With
    # eager registration the JS always receives the full graph.
    health.stage_started("page_callbacks")
    try:
        DATA_SOURCES.update(build_registry())
        view_count = 0
        for source in DATA_SOURCES.values():
            for view in source.all_views():
                view.register_fn(dash_app, source.store)
                view_count += 1
        # The /status page is global (not source-scoped), so register it
        # separately. Its register_fn accepts an unused store arg for API
        # symmetry.
        status_page.register_callbacks(dash_app, None)
        health.stage_ok(
            "page_callbacks",
            detail=f"{len(DATA_SOURCES)} fonte(s), {view_count} view(s) + /status",
        )
    except Exception as exc:
        logger.exception("Failed to register page callbacks at startup")
        health.stage_error("page_callbacks", str(exc))
        raise

    @dash_app.callback(
        Output("page-container", "children"),
        Output("url", "pathname"),
        Output("global-error", "data"),
        Input("url", "pathname"),
    )
    def _route(pathname):
        path = (pathname or "/").rstrip("/") or "/"

        # Special-cased global routes.
        if path == "/":
            target = _default_path()
            # Redirect — pathname update will re-fire this callback.
            return no_update, target, None
        if path == "/status":
            try:
                content = status_page.layout(None)
                return shell(content, path=path, source=None, view=None), no_update, None
            except Exception as exc:
                logger.exception("Failed to render layout for /status")
                return (
                    no_update,
                    no_update,
                    build_error_payload(exc, page=path, where="layout da página Saúde do sistema"),
                )

        source, view, canonical_path = _resolve(path)
        if source is None:
            return shell(_not_found(path), path=path, source=None, view=None), no_update, None
        if view is None:
            # /<source>/<unknown-view>
            return (
                shell(_not_found(path), path=path, source=source, view=None),
                no_update,
                None,
            )
        if canonical_path != path:
            # /<source> with no view → redirect to default view URL.
            return no_update, canonical_path, None
        try:
            content = view.layout_fn(source.store)
            return shell(content, path=path, source=source, view=view), no_update, None
        except Exception as exc:
            logger.exception("Failed to render layout for %s", path)
            return (
                no_update,
                no_update,
                build_error_payload(
                    exc,
                    page=path,
                    where=f"layout da view {source.label} · {view.label}",
                ),
            )

    @dash_app.callback(
        Output("error-overlay", "children"),
        Output("error-overlay", "className"),
        Input("global-error", "data"),
    )
    def _render_error_overlay(err):
        if err is None:
            return [], "error-overlay hidden"
        return _build_error_screen(err), "error-overlay visible"

    # JS hook on the Recarregar button — does a hard reload.
    dash_app.clientside_callback(
        """
        function(n_clicks) {
            if (n_clicks) { window.location.reload(); }
            return window.dash_clientside.no_update;
        }
        """,
        Output("error-overlay", "data-reloaded", allow_duplicate=True),
        Input("error-reload-btn", "n_clicks"),
        prevent_initial_call=True,
    )

    _attach_healthcheck(dash_app)
    return dash_app


def _not_found(path: str) -> html.Div:
    return html.Div(
        className="empty-state",
        children=[
            html.Div(className="overline", children="404"),
            html.H3(f"Página não encontrada: {path}", className="section-title"),
            dcc.Link("Voltar ao início", href=_default_path(), className="link"),
        ],
    )


def _build_error_screen(err: dict[str, str]) -> html.Div:
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


def _attach_healthcheck(dash_app: Dash) -> None:
    # Google Frontend reserves /healthz, so we expose our healthcheck under
    # a path that GFE doesn't intercept.
    @dash_app.server.route("/_health")
    def _health():
        return jsonify(status="ok"), 200


# Module-level exports for Gunicorn (`-w 2 module:server`).
app = _build_dash()
server = app.server


def main() -> None:
    """Local dev entry point: `python -m embrapa_commodities.dashboard.app`."""
    port = int(os.environ.get("PORT", "8080"))
    debug = os.environ.get("DASH_DEBUG", "").lower() in {"1", "true", "yes"}
    app.run(host="0.0.0.0", port=port, debug=debug)


if __name__ == "__main__":
    main()
