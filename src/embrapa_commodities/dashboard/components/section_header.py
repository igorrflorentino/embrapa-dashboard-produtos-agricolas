"""Section header — overline + h3 + optional right-aligned action slot."""

from __future__ import annotations

from dash import html


def section_header(overline: str, title: str, action=None) -> html.Div:
    return html.Div(
        className="section-head",
        children=[
            html.Div(
                children=[
                    html.Div(overline, className="overline"),
                    html.H3(title, className="section-title"),
                ]
            ),
            html.Div(action, className="section-action") if action is not None else None,
        ],
    )
