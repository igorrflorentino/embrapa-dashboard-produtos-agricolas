"""Auxiliary discovery helpers used by `embrapa discover ...`.

These functions are NEVER called by the main ingestion pipeline. They exist
purely so the engineer can inspect what is available on the IBGE / BCB APIs
before committing exact codes to `.env`.
"""

from __future__ import annotations

from dataclasses import dataclass

import requests

REQUEST_TIMEOUT = 30


# ─── IBGE SIDRA ──────────────────────────────────────────────────────────────
SIDRA_METADATA_URL = "https://servicodados.ibge.gov.br/api/v3/agregados/{table_id}/metadados"
SIDRA_PERIODS_URL = "https://servicodados.ibge.gov.br/api/v3/agregados/{table_id}/periodos"


@dataclass(frozen=True)
class ProductMatch:
    code: str
    name: str
    classification_id: str


def search_ibge_products(table_id: str, keywords: list[str]) -> list[ProductMatch]:
    """Return every product whose name contains any of the keywords (case-insensitive)."""
    response = requests.get(SIDRA_METADATA_URL.format(table_id=table_id), timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    payload = response.json()
    classifications = payload.get("classificacoes", [])
    needles = [k.lower() for k in keywords]

    matches: list[ProductMatch] = []
    for classification in classifications:
        for category in classification.get("categorias", []):
            name = str(category.get("nome", ""))
            if any(n in name.lower() for n in needles):
                matches.append(
                    ProductMatch(
                        code=str(category["id"]),
                        name=name,
                        classification_id=str(classification["id"]),
                    )
                )
    return sorted(matches, key=lambda m: (m.classification_id, m.code))


def list_ibge_periods(table_id: str) -> list[int]:
    """Return all years for which the table has data, sorted ascending."""
    response = requests.get(SIDRA_PERIODS_URL.format(table_id=table_id), timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    periods = response.json()
    years: list[int] = []
    for p in periods:
        raw = str(p.get("id") or (p.get("literals") or [""])[0])[:4]
        if raw.isdigit():
            years.append(int(raw))
    return sorted(set(years))


# ─── BCB SGS ─────────────────────────────────────────────────────────────────
BCB_SAMPLE_URL = (
    "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{code}/dados/ultimos/{n}?formato=json"
)


@dataclass(frozen=True)
class BcbSeriesSample:
    code: str
    sample: list[dict]


def sample_bcb_series(code: str, n: int = 5) -> BcbSeriesSample:
    """Pull the last N observations of an SGS series — useful to validate a code."""
    response = requests.get(BCB_SAMPLE_URL.format(code=code, n=n), timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    return BcbSeriesSample(code=code, sample=response.json())
