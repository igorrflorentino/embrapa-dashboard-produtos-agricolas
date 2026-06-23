"""Regenerate the IBGE municipal territorial-mesh seed (city_code → sub-UF levels).

The dashboard's geography filter goes finer than UF only if it can map each
município to its IBGE sub-UF groupings. IBGE divides each UF two INDEPENDENT,
PARALLEL ways (they do not nest into each other):

  • classic census division : Mesorregião → Microrregião → Município
  • current division (2017)  : Região Intermediária → Região Imediata → Município

The Localidades API returns both hierarchies nested under every município in a
single call, so one fetch yields the complete de-para. Gold already carries the
7-digit ``city_code`` (SIDRA n6), so this seed joins straight onto it — no
ingestion change.

Writes ``dbt/seeds/ibge_municipio_mesh.csv`` (one row per município, ~5570),
sorted by city_code, UTF-8. Rebuild after running:

    uv run python scripts/refresh_ibge_municipio_mesh.py
    make dbt-build            # (or: cd dbt && uv run dbt seed)

Uses ``requests`` (a core dep) because the host gzip-encodes the response.
"""

from __future__ import annotations

import csv
from pathlib import Path

import requests

URL = "https://servicodados.ibge.gov.br/api/v1/localidades/municipios"
SEED = Path(__file__).resolve().parents[1] / "dbt" / "seeds" / "ibge_municipio_mesh.csv"

FIELDNAMES = [
    "city_code",
    "city_name",
    "uf_code",
    "state_acronym",
    "state_name",
    "region_code",
    "region_abbrev",
    "region_name",
    "meso_code",
    "meso_name",
    "micro_code",
    "micro_name",
    "intermediaria_code",
    "intermediaria_name",
    "imediata_code",
    "imediata_name",
]


def _row(m: dict) -> dict:
    """Flatten one Localidades município into the seed's wide row.

    Both hierarchies carry the same UF/região, so read those from the classic
    branch. ``.get`` guards a município missing the 2017 branch (none today, but
    the API has shifted shape before — a blank is safe and visible)."""
    micro = m.get("microrregiao") or {}
    meso = micro.get("mesorregiao") or {}
    imediata = m.get("regiao-imediata") or {}
    intermediaria = imediata.get("regiao-intermediaria") or {}
    # UF + grande região are shared by both divisions; read from whichever branch
    # exists. A município created AFTER the classic meso/micro division was frozen
    # (e.g. Boa Esperança do Norte/MT, 2023) has ONLY the 2017 branch — so falling
    # back to it keeps UF/região populated (meso/micro stay blank, which is correct).
    uf = meso.get("UF") or intermediaria.get("UF") or {}
    region = uf.get("regiao") or {}
    return {
        "city_code": str(m["id"]),
        "city_name": m.get("nome", ""),
        "uf_code": str(uf.get("id", "")),
        "state_acronym": uf.get("sigla", ""),
        "state_name": uf.get("nome", ""),
        "region_code": str(region.get("id", "")),
        "region_abbrev": region.get("sigla", ""),
        "region_name": region.get("nome", ""),
        "meso_code": str(meso.get("id", "")),
        "meso_name": meso.get("nome", ""),
        "micro_code": str(micro.get("id", "")),
        "micro_name": micro.get("nome", ""),
        "intermediaria_code": str(intermediaria.get("id", "")),
        "intermediaria_name": intermediaria.get("nome", ""),
        "imediata_code": str(imediata.get("id", "")),
        "imediata_name": imediata.get("nome", ""),
    }


def main() -> None:
    resp = requests.get(URL, timeout=120, headers={"User-Agent": "Mozilla/5.0"})
    resp.raise_for_status()
    municipios = resp.json()
    rows = [_row(m) for m in municipios]
    rows.sort(key=lambda r: int(r["city_code"]))

    # Sanity: IBGE has ~5570 municípios; refuse to overwrite the seed with a
    # truncated/garbage response (a partial fetch would silently shrink the mesh).
    if len(rows) < 5000:
        raise SystemExit(f"Refusing to write only {len(rows)} municípios (expected ~5570).")
    missing = [r["city_code"] for r in rows if not r["micro_code"] or not r["imediata_code"]]
    if missing:
        print(f"WARNING: {len(missing)} município(s) missing a sub-UF level, e.g. {missing[:5]}")

    with SEED.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDNAMES, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} municípios to {SEED}")


if __name__ == "__main__":
    main()
