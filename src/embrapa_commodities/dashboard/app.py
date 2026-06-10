"""The Dash application: layout skeleton, routing, and state callbacks.

State lives in three ``dcc.Store``s (``ui`` / ``nav`` / ``overlay``); a single
updater callback patches them from clicks (dispatched via ``dash.ctx``), and
renderer callbacks rebuild the chrome and the routed screen. Routing mirrors the
prototype's ``MainScreen`` precedence: info page → cross-source → banco "Em breve"
→ "Não se aplica" → perspective "Em breve" → the real view.
"""

from __future__ import annotations

import contextlib

from dash import ALL, Dash, Input, Output, State, ctx, dcc, html, no_update

from embrapa_commodities.config import get_settings
from embrapa_commodities.serving.cache import init_cache

from . import format as fmt
from . import seam
from .components import shell
from .components.cards import maturity_banner, meta_group, page_hero
from .registries import banco_by_id, bancos_supporting, view_applies_to, view_by_id
from .views import (
    concentration,
    cross_analytics,
    cross_source,
    curation,
    flows,
    geography,
    glossary,
    overview,
    partners,
    placeholders,
    product_compare,
    product_profile,
    quality,
    seasonality,
    value_volume,
)

VIEW_LAYOUTS = {
    "overview": overview.layout,
    "value": value_volume.layout,
    "geo": geography.layout,
    "quality": quality.layout,
    "product_profile": product_profile.layout,
    "product_compare": product_compare.layout,
    "concentration": concentration.layout,
    "glossary": glossary.layout,
    "flows_territorial": flows.layout,
    "flows_partners": partners.layout,
    "seasonality": seasonality.layout,
}

# Cross-source (Multi-fonte) analytical views — take the whole ui (they read
# ui['cross_product'] / ui['cross']), not the per-banco (banco, conv, summary).
CROSS_ANALYTICS = {
    "cross_export_coef": cross_analytics.export_coef,
    "cross_market_share": cross_analytics.market_share,
    "cross_price_spread": cross_analytics.price_spread,
    "cross_mirror": cross_analytics.mirror,
    "curated_value_added": curation.value_added,
    "curated_market_nature": curation.market_nature,
}

INITIAL_UI = {
    "mode": "single",
    "banco": "ibge_pevs",
    "view": "overview",
    "info": "about",
    "conv": dict(fmt.DEFAULT_CONVENTIONS),
    "summary": {},
    "cross": {
        "series": [{"b": "ibge_pevs", "m": "prod_value"}, {"b": "mdic_comex", "m": "exp_value"}],
        "mode": "base100",
    },
    "cross_product": None,
}

app = Dash(
    __name__,
    assets_folder="assets",
    suppress_callback_exceptions=True,
    title="Embrapa · Inteligência de Mercado · Commodities",
    update_title=None,
)
server = app.server

_CACHE_BOUND = False


def _ensure_cache() -> None:
    """Bind flask-caching to the Dash Flask server once (needs GCP settings)."""
    global _CACHE_BOUND
    if _CACHE_BOUND:
        return
    init_cache(server, get_settings())
    _CACHE_BOUND = True


# Bind at import when settings are available (run/Cloud Run); skip silently when
# not (lint/test without a .env) — querying needs settings anyway.
with contextlib.suppress(Exception):  # pragma: no cover - depends on environment
    _ensure_cache()


app.layout = html.Div(
    [
        dcc.Store(id="ui", data=INITIAL_UI),
        dcc.Store(id="nav", data={"open": False}),
        dcc.Store(id="overlay", data={"kind": None}),
        shell.topbar(),
        html.Div(
            [
                html.Aside(id="sidebar", className="sidebar"),
                html.Main(
                    [html.Div(id="conventions"), html.Div(id="filterbar"), html.Div(id="screen")],
                    className="content",
                ),
            ],
            className="body",
        ),
        shell.footer(),
        html.Div(id="overlay-root"),
    ],
    className="shell",
)


