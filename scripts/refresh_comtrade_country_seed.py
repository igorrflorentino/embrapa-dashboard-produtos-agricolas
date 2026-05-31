"""Regenerate the UN Comtrade country/area reference seed (M49 → ISO3 + name).

Comtrade identifies both the reporter and the partner by a numeric **M49 area
code**. ``partnerAreas.json`` is the authoritative, complete list — a superset of
the reporters list that also carries the partner-only entries (World = 0,
Bunkers, Free Zones, and the various "nes" / not-elsewhere-specified aggregates).
We seed from it so both ``reporter_code`` and ``partner_code`` in the Gold table
resolve to a readable name + ISO-alpha-3 for Looker.

Writes ``dbt/seeds/comtrade_country.csv`` (m49_code, iso_a3, country_name,
is_group). ``is_group`` flags aggregate areas (World, EU, "X, nes", …) so the
dashboard can exclude them from a true bilateral matrix.

    uv run python scripts/refresh_comtrade_country_seed.py
    make dbt-build

The host serves these reference blobs over GET with a browser-like User-Agent
only (it 404s the default urllib agent), so we set one explicitly.
"""

from __future__ import annotations

import csv
import json
import urllib.request
from pathlib import Path

URL = "https://comtradeapi.un.org/files/v1/app/reference/partnerAreas.json"
SEED = Path(__file__).resolve().parents[1] / "dbt" / "seeds" / "comtrade_country.csv"


def main() -> None:
    req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        # The blob is served with a UTF-8 BOM → decode with utf-8-sig.
        payload = json.loads(resp.read().decode("utf-8-sig"))

    rows = []
    for area in payload["results"]:
        code = str(area["PartnerCode"])
        iso = (area.get("PartnerCodeIsoAlpha3") or "").strip()
        rows.append(
            {
                "m49_code": code,
                "iso_a3": iso,
                "country_name": area["text"],
                "is_group": "true" if area.get("isGroup") else "false",
            }
        )
    rows.sort(key=lambda r: int(r["m49_code"]))

    with SEED.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh, fieldnames=["m49_code", "iso_a3", "country_name", "is_group"], lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} areas to {SEED}")


if __name__ == "__main__":
    main()
