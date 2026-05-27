"""Reusable help/glossary modal — info-icon triggers a panel with explanatory content.

Each modal is namespaced by a `prefix` (typically the page PREFIX + a
short suffix, e.g. ``"overview-yoy"``) so multiple modals can coexist on
the same page. The CSS hooks (`.help-modal`, `.help-modal.visible`,
`.help-modal-backdrop`, etc.) are added to `assets/02-dashboard.css` in
Task #6.

Three pieces to wire in:
  1. `help_trigger(prefix)` — an inline `(i)` icon button next to the KPI/section it explains
  2. `help_modal(prefix, title=..., content=...)` — the modal container itself
  3. `register_callbacks(app, prefix)` — wires open/close behaviour for that prefix
"""

from __future__ import annotations

from dash import Input, Output, State, callback_context, html
from dash.exceptions import PreventUpdate


def help_trigger(prefix: str, *, title: str | None = None) -> html.Button:
    """Inline ``i`` icon next to a label or KPI value."""
    label = title or "Saiba mais"
    return html.Button(
        "i",
        id={"section": prefix, "control": "help-trigger"},
        className="help-trigger",
        type="button",
        title=label,
        **{"aria-label": label},
    )


def help_modal(prefix: str, *, title: str, content) -> html.Div:
    """Modal container; renders hidden by default until the trigger toggles it visible.

    `content` accepts any Dash component (str, dcc.Markdown, html.Div, ...).
    """
    return html.Div(
        id={"section": prefix, "control": "help-modal"},
        className="help-modal",
        children=[
            html.Div(
                id={"section": prefix, "control": "help-backdrop"},
                className="help-modal-backdrop",
                n_clicks=0,
            ),
            html.Div(
                className="help-modal-panel card",
                children=[
                    html.Div(
                        className="help-modal-head",
                        children=[
                            html.H3(title, className="section-title"),
                            html.Button(
                                "×",
                                id={"section": prefix, "control": "help-close"},
                                className="help-close",
                                type="button",
                                n_clicks=0,
                                **{"aria-label": "Fechar"},
                            ),
                        ],
                    ),
                    html.Div(className="help-modal-body", children=content),
                ],
            ),
        ],
    )


def register_callbacks(app, prefix: str) -> None:
    """Wire toggle behaviour for the help-modal instance with this prefix.

    Call once per page that mounts a `help_modal` with this prefix. The
    same callback handles open (trigger click) and close (close-button or
    backdrop click) by switching the modal's CSS class.
    """

    @app.callback(
        Output({"section": prefix, "control": "help-modal"}, "className"),
        Input({"section": prefix, "control": "help-trigger"}, "n_clicks"),
        Input({"section": prefix, "control": "help-close"}, "n_clicks"),
        Input({"section": prefix, "control": "help-backdrop"}, "n_clicks"),
        State({"section": prefix, "control": "help-modal"}, "className"),
        prevent_initial_call=True,
    )
    def _toggle(_open_clicks, _close_clicks, _backdrop_clicks, _current_class):
        if not callback_context.triggered:
            raise PreventUpdate
        trigger = callback_context.triggered[0]["prop_id"]
        # The trigger ID is JSON-serialized in the prop_id — string match
        # is enough to disambiguate between the three possible sources.
        if "help-trigger" in trigger:
            return "help-modal visible"
        return "help-modal"


__all__ = ["help_modal", "help_trigger", "register_callbacks"]
