"""/ — Visão geral.

KPIs (with sparklines), highlights derived from the data, a time-series
chart, product mix donut, top-states bar, and the monetary-convention card.
"""

from __future__ import annotations

from dash import Input, Output, State, dcc, html, no_update

from embrapa_commodities.dashboard.components.charts import (
    bar_top_states,
    donut_product_mix,
    line_time_series,
)
from embrapa_commodities.dashboard.components.export import (
    download_payload,
    export_button,
)
from embrapa_commodities.dashboard.components.filter_bar import filter_bar
from embrapa_commodities.dashboard.components.kpi import kpi_card
from embrapa_commodities.dashboard.components.monetary_legend import monetary_legend
from embrapa_commodities.dashboard.components.section_header import section_header
from embrapa_commodities.dashboard.data import GoldRepository
from embrapa_commodities.dashboard.formatting import (
    convention_label,
    fmt_currency,
    fmt_datetime,
    fmt_delta,
    fmt_number,
    period_to_years,
)

PREFIX = "overview"


def _hero(store: GoldRepository) -> html.Div:
    last_refresh = store.last_refresh()
    last_refresh_str = fmt_datetime(last_refresh) if last_refresh else "—"
    loaded_str = fmt_datetime(store.loaded_at())
    lo, hi = store.year_range()

    return html.Div(
        className="page-hero",
        children=[
            html.Div(
                children=[
                    html.Div(
                        "Dashboard de Inteligência de Mercado · Commodities",
                        className="overline",
                    ),
                    html.H1(
                        "Visão geral · Produção extrativa vegetal",
                        className="page-title",
                    ),
                    html.P(
                        children=[
                            "Pipeline Bronze → Silver → Gold sobre IBGE PEVS, com "
                            "correção monetária por IPCA, IGP-M e câmbio do ano. "
                            "Cobertura: ",
                            html.Strong(f"{lo}–{hi}"),
                            ", baseada na Pesquisa da Extração Vegetal e da Silvicultura.",
                        ],
                        className="page-sub",
                    ),
                ]
            ),
            html.Div(
                className="hero-meta",
                children=[
                    _meta_row("Convenção ativa", "IPCA · BRL"),
                    _meta_row("Última carga do Gold", last_refresh_str),
                    _meta_row("Snapshot carregado em", loaded_str),
                    html.Div(
                        style={"display": "flex", "gap": "8px", "marginTop": "8px"},
                        children=export_button(
                            button_id={"section": PREFIX, "control": "export"},
                            download_id={"section": PREFIX, "control": "download"},
                        ),
                    ),
                ],
            ),
        ],
    )


def _meta_row(label: str, value: str) -> html.Div:
    return html.Div(
        className="meta-row",
        children=[
            html.Span(label, className="meta-label"),
            html.Span(value, className="meta-val tnum"),
        ],
    )


def _highlights(store: GoldRepository, conv: str, ccy: str) -> html.Div:
    """Three institutional 'destaques' derived directly from the data."""
    lo, hi = store.year_range()
    cards: list = []

    # 1) Leading state in the latest year.
    top = store.top_states(year=hi, convention=conv, currency=ccy, n=1)
    if not top.empty:
        row = top.iloc[0]
        cards.append(
            _highlight(
                overline="Líder nacional",
                badge=str(row["state_acronym"]),
                badge_tone="info",
                title=f"{row['state_name']} concentra o maior valor real em {hi}",
                body=f"Total estimado de {fmt_currency(float(row['value']), ccy)} em "
                f"{convention_label(conv)} · {ccy}.",
            )
        )

    # 2) Biggest YoY mover by ABSOLUTE change. Ranking by % swing surfaces
    # microscopic baselines (e.g. a UF that went from R$ 300k to R$ 16 mi
    # produces a +4000% headline that misleads more than it informs). We
    # rank by absolute delta and quote the percentage as secondary context.
    if hi > lo:
        cur = store.top_states(year=hi, convention=conv, currency=ccy, n=27)
        prev = store.top_states(year=hi - 1, convention=conv, currency=ccy, n=27)
        merged = cur.merge(prev, on=["state_acronym", "state_name"], suffixes=("", "_prev"))
        merged = merged[(merged["value_prev"] > 0) & (merged["value"] > 0)]
        if not merged.empty:
            merged["delta_abs"] = merged["value"] - merged["value_prev"]
            merged["delta_pct"] = merged["delta_abs"] / merged["value_prev"] * 100.0
            mover = merged.loc[merged["delta_abs"].abs().idxmax()]
            tone = "ok" if mover["delta_abs"] >= 0 else "err"
            cards.append(
                _highlight(
                    overline=f"Maior variação · {hi - 1} → {hi}",
                    badge=fmt_currency(float(mover["delta_abs"]), ccy),
                    badge_tone=tone,
                    title=f"{mover['state_name']} ({mover['state_acronym']}) lidera a variação",
                    body=f"De {fmt_currency(float(mover['value_prev']), ccy)} para "
                    f"{fmt_currency(float(mover['value']), ccy)} "
                    f"({fmt_delta(float(mover['delta_pct']))}) "
                    f"em {convention_label(conv)} · {ccy}.",
                )
            )

    # 3) Data-quality summary.
    q = store.quality_summary()
    cards.append(
        _highlight(
            overline="Qualidade dos dados",
            badge=f"{q['pct_ok']:.1f}%".replace(".", ","),
            badge_tone="ok",
            title="Linhas marcadas como OK no Gold",
            body=f"De {fmt_number(q['rows_total'])} linhas totais, "
            f"{fmt_number(q['rows_ok'])} têm quantidade e valor consistentes. "
            f"{fmt_number(q['rows_missing_value'])} sem valor monetário.",
        )
    )

    return html.Div(
        className="highlights",
        children=[
            section_header(
                overline=f"Destaques · {hi}",
                title="O que se observa no último ciclo",
            ),
            html.Div(className="highlights-grid", children=cards),
        ],
    )