# ── State updater ────────────────────────────────────────────────────────────
@app.callback(
    Output("ui", "data"),
    Output("nav", "data"),
    Output("overlay", "data"),
    Input("mode-single", "n_clicks"),
    Input("mode-multi", "n_clicks"),
    Input("nav-trigger", "n_clicks"),
    Input("nav-scrim", "n_clicks"),
    Input("brand-home", "n_clicks"),
    Input("cite-open", "n_clicks"),
    Input("filter-open", "n_clicks"),
    Input("filter-close", "n_clicks"),
    Input("filter-close-x", "n_clicks"),
    Input("cite-close", "n_clicks"),
    Input("cite-close-x", "n_clicks"),
    Input("f-apply", "n_clicks"),
    Input("f-clear", "n_clicks"),
    Input({"type": "banco", "id": ALL}, "n_clicks"),
    Input({"type": "pick-banco", "id": ALL}, "n_clicks"),
    Input({"type": "view", "id": ALL}, "n_clicks"),
    Input({"type": "info", "id": ALL}, "n_clicks"),
    Input({"type": "conv", "group": ALL, "value": ALL}, "n_clicks"),
    State("ui", "data"),
    State("nav", "data"),
    State("overlay", "data"),
    State("f-products", "value"),
    State("f-years", "value"),
    prevent_initial_call=True,
)
def update_state(*args):
    ui, nav, _overlay = (dict(args[-5]), dict(args[-4]), dict(args[-3]))
    f_products, f_years = args[-2], args[-1]
    tid = ctx.triggered_id
    trig = ctx.triggered
    # Ignore component-creation fires (re-rendered nav/sidebar reset n_clicks to 0).
    if tid is None or not trig or not trig[0].get("value"):
        return no_update, no_update, no_update

    ui_d = nav_d = ov_d = no_update

    if isinstance(tid, dict):
        kind = tid.get("type")
        if kind in ("banco", "pick-banco"):
            ui["banco"] = tid["id"]
            ui["info"] = None
            ui["summary"] = {}  # product/year codes are banco-specific
            ui["conv"] = {**ui["conv"], "currency": banco_by_id(tid["id"]).base_currency}
            nav = {"open": False}
            ui_d, nav_d = ui, nav
        elif kind == "view":
            ui["view"] = tid["id"]
            ui["info"] = None
            nav = {"open": False}
            ui_d, nav_d = ui, nav
        elif kind == "info":
            ui["info"] = tid["id"]
            ui_d = ui
        elif kind == "conv":
            ui["conv"] = {**ui["conv"], tid["group"]: tid["value"]}
            ui_d = ui
        elif kind == "xmetric":  # toggle a (banco, metric) series in the cross picker
            cross = dict(ui.get("cross") or {"series": [], "mode": "base100"})
            series = [dict(s) for s in cross.get("series", [])]
            pair = (tid["banco"], tid["metric"])
            if pair in [(s["b"], s["m"]) for s in series]:
                if len(series) > 1:  # keep at least one series
                    series = [s for s in series if (s["b"], s["m"]) != pair]
            elif len(series) < 4:  # cap at four
                series.append({"b": pair[0], "m": pair[1]})
            cross["series"] = series
            ui["cross"] = cross
            ui_d = ui
        elif kind == "xmode":  # base100 / dual / panels
            cross = dict(ui.get("cross") or {"series": [], "mode": "base100"})
            cross["mode"] = tid["value"]
            ui["cross"] = cross
            ui_d = ui
        elif kind == "xproduct":  # commodity selection for the cross-analytics views
            ui["cross_product"] = None if tid["code"] == "__all__" else tid["code"]
            ui_d = ui
        elif kind == "cur-set":  # stage a per-code industrialization level (Curadoria)
            draft = dict(ui.get("cur_draft") or {})
            draft[f"{tid['source']}|{tid['code']}"] = tid["level"]
            ui["cur_draft"] = draft
            ui["cur_status"] = None
            ui_d = ui
    elif tid == "mode-single":
        ui.update(mode="single", view="overview", info=None)
        nav, ui_d, nav_d = {"open": False}, ui, {"open": False}
    elif tid == "mode-multi":
        ui.update(mode="multi", view="cross_source", info=None)
        nav, ui_d, nav_d = {"open": False}, ui, {"open": False}
    elif tid == "nav-trigger":
        nav_d = {"open": not nav.get("open")}
    elif tid == "nav-scrim":
        nav_d = {"open": False}
    elif tid == "brand-home":
        ui["info"] = "about"
        ui_d = ui
    elif tid == "cite-open":
        ov_d = {"kind": "cite"}
    elif tid == "filter-open":
        ov_d = {"kind": "filter"}
    elif tid in ("filter-close", "filter-close-x", "cite-close", "cite-close-x"):
        ov_d = {"kind": None}
    elif tid == "f-clear":
        ui["summary"] = {}
        ui_d = ui
    elif tid == "f-apply":
        summary = dict(ui.get("summary", {}))
        summary["basket"] = list(f_products) if f_products else None
        if f_years:
            summary["startDate"] = f"{int(f_years[0])}-01-01"
            summary["endDate"] = f"{int(f_years[1])}-12-31"
        ui["summary"] = summary
        ui_d, ov_d = ui, {"kind": None}
    elif tid == "cur-apply":  # commit staged curation edits to the append-only log
        draft = dict(ui.get("cur_draft") or {})
        ok = fail = 0
        for key, level in draft.items():
            source, _, code = key.partition("|")
            try:
                seam.record_code_level(source, code, level)
                ok += 1
            except Exception:
                fail += 1
        ui["cur_draft"] = {}
        ui["cur_status"] = (
            f"Aplicado — {ok} classificação(ões) registrada(s) no log."
            if not fail
            else f"{ok} registrada(s); {fail} falhou(aram). Confira a ativação (autor "
            "IAP/curation_dev_author + dim_code_industrialization_scd2 em prod)."
        )
        ui_d = ui
    elif tid == "cur-discard":
        ui["cur_draft"], ui["cur_status"] = {}, None
        ui_d = ui

    return ui_d, nav_d, ov_d


