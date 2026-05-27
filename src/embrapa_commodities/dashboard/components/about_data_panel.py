"""Collapsible "Sobre estes dados" panel for the bottom of each analytical view.

Anchors per-view methodology notes (sources, coverage gaps, caveats) next
to the analysis they qualify, rather than burying them in a separate
documentation page. Replaces the dedicated `/dados` page after Task #5.

Uses the native `<details>` / `<summary>` HTML elements — no Dash callback
needed for open/close, the browser handles it. Lighter than the help_modal
(which is for short inline glossary lookups); this is for longer narrative
context that fits comfortably in a collapsed accordion.
"""

from __future__ import annotations

from dash import dcc, html


def about_data_panel(
    *,
    sources: list[str] | None = None,
    coverage_notes: list[str] | None = None,
    caveats: list[str] | None = None,
    body: object | None = None,
) -> html.Details:
    """Render a collapsed-by-default ``<details>`` block.

    Two usage modes — pick one:

    - **Structured**: pass any combination of ``sources`` / ``coverage_notes``
      / ``caveats`` as lists of pt-BR strings (Markdown supported per item).
      Each non-empty list becomes a labelled subsection.
    - **Free-form**: pass ``body`` as any Dash component (e.g.
      ``dcc.Markdown(...)``) to render verbatim.

    If both are given, ``body`` wins.
    """
    if body is not None:
        contents = body
    else:
        parts: list[html.Div] = []
        if sources:
            parts.append(_section("Fontes", sources))
        if coverage_notes:
            parts.append(_section("Cobertura", coverage_notes))
        if caveats:
            parts.append(_section("Ressalvas", caveats))
        contents = html.Div(parts) if parts else html.Div("Sem notas para esta visão.")
    return html.Details(
        className="about-data-panel",
        children=[
            html.Summary("Sobre estes dados"),
            html.Div(className="about-data-body", children=contents),
        ],
    )


def _section(title: str, items: list[str]) -> html.Div:
    return html.Div(
        className="about-data-section",
        children=[
            html.H4(title, className="overline"),
            html.Ul([html.Li(dcc.Markdown(item, link_target="_blank")) for item in items]),
        ],
    )


__all__ = ["about_data_panel"]