def _highlight(*, overline: str, title: str, body: str, badge: str, badge_tone: str) -> html.Div:
    classes = {"err": "highlight warn", "info": "highlight info"}
    cls = classes.get(badge_tone, "highlight")
    return html.Div(
        className=cls,
        children=[
            html.Div(
                className="highlight-head",
                children=[
                    html.Span(overline, className="overline"),
                    html.Span(badge, className=f"chip {badge_tone}"),
                ],
            ),
            html.Div(title, className="highlight-title"),
            html.Div(body, className="highlight-body"),
        ],
    )


def _yoy_deltas(series) -> tuple[float | None, float | None, object | None]:
    """Compute YoY deltas for value and quantity from a time series.

    Returns (delta_value_pct, delta_quantity_pct, prev_row).
    """
    if len(series) < 2:
        return None, None, None
    last = series.iloc[-1]
    prev = series.iloc[-2]
    delta_v = (last["value"] - prev["value"]) / prev["value"] * 100.0 if prev["value"] else None
    delta_q = (
        (last["quantity"] - prev["quantity"]) / prev["quantity"] * 100.0
        if prev["quantity"]
        else None
    )
    return delta_v, delta_q, prev


def _build_kpi_cards(
    *,
    store: GoldRepository,
    series,
    conv: str,
    ccy: str,
    states_value: str,
    states_sub: str,
    quality_value: str,
    quality_sub: str,
) -> list:
    """Build the four standard KPI cards (value, quantity, coverage, quality).

    Callers supply the pre-computed coverage and quality strings so the
    unfiltered path (``_kpi_strip``) can use ``store.coverage_summary()``
    while the filtered path can derive them from a scoped DataFrame.
    """
    last = series.iloc[-1]
    delta_v, delta_q, prev = _yoy_deltas(series)

    return [
        kpi_card(
            label=f"Valor ({convention_label(conv)}) · {ccy}",
            value=fmt_currency(float(last["value"]), ccy),
            delta=fmt_delta(delta_v) if delta_v is not None else None,
            delta_positive=(delta_v or 0) >= 0,
            sub=f"vs. {int(prev['reference_year'])}" if prev is not None else None,
            spark_values=series["value"].tail(12).tolist(),
            spark_color="#1D4D7E",
        ),
        kpi_card(
            label="Quantidade total",
            value=fmt_number(float(last["quantity"]), decimals=0),
            delta=fmt_delta(delta_q) if delta_q is not None else None,
            delta_positive=(delta_q or 0) >= 0,
            sub=f"unidades em {int(last['reference_year'])}",
            spark_values=series["quantity"].tail(12).tolist(),
            spark_color="#006f35",
        ),
        kpi_card(
            label="Cobertura geográfica",
            value=states_value,
            sub=states_sub,
            spark_values=_coverage_spark(store, conv, ccy),
            spark_color="#3A74B0",
        ),
        kpi_card(
            label="Qualidade dos dados",
            value=quality_value,
            sub=quality_sub,
            spark_values=_quality_spark(store),
            spark_color="#006f35",
        ),
    ]