# ── Chrome renderer ──────────────────────────────────────────────────────────
@app.callback(
    Output("sidebar", "children"),
    Output("navmenu", "children"),
    Output("nav-trigger-label", "children"),
    Output("conventions", "children"),
    Output("filterbar", "children"),
    Input("ui", "data"),
    Input("nav", "data"),
)
def render_chrome(ui, nav):
    info = ui.get("info")
    view = ui.get("view")
    applies = view_applies_to(view, ui.get("banco"))[0]
    v = view_by_id(view)
    is_data_view = (
        not info
        and applies
        and v is not None
        and v.status == "live"
        and not v.cross_banco
        and view != "glossary"
    )
    conv = shell.conventions_strip(ui) if is_data_view else []
    fbar = shell.filter_trigger_bar(ui) if is_data_view else []
    return (
        shell.sidebar(ui),
        shell.navmenu(ui, nav.get("open", False)),
        shell.nav_trigger_label(ui),
        conv,
        fbar,
    )


# ── Overlay renderer (filter / citation modals) ──────────────────────────────
@app.callback(Output("overlay-root", "children"), Input("overlay", "data"), State("ui", "data"))
def render_overlay(overlay, ui):
    kind = (overlay or {}).get("kind")
    if kind == "filter":
        return shell.filter_modal(ui)
    if kind == "cite":
        return shell.cite_modal(ui)
    return []


# ── Screen router ────────────────────────────────────────────────────────────
@app.callback(Output("screen", "children"), Input("ui", "data"))
def render_screen(ui):
    info = ui.get("info")
    banco = banco_by_id(ui.get("banco"))
    conv = ui.get("conv", fmt.DEFAULT_CONVENTIONS)
    summary = ui.get("summary", {})

    if info:
        return _info_screen(info, banco, conv, summary, ui)

    view = ui.get("view")
    v = view_by_id(view)
    if v is None:
        return _screen(page_hero("Perspectiva", view, ""), [])

    if v.cross_banco:
        hero = page_hero("Análise cruzada · multi-fonte", v.label, v.desc, _cross_hero_meta(ui, v))
        if view == "cross_source" and v.status == "live":
            return _screen(hero, cross_source.layout(ui))
        if v.status == "live" and view in CROSS_ANALYTICS:
            return _screen(hero, CROSS_ANALYTICS[view](ui))
        return _screen(hero, [placeholders.perspective_soon(view)])

    applies, missing = view_applies_to(view, banco.id)
    hero = page_hero(
        f"Pesquisa histórica · {banco.short}",
        v.label,
        banco.sub,
        _data_hero_meta(banco) if banco.has_data else None,
    )

    if not banco.has_data:  # PAM / SEFAZ placeholders
        return _screen(hero, [placeholders.coming_soon(banco, view)])
    if not applies:
        return _screen(
            hero,
            [
                placeholders.not_applicable(
                    view, banco, _missing_label(missing), bancos_supporting(view)
                )
            ],
        )
    if v.status == "soon":  # built-later perspective on a live banco
        return _screen(hero, [placeholders.perspective_soon(view)])

    blocks = VIEW_LAYOUTS[view](banco.id, conv, summary)
    banner = maturity_banner(banco)
    return _screen(hero, blocks, banner=banner)


