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

pt-BR PRESERVATION — ``country_name`` is a **curated pt-BR** column (per
``dbt/seeds/_seeds.yml``): those names flow verbatim to the user-facing SPA
(``reporter_name`` / ``partner_name`` in ``gold_comtrade_flows``). The UN blob
only carries English labels, so this script must NOT clobber the hand-translated
names. It therefore reads the existing seed first and keeps every existing
``country_name`` as-is; the English UN ``text`` is used ONLY to seed
``country_name`` for m49 codes not yet present in the CSV (new areas), which a
human must then re-translate to pt-BR by hand. ``iso_a3`` and ``is_group`` are
always refreshed from the source (not user-facing / not translated).
"""

from __future__ import annotations

import csv
import json
import urllib.request
from pathlib import Path

URL = "https://comtradeapi.un.org/files/v1/app/reference/partnerAreas.json"
SEED = Path(__file__).resolve().parents[1] / "dbt" / "seeds" / "comtrade_country.csv"


def _load_existing_names() -> dict[str, str]:
    """Return {m49_code: curated pt-BR country_name} from the current seed, if any.

    Preserves the hand-translated pt-BR names across a refresh — the UN source is
    English-only and those names are user-facing (see module docstring).
    """
    if not SEED.exists():
        return {}
    with SEED.open("r", newline="", encoding="utf-8") as fh:
        return {
            row["m49_code"]: row["country_name"]
            for row in csv.DictReader(fh)
            if row.get("m49_code") and row.get("country_name")
        }


def main() -> None:
    existing_names = _load_existing_names()

    req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        # The blob is served with a UTF-8 BOM → decode with utf-8-sig.
        payload = json.loads(resp.read().decode("utf-8-sig"))

    new_codes = []
    rows = []
    for area in payload["results"]:
        code = str(area["PartnerCode"])
        iso = (area.get("PartnerCodeIsoAlpha3") or "").strip()
        # Keep the curated pt-BR name; only fall back to the English UN label for a
        # brand-new area not yet in the seed (flagged below for manual translation).
        if code in existing_names:
            name = existing_names[code]
        else:
            name = area["text"]
            new_codes.append(code)
        rows.append(
            {
                "m49_code": code,
                "iso_a3": iso,
                "country_name": name,
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
    if new_codes:
        print(
            f"WARNING: {len(new_codes)} new area(s) got the English UN name and MUST be "
            f"re-translated to pt-BR by hand (m49 codes: {', '.join(new_codes)})."
        )


if __name__ == "__main__":
    main()