def _kpi_strip(store: GoldRepository, conv: str, ccy: str) -> html.Div:
    _, hi = store.year_range()
    series = store.time_series(convention=conv, currency=ccy)
    if series.empty:
        return html.Div(className="kpi-row", children=[])

    cov = store.coverage_summary(year=int(hi))
    q = store.quality_summary()
    states_total = store.df()["state_acronym"].nunique()

    cards = _build_kpi_cards(
        store=store,
        series=series,
        conv=conv,
        ccy=ccy,
        states_value=f"{cov['states']} / {states_total}",
        states_sub=f"UFs com dados · {int(hi)}",
        quality_value=f"{q['pct_ok']:.1f}%".replace(".", ","),
        quality_sub=f"linhas com flag OK · {fmt_number(q['rows_total'])} no total",
    )
    return html.Div(className="kpi-row", children=cards)


def _coverage_spark(store: GoldRepository, conv: str, ccy: str) -> list[float]:
    df = store.df()
    if df.empty:
        return []
    coverage = df.groupby("reference_year")["state_acronym"].nunique().tail(12)
    return coverage.astype(float).tolist()


def _quality_spark(store: GoldRepository) -> list[float]:
    df = store.df()
    if df.empty:
        return []
    g = (
        df.groupby("reference_year")["data_quality_flag"]
        .apply(lambda s: (s == "OK").mean() * 100.0)
        .tail(12)
    )
    return g.astype(float).tolist()


def _spinner(child, *, name: str):
    """Wrap a chart/region in a Dash Loading so users get explicit feedback."""
    return dcc.Loading(
        children=child,
        type="circle",
        color="#006f35",
        parent_className=f"loading-wrap loading-{name}",
        delay_show=120,
    )


def layout(store: GoldRepository) -> html.Div:
    """Render the page. Filter callbacks are registered via `register_callbacks`."""
    return html.Div(
        className="screen",
        children=[
            _hero(store),
            filter_bar(PREFIX, store),
            _spinner(
                html.Div(
                    id={"section": PREFIX, "control": "kpi_strip"},
                    children=_kpi_strip(store, "ipca", "BRL"),
                ),
                name="kpi",
            ),
            _spinner(
                html.Div(
                    id={"section": PREFIX, "control": "highlights"},
                    children=_highlights(store, "ipca", "BRL"),
                ),
                name="highlights",
            ),
            html.Div(
                className="grid-2",
                children=[
                    html.Div(
                        className="card",
                        children=[
                            section_header(
                                overline="Série histórica · IPCA · BRL",
                                title="Valor real total ao longo do tempo",
                            ),
                            _spinner(
                                dcc.Graph(
                                    id={"section": PREFIX, "control": "time_series"},
                                    config={"displayModeBar": False},
                                    className="chart-box",
                                ),
                                name="ts",
                            ),
                        ],
                    ),
                    html.Div(
                        className="card",
                        children=[
                            section_header(
                                overline="Composição",
                                title="Participação por produto",
                            ),
                            _spinner(
                                dcc.Graph(
                                    id={"section": PREFIX, "control": "donut"},
                                    config={"displayModeBar": False},
                                    className="chart-box",
                                ),
                                name="donut",
                            ),
                        ],
                    ),
                ],
            ),
            html.Div(
                className="card",
                children=[
                    section_header(
                        overline="Top estados",
                        title="Maiores produtores no ano mais recente",
                        action=html.Span(
                            "Valor real (IPCA), na moeda selecionada",
                            className="caption",
                        ),
                    ),
                    _spinner(
                        dcc.Graph(
                            id={"section": PREFIX, "control": "top_states"},
                            config={"displayModeBar": False},
                            className="chart-box",
                        ),
                        name="topstates",
                    ),
                ],
            ),
            monetary_legend(),
        ],
    )


