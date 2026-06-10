"""Curadoria — the researcher curation editor + the curated analyses.

``editor`` is an info-screen (``info='curation'``): a worklist of Gold codes
LEFT-JOINed to the current industrialization classification, with per-row level
controls staged into ``ui['cur_draft']`` and committed by "Aplicar" (the seam
writes to the append-only SCD2 log). ``value_added`` is the real curated
analysis (COMEX exports split by the curated level). ``market_nature`` is a
walled placeholder: its regime×flow basis is summed away in Gold (see seam).

Interaction is click-based (level buttons, not a <select>) to fit the app's
n_clicks callback model. Reads degrade gracefully before the SCD2 view exists.
"""

from __future__ import annotations

# ruff: noqa: E501 — presentation module; long pt-BR UI copy strings are intentional.
from dash import html

from .. import format as fmt
from .. import seam
from ..charts import basic
from ..components.cards import card, kpi_card, section_header
from ..components.icons import icon
from ..theme import EMBRAPA_GREEN

LEVEL_LABEL = {"bruta": "Bruta", "processada": "Processada", "misturado": "Misturado"}
_SRC_SHORT = {"ibge_pevs": "IBGE", "mdic_comex": "MDIC", "un_comtrade": "Comtrade"}


def _draft_key(source: str, code: str) -> str:
    return f"{source}|{code}"


def _level_control(source: str, code: str, persisted: str | None, draft_level: str | None):
    """A compact per-row segmented control (Bruta/Processada/Misturado). Click-based
    so it stages through the same n_clicks path as the rest of the app."""
    effective = draft_level if draft_level is not None else persisted
    dirty = draft_level is not None and draft_level != persisted
    buttons = [
        html.Button(
            LEVEL_LABEL[lvl],
            className="seg-opt" + (" on" if effective == lvl else ""),
            id={"type": "cur-set", "source": source, "code": code, "level": lvl},
            n_clicks=0,
        )
        for lvl in seam.CUR_LEVELS
    ]
    return html.Div(buttons, className="seg cur-level-seg" + (" cur-dirty" if dirty else ""))


def _row(r: dict, draft: dict):
    code, source = r["code"], r["source"]
    draft_level = draft.get(_draft_key(source, code))
    effective = draft_level if draft_level is not None else r["level"]
    todo = not effective
    return html.Tr(
        [
            html.Td(html.Span(_SRC_SHORT.get(source, source), className="cur-src")),
            html.Td(code, className="tnum"),
            html.Td(
                [
                    r["name"],
                    html.Span("a classificar", className="cur-todo-pill") if todo else None,
                ]
            ),
            html.Td(_level_control(source, code, r["level"], draft_level)),
        ],
        className="cur-coderow" + (" cur-coderow-todo" if todo else ""),
    )


def editor(ui: dict) -> html.Div:
    """The curation worklist editor (info-screen)."""
    draft = ui.get("cur_draft") or {}
    status = ui.get("cur_status")
    wl = seam.curation_worklist()
    rows = wl["rows"]
    pending = sum(
        1
        for k, lvl in draft.items()
        if lvl != next((r["level"] for r in rows if _draft_key(r["source"], r["code"]) == k), None)
    )

    note = html.Div(
        [
            icon("info", size=16, color="#06617c"),
            html.Span(
                [
                    "Curadoria ",
                    html.Strong("institucional compartilhada"),
                    ": a classificação vale para todos os pesquisadores e alimenta a análise de "
                    "valor agregado. A worklist é um ",
                    html.Strong("LEFT JOIN"),
                    " entre os códigos da Gold e o log de classificação — códigos sem classificação "
                    "aparecem como ",
                    html.Strong("a classificar"),
                    ". As alterações só entram na base ao clicar em ",
                    html.Strong("Aplicar"),
                    ".",
                ]
            ),
        ],
        className="cur-note",
    )

    apply_bar = html.Div(
        [
            html.Span(
                status
                or (
                    f"{pending} alteração(ões) não aplicada(s) à base"
                    if pending
                    else "Curadoria em sincronia com a base"
                ),
                className="cur-apply-status",
            ),
            html.Div(
                [
                    html.Button(
                        "Descartar",
                        className="btn-secondary",
                        id="cur-discard",
                        n_clicks=0,
                        disabled=pending == 0,
                    ),
                    html.Button(
                        "Aplicar à base",
                        className="btn-primary",
                        id="cur-apply",
                        n_clicks=0,
                        disabled=pending == 0,
                    ),
                ],
                className="cur-apply-actions",
            ),
        ],
        className="cur-apply" + (" dirty" if pending else ""),
    )

    kpis = html.Div(
        [
            kpi_card("Códigos na worklist", str(wl["total"]), sub="Gold DISTINCT ⟕ log"),
            kpi_card("A classificar", str(wl["pending"]), sub="sem linha no log"),
            kpi_card("Bruta", str(wl["by_level"]["bruta"]), sub="códigos classificados"),
            kpi_card("Processada", str(wl["by_level"]["processada"]), sub="códigos classificados"),
        ],
        className="kpi-row",
    )

    # Group the worklist by commodity (crosswalk), unmapped codes last.
    groups: dict = {}
    for r in rows:
        key = r["commodity_name"] or "Não mapeadas ao crosswalk"
        groups.setdefault(key, []).append(r)
    body = []
    for gname in sorted(groups, key=lambda g: (g == "Não mapeadas ao crosswalk", g)):
        body.append(html.Tr(html.Td(gname, colSpan=4), className="cur-grouprow"))
        body.extend(_row(r, draft) for r in groups[gname])

    table = card(
        [
            section_header(
                "Códigos entre fontes · nível de industrialização",
                "Classifique cada código como bruto ou processado",
            ),
            html.Div(
                html.Table(
                    [
                        html.Thead(
                            html.Tr(
                                [
                                    html.Th("Fonte"),
                                    html.Th("Código"),
                                    html.Th("Descrição"),
                                    html.Th("Nível de industrialização"),
                                ]
                            )
                        ),
                        html.Tbody(body),
                    ],
                    className="pc-table cur-table",
                ),
                className="pc-table-wrap",
            ),
        ]
    )

    # The handoff's second curation axis (regime × flow → finalidade) is walled:
    # both trade Golds sum the customs-procedure dimension away in Silver.
    walled = card(
        [
            section_header(
                "Aduana & finalidade econômica",
                "Indisponível nesta base",
                action=html.Span("regime × fluxo", className="caption"),
            ),
            html.Div(
                [
                    icon("info", size=14, color="#06617c"),
                    html.Span(
                        "A classificação por finalidade (consumo × processamento) depende do par "
                        "regime aduaneiro × fluxo (o customs procedure code do Comtrade). Esse eixo é "
                        "somado/colapsado na camada Silver→Gold das duas fontes de comércio, então não "
                        "há lastro real para curá-lo aqui — exigiria re-arquitetar a ingestão para "
                        "preservar a dimensão alfandegária. Por isso só o eixo de industrialização "
                        "(acima) está ativo.",
                    ),
                ],
                className="cs-note",
            ),
        ]
    )
    return html.Div([note, apply_bar, kpis, table, walled], className="cs-stack")


