"""Icon helper — Material Symbols (Outlined, weight 400).

The Embrapa Mobile Identity Guide explicitly endorses Google Material Design
icons as the in-product iconography baseline. We load the Material Symbols
Outlined font from Google Fonts (see `assets/01-tokens.css`) and use a span
with the proper class to render each glyph.

We expose a thin Python helper so pages can write `icon("dashboard")` and not
care about the underlying mechanism.
"""

from __future__ import annotations

from dash import html

# Mapping from the design system's logical names (Icon.jsx) to the Material
# Symbols glyph name. The Material Symbols glyph name is the same as the span's
# text content — that's how Material Symbols ligatures work.
_GLYPH_FOR = {
    "dashboard": "dashboard",
    "eco": "eco",
    "map": "map",
    "fact_check": "fact_check",
    "database": "database",
    "download": "download",
    "info": "info",
    "schedule": "schedule",
    "arrow_upward": "arrow_upward",
    "arrow_downward": "arrow_downward",
    "refresh": "refresh",
    "help": "help",
    "api": "api",
    "search": "search",
    "notifications": "notifications",
    "menu_book": "menu_book",
}


def icon(name: str, size: int = 18) -> html.Span:
    """Inline Material Symbols icon (Outlined). Inherits text color.

    Unknown names fall back to the literal name as text — visible enough to
    spot in dev without breaking layout.
    """
    glyph = _GLYPH_FOR.get(name, name)
    return html.Span(
        glyph,
        className="material-symbols-outlined",
        style={
            "fontSize": f"{size}px",
            "display": "inline-flex",
            "alignItems": "center",
            "justifyContent": "center",
            "lineHeight": 1,
            "verticalAlign": "middle",
            "flexShrink": 0,
            "fontVariationSettings": "'FILL' 0, 'wght' 400, 'GRAD' 0, 'opsz' 24",
        },
    )
