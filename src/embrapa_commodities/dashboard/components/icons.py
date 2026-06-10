"""Inline-SVG icon set, ported from the design system's ``Icon.jsx``.

Dash has no inline ``<svg>`` element, so each icon is rendered as a data-URI SVG
``html.Img``. The stroke colour is baked per call (an ``<img>`` can't inherit
``currentColor``), so callers pass the colour for the icon's context — white on
the green topbar, ink elsewhere. Names mirror the Material Symbols vocabulary.
"""

from __future__ import annotations

# ruff: noqa: E501 — this module is SVG path data; long single-line literals are intentional.
from urllib.parse import quote

from dash import html

# 24×24 stroke geometry (Feather/Lucide style), verbatim from Icon.jsx.
ICONS: dict[str, str] = {
    "dashboard": '<rect x="3" y="3" width="7" height="9"/><rect x="14" y="3" width="7" height="5"/>'
    '<rect x="14" y="12" width="7" height="9"/><rect x="3" y="16" width="7" height="5"/>',
    "database": '<ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M3 5v14a9 3 0 0 0 18 0V5"/>'
    '<path d="M3 12a9 3 0 0 0 18 0"/>',
    "hub": '<circle cx="12" cy="12" r="2.4"/><circle cx="5" cy="6" r="2"/><circle cx="19" cy="6" r="2"/>'
    '<circle cx="5" cy="18" r="2"/><circle cx="19" cy="18" r="2"/><path d="M10.3 10.6 6.3 7.2"/>'
    '<path d="m13.7 10.6 4-3.4"/><path d="m10.3 13.4-4 3.4"/><path d="m13.7 13.4 4 3.4"/>',
    "expand_more": '<polyline points="6 9 12 15 18 9"/>',
    "info": '<circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/>'
    '<line x1="12" y1="8" x2="12.01" y2="8"/>',
    "menu_book": '<path d="M2 19V5a2 2 0 0 1 2-2h6v18H4a2 2 0 0 1-2-2z"/>'
    '<path d="M22 19V5a2 2 0 0 0-2-2h-6v18h6a2 2 0 0 0 2-2z"/>',
    "pulse": '<path d="M22 12h-4l-3 9L9 3l-3 9H2"/>',
    "fact_check": '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="m9 10 1.5 1.5L13 9"/>'
    '<path d="M16 11h2"/><path d="m9 16 1.5 1.5L13 15"/><path d="M16 17h2"/>',
    "format_quote": '<path d="M7 7h4v6H5v-2c0-2 .5-3 2-4zm8 0h4v6h-6v-2c0-2 .5-3 2-4z"/>',
    "link": '<path d="M10 13a5 5 0 0 0 7 0l3-3a5 5 0 0 0-7-7l-1.5 1.5"/>'
    '<path d="M14 11a5 5 0 0 0-7 0l-3 3a5 5 0 0 0 7 7l1.5-1.5"/>',
    "close": '<line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>',
    "refresh": '<polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/>'
    '<path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>',
    "warning": '<path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>'
    '<line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>',
    "arrow_upward": '<line x1="12" y1="19" x2="12" y2="5"/><polyline points="5 12 12 5 19 12"/>',
    "arrow_downward": '<line x1="12" y1="5" x2="12" y2="19"/><polyline points="19 12 12 19 5 12"/>',
    "content_copy": '<rect x="9" y="9" width="11" height="11" rx="2"/>'
    '<path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>',
    "filter": '<polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/>',
    "download": '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>'
    '<polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>',
    "search": '<circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>',
    "trending_up": '<polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/><polyline points="16 7 22 7 22 13"/>',
}


def icon(name: str, *, size: int = 18, color: str = "#333333") -> html.Img:
    """Return an icon as a data-URI SVG ``html.Img`` (stroke = ``color``)."""
    paths = ICONS.get(name)
    if not paths:
        return html.Span()
    svg = (
        f"<svg xmlns='http://www.w3.org/2000/svg' width='{size}' height='{size}' "
        f"viewBox='0 0 24 24' fill='none' stroke='{color}' stroke-width='1.8' "
        f"stroke-linecap='round' stroke-linejoin='round'>{paths}</svg>"
    )
    return html.Img(
        src="data:image/svg+xml;utf8," + quote(svg),
        width=size,
        height=size,
        style={"display": "inline-block", "verticalAlign": "middle", "flexShrink": 0},
        alt="",
    )