def value_added(ui: dict) -> list:
    """Curated analysis: COMEX exports split by the curated industrialization level."""
    data = seam.value_added()
    series = data["series"]
    if not series:
        return [
            card(
                [
                    section_header("Valor agregado · bruta vs processada", "Aguardando curadoria"),
                    html.P(
                        [
                            "Nenhum código de exportação (MDIC) foi classificado ainda como ",
                            html.Strong("bruta"),
                            " ou ",
                            html.Strong("processada"),
                            ". Classifique os códigos em ",
                            html.Strong("Curadoria"),
                            " — esta análise separa a exportação por nível de industrialização a partir "
                            "dessa classificação curada.",
                        ],
                        className="caption",
                        style={"padding": "16px 4px"},
                    ),
                ],
                subtle=True,
            )
        ]
    last = series[-1]
    kpis = html.Div(
        [
            kpi_card(
                "Participação processada",
                fmt.fmt_num(last["procShare"], decimals=1) + "%",
                sub=f"{last['y']} · da exportação",
            ),
            kpi_card(
                "Prêmio processada/bruta",
                "×" + fmt.fmt_num(last["premium"], decimals=1) if last["premium"] else "—",
                sub="preço processada ÷ bruta",
            ),
            kpi_card(
                "Exportação processada",
                fmt.fmt_money(last["procV"] * 1e9, "US$"),
                sub=f"{last['y']}",
            ),
            kpi_card("Códigos considerados", str(data["n_codes"]), sub="classificados (MDIC)"),
        ],
        className="kpi-row",
    )
    line = basic.multi_line(
        [
            {
                "name": "Processada",
                "color": EMBRAPA_GREEN,
                "xs": [d["y"] for d in series],
                "ys": [d["procV"] for d in series],
            },
            {
                "name": "Bruta",
                "color": "#B7791F",
                "xs": [d["y"] for d in series],
                "ys": [d["brutaV"] for d in series],
            },
        ],
        label="US$ bi",
        height=320,
    )
    share = basic.line_area(
        [d["y"] for d in series],
        [d["procShare"] for d in series],
        label="% processada",
        color=EMBRAPA_GREEN,
    )
    return [
        kpis,
        card(
            [
                section_header(
                    "Exportação por nível de industrialização",
                    "Bruta vs processada · da classificação curada",
                    action=html.Span("US$ bi · MDIC", className="caption"),
                ),
                line,
            ]
        ),
        card(
            [
                section_header(
                    "Participação da processada no tempo", "Quanto da exportação é industrializado"
                ),
                share,
            ]
        ),
    ]


def market_nature(ui: dict) -> list:
    """Walled placeholder — the regime×flow basis is summed away in Gold."""
    return [
        card(
            [
                section_header(
                    "Finalidade econômica",
                    "Indisponível nesta base",
                    action=html.Span("consumo × processamento", className="caption"),
                ),
                html.Div(
                    [
                        icon("info", size=14, color="#06617c"),
                        html.Span(
                            "Esta análise separaria o comércio por finalidade econômica (consumo × "
                            "processamento), classificada pelo par regime aduaneiro × fluxo. Esse par é "
                            "o customs procedure code do Comtrade, que a camada Silver→Gold soma/colapsa "
                            "em ambas as fontes de comércio — não há dado real por regime para alimentar "
                            "a análise. Habilitá-la exigiria preservar a dimensão alfandegária na "
                            "ingestão (mudança de pipeline, não de curadoria).",
                        ),
                    ],
                    className="cs-note",
                ),
            ]
        )
    ]
