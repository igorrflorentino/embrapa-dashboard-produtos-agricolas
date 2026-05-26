"""Data-source registry — the spine of the multi-source dashboard.

A `DataSource` declares everything the shell needs to surface a specific
upstream dataset: its label, icon, the analytical views shown in the top
nav, the secondary tools/docs grouped into sidebar sections, and the
in-memory store that the views' callbacks query.

The dashboard is intentionally **source-scoped**: switching between
sources should look like switching between different applications — no
mixed data, no shared filter state. The only truly global page is the
`/status` health view.

To add a new source X:

1. Build a store class for X (or reuse `GoldStore` if X is also a single
   BigQuery table with the same shape).
2. Write source-specific page modules under `pages/x_*.py` whose `PREFIX`
   constants are unique across all sources — Dash uses callback Output IDs
   to dispatch, and two callbacks with the same Output ID would clash.
3. Add an entry to `_build_registry()` describing X's views and sections.

URLs are `/<source-id>/<view-id>`. View IDs are the URL slugs (e.g.
`visao-geral`, `geografia`); they need not match the underlying page
module's `PREFIX`.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

# Public type alias for the store: we don't constrain the shape here so
# future sources can plug in their own stores with their own slicer
# methods. Page modules know the concrete type they expect.
Store = object


@dataclass(frozen=True)
class View:
    """A single page bound to a data source."""

    id: str  # URL slug, e.g. "visao-geral"
    label: str  # pt-BR display label
    icon: str  # material-symbols name
    layout_fn: Callable[[Store], object]
    register_fn: Callable[[object, Store], None]


@dataclass(frozen=True)
class SidebarSection:
    """A titled group of secondary views in the sidebar."""

    title: str  # pt-BR section header
    views: tuple[View, ...]


@dataclass(frozen=True)
class DataSource:
    """Everything the shell needs to surface a source."""

    id: str  # URL slug, e.g. "ibge-pevs"
    label: str  # short brand name, e.g. "IBGE PEVS"
    icon: str
    primary_views: tuple[View, ...]  # top nav
    sidebar_sections: tuple[SidebarSection, ...]  # secondary tools/docs
    store: Store

    # ── Helpers ───────────────────────────────────────────────────────────
    def find_view(self, view_id: str) -> View | None:
        for v in self.primary_views:
            if v.id == view_id:
                return v
        for sec in self.sidebar_sections:
            for v in sec.views:
                if v.id == view_id:
                    return v
        return None

    def default_view(self) -> View:
        return self.primary_views[0]

    def all_views(self) -> list[View]:
        out = list(self.primary_views)
        for sec in self.sidebar_sections:
            out.extend(sec.views)
        return out


# ── Default source convention ─────────────────────────────────────────────
DEFAULT_SOURCE_ID = "ibge-pevs"


def build_registry() -> dict[str, DataSource]:
    """Construct every available `DataSource`.

    Called once at app startup from `app.py`. Page modules are imported
    lazily here to avoid a circular dependency: each page's
    `register_callbacks` imports `build_error_payload` from `app.py`, and
    `app.py` imports this module.
    """
    from embrapa_commodities.dashboard.config import get_settings
    from embrapa_commodities.dashboard.data import GoldStore
    from embrapa_commodities.dashboard.pages import (
        dados,
        export,
        geography,
        glossario,
        overview,
        product,
        sobre_api,
        tabela,
    )

    ingestion, dashboard = get_settings()
    ibge_pevs_store = GoldStore(ingestion, dashboard)

    ibge_pevs = DataSource(
        id="ibge-pevs",
        label="IBGE PEVS",
        icon="eco",
        primary_views=(
            View(
                id="visao-geral",
                label="Visão geral",
                icon="dashboard",
                layout_fn=overview.layout,
                register_fn=overview.register_callbacks,
            ),
            View(
                id="produto",
                label="Produto",
                icon="eco",
                layout_fn=product.layout,
                register_fn=product.register_callbacks,
            ),
            View(
                id="geografia",
                label="Geografia",
                icon="map",
                layout_fn=geography.layout,
                register_fn=geography.register_callbacks,
            ),
        ),
        sidebar_sections=(
            SidebarSection(
                title="Dados",
                views=(
                    View(
                        id="tabela",
                        label="Tabela bruta",
                        icon="database",
                        layout_fn=tabela.layout,
                        register_fn=tabela.register_callbacks,
                    ),
                    View(
                        id="export",
                        label="Exportar CSV",
                        icon="download",
                        layout_fn=export.layout,
                        register_fn=export.register_callbacks,
                    ),
                    View(
                        id="sobre-api",
                        label="Sobre a API",
                        icon="api",
                        layout_fn=sobre_api.layout,
                        register_fn=sobre_api.register_callbacks,
                    ),
                ),
            ),
            SidebarSection(
                title="Sobre",
                views=(
                    View(
                        id="glossario",
                        label="Glossário",
                        icon="help",
                        layout_fn=glossario.layout,
                        register_fn=glossario.register_callbacks,
                    ),
                    View(
                        id="dados",
                        label="Sobre os dados",
                        icon="info",
                        layout_fn=dados.layout,
                        register_fn=dados.register_callbacks,
                    ),
                ),
            ),
        ),
        store=ibge_pevs_store,
    )

    return {ibge_pevs.id: ibge_pevs}