def register_callbacks(dash_app, store: GoldRepository) -> None:
    from embrapa_commodities.dashboard.app import build_error_payload

    @dash_app.callback(
        Output({"section": PREFIX, "control": "kpi_strip"}, "children"),
        Output({"section": PREFIX, "control": "highlights"}, "children"),
        Output({"section": PREFIX, "control": "time_series"}, "figure"),
        Output({"section": PREFIX, "control": "donut"}, "figure"),
        Output({"section": PREFIX, "control": "top_states"}, "figure"),
        Output("global-error", "data", allow_duplicate=True),
        Input({"section": PREFIX, "control": "period"}, "value"),
        Input({"section": PREFIX, "control": "product"}, "value"),
        Input({"section": PREFIX, "control": "uf"}, "value"),
        Input({"section": PREFIX, "control": "conv"}, "value"),
        Input({"section": PREFIX, "control": "ccy"}, "value"),
        Input({"section": PREFIX, "control": "only_ok"}, "value"),
        prevent_initial_call="initial_duplicate",
    )
    def _update(period, product, uf, conv, ccy, only_ok):
        try:
            conv = conv or "ipca"
            ccy = ccy or "BRL"
            years = period_to_years(store.year_range(), period)
            product_code = None if product in (None, "all") else product
            uf_code = None if uf in (None, "all") else uf
            only_ok_flag = bool(only_ok) and "ok" in (only_ok or [])

            ts = store.time_series(
                convention=conv,
                currency=ccy,
                years=years,
                product_code=product_code,
                state_acronym=uf_code,
            )
            value_label = f"Valor ({convention_label(conv)}, {ccy})"
            line = line_time_series(ts, value_label=value_label)

            hi = years[1] if years else store.year_range()[1]
            mix = store.product_mix(year=hi, convention=conv, currency=ccy, state_acronym=uf_code)
            donut = donut_product_mix(mix)

            top = store.top_states(
                year=hi, convention=conv, currency=ccy, product_code=product_code
            )
            bar = bar_top_states(top, value_label=value_label)

            kpis = _kpi_strip_filtered(store, conv, ccy, years, product_code, uf_code, only_ok_flag)
            highlights = _highlights(store, conv, ccy)
            return kpis, highlights, line, donut, bar, no_update
        except Exception as exc:
            err = build_error_payload(exc, page="/", where="callback de atualização (Visão geral)")
            return (no_update, no_update, no_update, no_update, no_update, err)

    @dash_app.callback(
        Output({"section": PREFIX, "control": "download"}, "data"),
        Input({"section": PREFIX, "control": "export"}, "n_clicks"),
        State({"section": PREFIX, "control": "period"}, "value"),
        State({"section": PREFIX, "control": "product"}, "value"),
        State({"section": PREFIX, "control": "uf"}, "value"),
        State({"section": PREFIX, "control": "only_ok"}, "value"),
        prevent_initial_call=True,
    )
    def _download(n_clicks, period, product, uf, only_ok):
        if not n_clicks:
            return no_update
        years = period_to_years(store.year_range(), period)
        product_code = None if product in (None, "all") else product
        uf_code = None if uf in (None, "all") else uf
        only_ok_flag = bool(only_ok) and "ok" in (only_ok or [])
        df = store.filtered(
            years=years,
            product_code=product_code,
            state_acronym=uf_code,
            only_ok=only_ok_flag,
        )
        return download_payload(df, filename_prefix="embrapa-visao-geral")


def _kpi_strip_filtered(
    store: GoldRepository,
    conv: str,
    ccy: str,
    years: tuple[int, int] | None,
    product_code: str | None,
    uf_code: str | None,
    only_ok: bool,
) -> html.Div:
    """KPI strip respecting the active filters."""
    series = store.time_series(
        convention=conv,
        currency=ccy,
        years=years,
        product_code=product_code,
        state_acronym=uf_code,
    )
    if series.empty:
        return html.Div(
            className="empty-state",
            children="Sem dados para os filtros selecionados.",
        )

    last = series.iloc[-1]

    df_scope = store.filtered(
        years=years,
        product_code=product_code,
        state_acronym=uf_code,
        only_ok=only_ok,
    )
    states_last = df_scope[df_scope["reference_year"] == last["reference_year"]][
        "state_acronym"
    ].nunique()
    states_total = store.df()["state_acronym"].nunique() or 1

    if df_scope.empty:
        pct_ok = 0.0
        rows_total = 0
    else:
        rows_total = len(df_scope)
        pct_ok = round(
            100.0 * (df_scope["data_quality_flag"] == "OK").sum() / max(rows_total, 1),
            1,
        )

    cards = _build_kpi_cards(
        store=store,
        series=series,
        conv=conv,
        ccy=ccy,
        states_value=f"{states_last} / {states_total}",
        states_sub=f"UFs com dados · {int(last['reference_year'])}",
        quality_value=f"{pct_ok:.1f}%".replace(".", ","),
        quality_sub=f"linhas com flag OK · {fmt_number(rows_total)} no recorte",
    )
    return html.Div(className="kpi-row", children=cards)


__all__ = ["PREFIX", "layout", "register_callbacks"]