def _info_screen(info: str, banco, conv, summary, ui=None):
    if info == "about":
        return _screen(
            page_hero(
                "Informações",
                "Sobre o dashboard",
                "O que é o painel, quais bancos compõem a base e como os dados são processados.",
            ),
            [placeholders.about()],
        )
    if info == "health":
        return _screen(
            page_hero(
                "Informações",
                "Saúde do sistema",
                "Maturidade dos bancos e disponibilidade das tabelas Gold.",
            ),
            [placeholders.health()],
        )
    if info == "glossary":
        return _screen(
            page_hero(
                "Informações",
                "Glossário global",
                f"Termos, códigos e colunas — banco ativo: {banco.short}.",
            ),
            glossary.layout(banco.id, conv, summary),
        )
    if info == "curation":
        return _screen(
            page_hero(
                "Curadoria · conhecimento do pesquisador",
                "Enriquecimento dos dados",
                "Classifique cada código pelo nível de industrialização; a análise de "
                "valor agregado lê essa classificação curada ao vivo.",
            ),
            [curation.editor(ui or {})],
        )
    return _screen(page_hero("Informações", info, ""), [])


def _screen(hero, blocks, banner=None):
    children = [hero]
    if banner is not None:
        children.insert(0, banner)
    children.extend(blocks)
    return html.Div(children, className="screen")


def _cross_hero_meta(ui: dict, v) -> list:
    """Hero meta for a Multi-fonte perspective (fontes · séries · alinhamento)."""
    if v.id == "cross_source":
        series = (ui.get("cross") or {}).get("series") or []
        shorts = " · ".join(dict.fromkeys(banco_by_id(s["b"]).short for s in series)) or "—"
        rows = [
            ("Fontes", shorts),
            ("Séries", f"{len(series)} de 4"),
            ("Alinhamento", v.align or "eixo temporal (ano)"),
        ]
    else:
        shorts = " · ".join(banco_by_id(b).short for b in v.sources) or "—"
        rows = [("Fontes", shorts), ("Alinhamento", v.align or "eixo temporal (ano)")]
    return [meta_group("Cruzamento ativo", rows)]


def _data_hero_meta(banco) -> list:
    """Provenance + volume meta groups for the page hero, from gold_source_metadata."""
    try:
        m = seam.source_meta(banco.id)
    except Exception:
        m = {}
    if not m:
        return [
            meta_group(
                "Proveniência", [("Banco", banco.source), ("Tabela Gold", html.Code(banco.table))]
            )
        ]
    yr = f"{m.get('year_start', '')}–{m.get('year_end', '')}"
    prov = meta_group(
        "Proveniência",
        [
            (
                "Banco",
                html.Span([f"{banco.source} · ", html.Code(m.get("gold_table", banco.table))]),
            ),
            ("Cadência", str(m.get("cadence", "—"))),
            ("Cobertura", yr),
            ("Refresh Gold", str(m.get("last_refresh", "—"))[:19]),
        ],
    )
    vol = meta_group(
        "Volume",
        [
            ("Linhas", fmt.fmt_rows(float(m.get("total_rows", 0) or 0))),
            ("Produtos", str(m.get("products_total", "—"))),
            ("UFs", str(m.get("ufs_total", "—") or "—")),
        ],
    )
    return [prov, vol]


def _missing_label(missing) -> str:
    from .registries import missing_caps_label

    return missing_caps_label(missing)


def main() -> None:
    """Run the dashboard locally against the configured serving dataset."""
    _ensure_cache()
    app.run(host="127.0.0.1", port=8050, debug=False)


if __name__ == "__main__":
    main()
