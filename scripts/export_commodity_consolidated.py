"""Export the commodity inventory CONSOLIDATED by commodity concept (crosswalk).

Joins every per-banco product code to gold_commodity_crosswalk so each code is
grouped under its cross-source commodity CONCEPT (Soja, Madeira, ...). A LEFT
JOIN keeps every code: those the crosswalk does not yet link (all PAM + PPM, plus
deep COMTRADE wood-derivatives) fall into a clearly-marked "(não vinculado)"
bucket instead of being silently dropped.

Writes two files:
  - inventario_commodities_consolidado.csv  (detail: concept | banco | code | desc)
  - inventario_commodities_por_conceito_resumo.csv  (summary: concept x banco counts)

Run with owner ADC (no impersonation):
    GCP_IMPERSONATION_SA= uv run python scripts/export_commodity_consolidated.py
"""

from __future__ import annotations

import csv
from pathlib import Path

from google.cloud import bigquery

PROJECT = "embrapa-dashboard-commodities"
OUT_DETAIL = Path("inventario_commodities_consolidado.csv")
OUT_SUMMARY = Path("inventario_commodities_por_conceito_resumo.csv")
UNLINKED = "(não vinculado)"

# (banco label, crosswalk source key, gold table, code column, description column)
# crosswalk only carries pevs/comex/comtrade → pam/ppm keys never match (by design).
SOURCES = [
    ("IBGE PEVS", "pevs", "gold_pevs_production", "product_code", "product_description"),
    ("IBGE PAM", "pam", "gold_pam_production", "product_code", "product_description"),
    ("IBGE PPM", "ppm", "gold_ppm_production", "product_code", "product_description"),
    ("MDIC COMEX", "comex", "gold_comex_flows", "ncm_code", "ncm_description"),
    ("UN COMTRADE", "comtrade", "gold_comtrade_flows", "cmd_code", "cmd_description"),
]

inv_arms = "\n  UNION ALL\n".join(
    f"  SELECT DISTINCT '{label}' AS banco, '{src}' AS src, "
    f"{code} AS codigo, {desc} AS descricao FROM `{PROJECT}.gold.{table}`"
    for label, src, table, code, desc in SOURCES
)
banco_order = " ".join(f"WHEN '{label}' THEN {i}" for i, (label, *_r) in enumerate(SOURCES))

detail_query = f"""
WITH inv AS (
{inv_arms}
)
SELECT
  COALESCE(x.commodity_name, '{UNLINKED}') AS conceito,
  inv.banco, inv.codigo, inv.descricao
FROM inv
LEFT JOIN `{PROJECT}.gold.gold_commodity_crosswalk` x
  ON x.source = inv.src AND x.code = inv.codigo
ORDER BY
  (x.commodity_name IS NULL),                 -- linked concepts first, unlinked last
  x.commodity_name,
  CASE inv.banco {banco_order} END,
  SAFE_CAST(inv.codigo AS INT64), inv.codigo
"""

summary_query = f"""
SELECT
  commodity_name AS conceito,
  COUNTIF(source = 'pevs')     AS pevs,
  COUNTIF(source = 'comex')    AS comex,
  COUNTIF(source = 'comtrade') AS comtrade,
  COUNT(*)                     AS total_codigos
FROM `{PROJECT}.gold.gold_commodity_crosswalk`
GROUP BY conceito
ORDER BY conceito
"""


def main() -> None:
    client = bigquery.Client(project=PROJECT)

    detail = list(client.query(detail_query).result())
    with OUT_DETAIL.open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(["Conceito Commodity", "Banco", "Codigo Commodity", "Descricao Commodity"])
        for r in detail:
            w.writerow([r["conceito"], r["banco"], r["codigo"], r["descricao"] or ""])

    summary = list(client.query(summary_query).result())
    with OUT_SUMMARY.open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(["Conceito Commodity", "PEVS", "COMEX", "COMTRADE", "Total de codigos"])
        for r in summary:
            w.writerow([r["conceito"], r["pevs"], r["comex"], r["comtrade"], r["total_codigos"]])

    # console report
    linked = sum(1 for r in detail if r["conceito"] != UNLINKED)
    print(f"Detalhe : {len(detail)} codigos -> {OUT_DETAIL.resolve()}")
    print(f"Resumo  : {len(summary)} conceitos -> {OUT_SUMMARY.resolve()}")
    print(f"Vinculados ao crosswalk: {linked} | Nao vinculados: {len(detail) - linked}\n")

    print(f"{'Conceito':<20}{'PEVS':>6}{'COMEX':>7}{'COMTRADE':>10}{'Total':>7}")
    for r in summary:
        print(
            f"{r['conceito']:<20}{r['pevs']:>6}{r['comex']:>7}"
            f"{r['comtrade']:>10}{r['total_codigos']:>7}"
        )

    unlinked: dict[str, int] = {}
    for r in detail:
        if r["conceito"] == UNLINKED:
            unlinked[r["banco"]] = unlinked.get(r["banco"], 0) + 1
    if unlinked:
        print("\nNao vinculados por banco:")
        for banco, n in unlinked.items():
            print(f"  {banco:<14}{n:>4}")


if __name__ == "__main__":
    main()
