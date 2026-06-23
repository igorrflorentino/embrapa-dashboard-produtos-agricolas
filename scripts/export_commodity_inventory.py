"""Export the per-banco commodity inventory (code + description) to CSV.

One-off reporting helper: pulls every DISTINCT (banco, product code, description)
from the five live Gold tables and writes a flat CSV for a supervisor report.

Run with owner ADC (no impersonation), e.g.:
    GCP_IMPERSONATION_SA= uv run python scripts/export_commodity_inventory.py
"""

from __future__ import annotations

import csv
from pathlib import Path

from google.cloud import bigquery

PROJECT = "embrapa-dashboard-commodities"
OUT = Path("inventario_commodities.csv")

# (banco label, gold table, code column, description column)
SOURCES = [
    ("IBGE PEVS", "gold_pevs_production", "product_code", "product_description"),
    ("IBGE PAM", "gold_pam_production", "product_code", "product_description"),
    ("IBGE PPM", "gold_ppm_production", "product_code", "product_description"),
    ("MDIC COMEX", "gold_comex_flows", "ncm_code", "ncm_description"),
    ("UN COMTRADE", "gold_comtrade_flows", "cmd_code", "cmd_description"),
]

arms = "\n  UNION ALL\n".join(
    f"  SELECT DISTINCT '{label}' AS banco, {code} AS codigo, "
    f"{desc} AS descricao FROM `{PROJECT}.gold.{table}`"
    for label, table, code, desc in SOURCES
)

ORDER = {label: i for i, (label, *_rest) in enumerate(SOURCES)}
case = " ".join(f"WHEN '{label}' THEN {i}" for label, i in ORDER.items())

query = f"""
WITH all_commodities AS (
{arms}
)
SELECT banco, codigo, descricao
FROM all_commodities
ORDER BY CASE banco {case} END, SAFE_CAST(codigo AS INT64), codigo
"""


def main() -> None:
    client = bigquery.Client(project=PROJECT)
    rows = list(client.query(query).result())

    with OUT.open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.writer(fh)
        writer.writerow(["Banco", "Codigo Commodity", "Descricao Commodity"])
        for r in rows:
            writer.writerow([r["banco"], r["codigo"], r["descricao"] or ""])

    by_banco: dict[str, int] = {}
    for r in rows:
        by_banco[r["banco"]] = by_banco.get(r["banco"], 0) + 1

    print(f"Wrote {len(rows)} rows to {OUT.resolve()}")
    for label, *_ in SOURCES:
        print(f"  {label:<12} {by_banco.get(label, 0):>4} commodities")


if __name__ == "__main__":
    main()
