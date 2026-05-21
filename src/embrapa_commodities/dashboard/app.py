"""Dash application factory.

Exposes the Flask WSGI app as ``server`` so Gunicorn / Cloud Run can target
``embrapa_commodities.dashboard.app:server``.

The first request lazily instantiates a singleton `GoldStore`, which in turn
issues one `SELECT * FROM gold_commodity_matrix` against BigQuery. Subsequent
requests are served from the in-memory pandas snapshot.
"""

from __future__ import annotations

import logging
import os
import threading

from dash import Dash, Input, Output, dcc, html
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
        Input("url", "pathname"),
    )
    def _route(pathname):
        path = pathname or "/"
        module = PAGE_MODULES.get(path)
        if module is None:
            return shell(_not_found(path), pathname=path)
        _register_all_callbacks_once()
        try:
            content = module.layout(_store())
        except Exception as exc:
            logger.exception("Failed to render %s", path)
            content = _error_state(exc)
        return shell(content, pathname=path)

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


def _error_state(exc: Exception) -> html.Div:
    return html.Div(
        className="card",
        children=[
            html.Div("Falha ao carregar a página", className="overline"),
            html.H3("Erro inesperado", className="section-title"),
            html.P(
                "Não foi possível carregar os dados do BigQuery. Verifique as "
                "credenciais, o nome do projeto e o acesso à tabela "
                "gold.gold_commodity_matrix.",
                className="page-sub",
            ),
            html.Pre(
                str(exc),
                style={
                    "background": "var(--bg-surface-2)",
                    "padding": "12px",
                    "borderRadius": "6px",
                    "fontSize": "12px",
                    "color": "var(--fg-2)",
                    "overflow": "auto",
                },
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
