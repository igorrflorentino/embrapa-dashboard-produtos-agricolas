"""Dash dashboard UI — the Claude Design System reimplementation.

This package is the **presentation layer** of the Embrapa Commodities dashboard.
It is a thin, stateless Dash/Plotly app that consumes the verified BFF in
``embrapa_commodities.serving`` (the *data seam*): UI interactions become
parameterized BigQuery reads against the pre-aggregated ``serving`` marts, and
the small results are cached by ``flask-caching``. There is no Gold held in
process memory — the Pushdown Computing model.

Layout:
  * ``registries``  — ports of the design system's bancos / views / filters
  * ``seam``        — ``dataset_for`` / ``apply_filters`` over the BFF readers
  * ``format``      — pt-BR number/currency formatting + metric conventions
  * ``theme``       — the ``embrapa`` Plotly template + viz palette
  * ``components``  — the app chrome (topbar, sidebar, mega-menu, filters, cards)
  * ``charts``      — Plotly figure builders
  * ``views``       — one layout function per analytical perspective
  * ``app``         — the Dash app, global layout, and routing callbacks

Run it with ``uv run embrapa-dashboard`` (see ``app.main``) or
``uv run python -m embrapa_commodities.dashboard.app``.
"""

from __future__ import annotations
