"""CSV export helpers.

Shared by the dedicated /export page and the inline "Exportar CSV" button
that lives in every analytical page. Generates a pt-BR locale CSV (UTF-8
with BOM, semicolon separator, comma decimal) so Excel pt-BR opens it
cleanly by default.
"""

from __future__ import annotations

from datetime import datetime

import pandas as pd
from dash import dcc, html

# Default column order surfaced in the UI — anything not in here can still
# be opted-in via the column toggle on /tabela and /export.
DEFAULT_COLUMNS: tuple[str, ...] = (
    "reference_year",
    "reference_date",
    "state_acronym",
    "state_name",
    "region",
    "city_code",
    "city_name",
    "product_code",
    "product_description",
    "quantity_tons",
    "quantity_m3",
    "val_real_ipca_brl",
    "val_real_ipca_usd",
    "val_real_ipca_eur",
    "val_real_ipca_cny",
    "val_real_igpm_brl",
    "val_real_igpm_usd",
    "val_real_igpm_eur",
    "val_real_igpm_cny",
    "val_real_igpdi_brl",
    "val_real_igpdi_usd",
    "val_real_igpdi_eur",
    "val_real_igpdi_cny",
    "val_yearfx_brl",
    "val_yearfx_usd",
    "val_yearfx_eur",
    "val_yearfx_cny",
    "data_quality_flag",
    "last_refresh",
)

# Human-readable header labels (pt-BR) for the exported CSV.
COLUMN_LABELS: dict[str, str] = {
    "reference_year": "Ano",
    "reference_date": "Data ref.",
    "state_acronym": "UF",
    "state_name": "Estado",
    "region": "Região",
    "city_code": "Cód. município",
    "city_name": "Município",
    "product_code": "Cód. produto",
    "product_description": "Produto",
    "quantity_tons": "Quantidade (t)",
    "quantity_m3": "Quantidade (m³)",
    "val_real_ipca_brl": "Valor real IPCA (BRL)",
    "val_real_ipca_usd": "Valor real IPCA (USD)",
    "val_real_ipca_eur": "Valor real IPCA (EUR)",
    "val_real_ipca_cny": "Valor real IPCA (CNY)",
    "val_real_igpm_brl": "Valor real IGP-M (BRL)",
    "val_real_igpm_usd": "Valor real IGP-M (USD)",
    "val_real_igpm_eur": "Valor real IGP-M (EUR)",
    "val_real_igpm_cny": "Valor real IGP-M (CNY)",
    "val_real_igpdi_brl": "Valor real IGP-DI (BRL)",
    "val_real_igpdi_usd": "Valor real IGP-DI (USD)",
    "val_real_igpdi_eur": "Valor real IGP-DI (EUR)",
    "val_real_igpdi_cny": "Valor real IGP-DI (CNY)",
    "val_yearfx_brl": "Valor FX do ano (BRL)",
    "val_yearfx_usd": "Valor FX do ano (USD)",
    "val_yearfx_eur": "Valor FX do ano (EUR)",
    "val_yearfx_cny": "Valor FX do ano (CNY)",
    "data_quality_flag": "Flag de qualidade",
    "last_refresh": "Última carga",
}


def build_csv(df: pd.DataFrame, columns: list[str] | None = None) -> str:
    """Render `df` as a pt-BR-friendly CSV string.

    - UTF-8 (with BOM is added by the download component)
    - Semicolon separator (Excel pt-BR default)
    - Comma decimal mark
    - Header row uses Portuguese labels from COLUMN_LABELS
    """
    if columns:
        cols = [c for c in columns if c in df.columns]
    else:
        cols = [c for c in DEFAULT_COLUMNS if c in df.columns]
    if not cols:
        cols = list(df.columns)
    subset = df[cols].copy()
    rename = {c: COLUMN_LABELS.get(c, c) for c in cols}
    subset.rename(columns=rename, inplace=True)
    return subset.to_csv(
        index=False,
        sep=";",
        decimal=",",
        date_format="%Y-%m-%d",
    )


def download_payload(
    df: pd.DataFrame,
    *,
    filename_prefix: str = "embrapa-commodities",
    columns: list[str] | None = None,
) -> dict[str, str | bool]:
    """Build the dict expected by `dcc.Download` (data + filename)."""
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    filename = f"{filename_prefix}-{stamp}.csv"
    return {
        "content": build_csv(df, columns=columns),
        "filename": filename,
        "type": "text/csv",
        # BOM so Excel pt-BR auto-detects UTF-8 with accented characters.
        "base64": False,
    }


def export_button(
    button_id: dict,
    download_id: dict,
    *,
    label: str = "Exportar CSV",
) -> list:
    """Return the [Button, Download] pair to drop into a page layout.

    The page callback hooks the button's `n_clicks` to a Download `data`
    output and calls `download_payload(filtered_df)`.
    """
    return [
        html.Button(
            label,
            id=button_id,
            n_clicks=0,
            className="btn-secondary",
            type="button",
            **{"data-export": "true"},
        ),
        dcc.Download(id=download_id),
    ]


# IDs of the global header export — fixed (not pattern-matched) because there
# is exactly one in the app shell. Pages contribute the actual filtered
# dataset via a separate dispatcher callback wired in Task #5.
HEADER_EXPORT_BUTTON_ID = "header-export-button"
HEADER_EXPORT_DOWNLOAD_ID = "header-export-download"


def header_export_button(*, label: str = "Exportar") -> html.Span:
    """Render the global export button + download component for the app header.

    Mount ONCE in the shell. The actual export payload is wired by a global
    callback that reads the current view's filtered DataFrame — registered
    by `app.py` when the page registry is built.
    """
    return html.Span(
        className="header-export",
        children=[
            html.Button(
                label,
                id=HEADER_EXPORT_BUTTON_ID,
                n_clicks=0,
                className="btn-secondary",
                type="button",
                title="Exportar o recorte atual em CSV",
                **{"data-export": "true"},
            ),
            dcc.Download(id=HEADER_EXPORT_DOWNLOAD_ID),
        ],
    )
