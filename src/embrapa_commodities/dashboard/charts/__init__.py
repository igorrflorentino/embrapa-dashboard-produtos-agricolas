"""Plotly figure builders on the ``embrapa`` template.

The prototype hand-rolls SVG charts; per the handoff ("recreate the visual
output in whatever tech fits — charts → Plotly") these are reimplemented as
Plotly figures sharing the brand template (``theme.register_template``). Each
builder returns a ``dcc.Graph`` ready to drop into a card.
"""

from __future__ import annotations
