"""Regenerate the BRL/CNY reference seed from the Frankfurter API (ECB rates).

The BCB does not publish a BRL/CNY (nor USD/CNY) exchange rate in SGS or PTAX
(PTAX quotes only 10 currencies; the yuan is not one of them). China is a major
trade partner in the COMEX data, so the CNY column in the Gold tables is sourced
externally from the European Central Bank reference rates via Frankfurter
(https://frankfurter.dev), a free, key-less, ECB-backed FX API.

This writes ``dbt/seeds/extfx_cny_brl.csv`` (monthly average BRL per 1 CNY).
Run it to extend the seed with newer months, then rebuild dbt:

    uv run python scripts/refresh_cny_seed.py
    make dbt-build      # or dbt-build-prod-with-backup for prod

ECB CNY data starts in late 2004; earlier COMEX/PEVS rows get a NULL CNY rate.
"""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path

import pandas as pd

START = "2004-12-01"
END = "2026-12-31"
URL = f"https://api.frankfurter.dev/v1/{START}..{END}?base=CNY&symbols=BRL"
SEED = Path(__file__).resolve().parents[1] / "dbt" / "seeds" / "extfx_cny_brl.csv"


def main() -> None:
    with urllib.request.urlopen(URL, timeout=60) as resp:
        payload = json.load(resp)

    daily = pd.DataFrame(
        [(date, row["BRL"]) for date, row in payload["rates"].items()],
        columns=["date", "brl_per_cny"],
    )
    daily["date"] = pd.to_datetime(daily["date"])

    # Resample the daily ECB rates to a monthly mean, dated on the first of the
    # month — the grain the Gold fx CTEs average over.
    monthly = (
        daily.sort_values("date")
        .set_index("date")["brl_per_cny"]
        .resample("MS")
        .mean()
        .round(6)
        .reset_index()
    )
    monthly["reference_date"] = monthly["date"].dt.strftime("%Y-%m-%d")
    monthly[["reference_date", "brl_per_cny"]].to_csv(SEED, index=False)
    span = f"{monthly.reference_date.min()} → {monthly.reference_date.max()}"
    print(f"Wrote {len(monthly)} months to {SEED} ({span})")


if __name__ == "__main__":
    main()
