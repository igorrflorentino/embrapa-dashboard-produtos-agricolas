"""Dash application factory.

Exposes the Flask WSGI app as ``server`` so Gunicorn / Cloud Run can target
``embrapa_commodities.dashboard.app:server``.

The first request lazily instantiates a singleton `GoldStore`, which in turn
issues one `SELECT * FROM gold_commodity_matrix` against BigQuery. Subsequent
requests are served from the in-memory pandas snapshot.

Error handling:
- Any exception during layout rendering or in a page callback writes a
  structured payload to the `global-error` `dcc.Store`.
- A separate callback paints a full-screen overlay over the dashboard when
  that store has a value, blocking interaction until the user reloads.
"""

from __future__ import annotations

import logging
import os
import threading
import traceback

from dash import Dash, Input, Output, dcc, html, no_update
from flask import jsonify

from embrapa_commodities.dashboard.components.shell import shell
from embrapa_commodities.dashboard.config import get_settings
from embrapa_commodities.dashboard.data import GoldStore
from embrapa_commodities.dashboard.pages import geography, overview, product
from embrapa_commodities.dashboard.theme import install_template

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

PAGE_MODULES = {
    "/": overview,
    "/produto": product,
    "/geografia": geography,
}

PAGE_LABELS = {
    "/": "Visão geral",
    "/produto": "Produto",
    "/geografia": "Geografia",
}


def build_error_payload(
    exc: BaseException,
    *,
    page: str,
    where: str,
) -> dict[str, str]:
    """Structured error payload written to the global-error `dcc.Store`."""
    return {
        "page": PAGE_LABELS.get(page, page),
        "where": where,
        "type": type(exc).__name__,
        "message": str(exc) or "(sem mensagem)",
        "cause": _infer_cause(exc),
        "traceback": traceback.format_exc(limit=20),
    }


def _infer_cause(exc: BaseException) -> str:
    """Heuristic to translate common errors into operator-friendly causes."""
    name = type(exc).__name__
    msg = str(exc).lower()
    module = type(exc).__module__

    if "notfound" in name.lower() or "404" in msg:
        if "location" in msg:
            return (
                "Dataset não encontrado nessa location do BigQuery. "
                "Verifique se BQ_LOCATION corresponde à região onde o "
                "dataset gold realmente está."
            )
        return (
            "Tabela ou dataset não encontrado. Verifique BQ_GOLD_DATASET "
            "e se o pipeline dbt já materializou gold_commodity_matrix."
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
    """Construct the Dash app, install theme, register all callbacks lazily."""
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
            # global error store + always-mounted overlay
            dcc.Store(id="global-error", data=None, storage_type="memory"),
            html.Div(id="error-overlay", className="error-overlay hidden"),
            # the dashboard itself
            html.Div(id="page-container"),
        ]
    )

    store_holder: dict[str, GoldStore] = {}
    store_lock = threading.Lock()
    callbacks_registered = {"flag": False}

    def _store() -> GoldStore:
        if "store" not in store_holder:
            with store_lock:
                if "store" not in store_holder:
                    ingestion, dashboard = get_settings()
                    store_holder["store"] = GoldStore(ingestion, dashboard)
        return store_holder["store"]

    def _register_all_callbacks_once():
        if callbacks_registered["flag"]:
            return
        store = _store()
        for module in (overview, product, geography):
            module.register_callbacks(dash_app, store)
        callbacks_registered["flag"] = True

    @dash_app.callback(
        Output("page-container", "children"),
        Output("global-error", "data"),
        Input("url", "pathname"),
    )
    def _route(pathname):
        path = pathname or "/"
        module = PAGE_MODULES.get(path)
        if module is None:
            return shell(_not_found(path), pathname=path), None
        try:
            _register_all_callbacks_once()
        except Exception as exc:
            logger.exception("Failed to register callbacks")
            return no_update, build_error_payload(
                exc, page=path, where="inicialização das callbacks"
            )
        try:
            content = module.layout(_store())
            return shell(content, pathname=path), None
        except Exception as exc:
            logger.exception("Failed to render layout for %s", path)
            return no_update, build_error_payload(
                exc, page=path, where=f"layout da página {PAGE_LABELS.get(path, path)}"
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
            dcc.Link("Voltar à visão geral", href="/", className="link"),
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
