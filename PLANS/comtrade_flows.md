# UN COMTRADE source — `gold_comtrade_flows`

> ⚠️ **SUPERSEDED — historical plan (pre-implementation).** The source was
> delivered and is in production (PRs #45-#53). The implementation **diverged**
> from this plan on key points: products at the **HS6** level (not HS4), **4
> regimes** X/M/RX/RM (not just X/M), dev window **2022-2023** (not 2000→current),
> chunking by `(year, reporter batch)` with **adaptive split** anti-truncation, and
> Silver keeps only the aggregated record (anti-double-counting). For the current
> state, see [`ARCHITECTURE.md`](../ARCHITECTURE.md), [`CHANGELOG.md`](../CHANGELOG.md)
> and [`docs/frontend_data_contract.md`](../docs/frontend_data_contract.md). Kept
> only as a record of the original design.

> **Original status:** planned. Access gate **validated live** (2026-05-31): the
> public API responds without a key (HTTP 200, shape ok), but caps at **500
> records/request** (global ch. 44 overflows). With the **free key** the limit
> rises to ~100k records/call + a **daily quota** — so the strategy is
> **incremental ingestion in slices (chunked), resumable via the raw zone**.
> Blocked only on the key: the user puts it in `COMTRADE_API_KEY` in `.env`.

## Context

COMEX gives the perspective **of Brazil** (MDIC customs). **UN Comtrade** gives
the trade of the **entire world** (every reporting country, bilateral by HS), in US$.
For Embrapa, it adds **competitive and global market context**: the size
of the world castanha/wood market, the ranking of competitors (the gate already
showed: castanha 080121 2022 — Brazil #1 US$12.9M, Bolivia #2, Nigeria #3),
world prices, and a mirror validation of COMEX.

It is the first **global** `flows` source. Naming `gold_comtrade_flows` (the
docs already anticipate it).

## Scope (decided with the user)

- **Products:** mirror COMEX — HS `0801` (castanha) + chapter `44`
  (wood/charcoal). `COMTRADE_CMD_CODES`.
- **Reporters:** all (`all`) — global view.
- **Partners:** bilateral (`partnerCode=all`) — the complete origin→destination
  matrix (who each country buys from/sells to). It is the complete global analog of COMEX.
- **Flows:** export (`X`) + import (`M`).
- **Frequency:** annual (`A`) — Comtrade's complete/authoritative series.
- **Window:** `COMTRADE_START_YEAR..END_YEAR` (default 2000→current).
- US$→BRL deflation reusing `silver_currency` (BCB USD/EUR ∪ ECB CNY).
- Quantity in the **unit-family model (#44)**: `qty`+`qtyUnitCode` →
  `family`/`qty_native`/`qty_base`/`base_unit`; `netWgt` as a parallel kg mass.

## Access & incremental strategy (the key point)

- **Keyed endpoint:** `GET {COMTRADE_API_BASE_URL}/C/A/HS` with header
  `Ocp-Apim-Subscription-Key: <COMTRADE_API_KEY>` + params `reporterCode`,
  `period`, `partnerCode`, `cmdCode`, `flowCode`.
- **Limits (to confirm live with the key):** ~100k records/call + a daily
  call quota (~500/day on the free tier) + ~1 req/s.
- **Chunking:** unit = `(year, flow, commodity group)`. Castanha (0801,
  few HS6) fits in one call; ch. 44 (many HS6 × all-reporters ×
  all-partners) can exceed 100k → split by HS6 or by reporter.
- **Resumable via the raw zone** (which makes the daily quota a non-problem): each
  chunk → archives the JSON at `raw/comtrade/.../<chunk>.parquet` → loads Bronze.
  If the day's quota runs out, it **stops and resumes tomorrow** the chunks not
  yet archived (`raw_provenance`/`list_raw` know what already came in — same as
  COMEX's ETag-skip and the BCB trail). Bronze append + Silver dedup = the
  "join everything in BigQuery".

## Technical design (follows the guide's 11 steps, package `comtrade/`)

1. **`client.py`** — keyed GET (key from config, **never** logged), shared
   retry (`core/http`), parse JSON → DataFrame (columns `data[*]`).
   Chunking helper + (optional) honors `count`/pagination if a chunk exceeds the
   limit.
2. **`pipeline.py`** — two-phase: Phase 1 `sync_raw` per chunk (extracts→`land_raw`),
   resumable; Phase 2 `bronze_one` (reads raw→filters/shapes→Bronze). `run(full,
   from_raw)`. Multi-chunk `ingest comtrade` command (per-chunk events in the
   monitor; continue-on-failure; respects the quota — stops cleanly when it hits the limit).
3. **`config.py`/`.env`** — `COMTRADE_*` (already wired) + `COMTRADE_API_KEY` (secret).
4. **Registries** — `cli.INGESTS`, `doctor.SOURCE_CHECKS` (`_check_comtrade`:
   warns if the key is missing), `doctor.BRONZE_TARGETS`.
5–7. **dbt** — `_sources.yml` (`bronze_comtrade`); `silver_comtrade_flows`
   (dedup by natural key reporter×partner×cmd×year×flow; `safe_numeric`);
   `gold_comtrade_flows` (grain reporter×partner×cmd×year×flow; deflation via
   `silver_currency`; family via `unit_family_conversions`/`product_unit_factors`).
8. **Seeds** — from Comtrade's reference tables (keyless JSON at
   `comtradeapi.un.org/files/v1/app/reference/`): `comtrade_country` (M49→ISO/
   name, for reporter **and** partner), `comtrade_unit` (qtyUnitCode→label+family),
   `comtrade_hs` (HS→description, filtered for 0801+44).
9. **Tests** — `test_comtrade_client.py` (JSON fixture, no network),
   `test_comtrade_pipeline.py` (chunk/resumable + GCP mocks).
10. **Secret** — `COMTRADE_API_KEY` in `.env` (gitignored) + GitHub secret in CI.
11. **Docs** — README/ARCHITECTURE/CONTRIBUTING/CHANGELOG.

## Reuses / is new

- **Reuses:** two-phase + resumable raw zone; US$ deflation via
  `silver_currency`; unit family (#44); the `gold_<source>_flows` pattern;
  shared HTTP retry; dimension seeds (same pattern as COMEX).
- **New:** an **API key** (the project's 1st source secret); the quota-driven
  resumable chunking; Comtrade's own reference tables.

## Tasks / PRs

- [x] Access gate (keyless works, 500-cap; keyed raises the limit). Config
      `COMTRADE_*` + `.env.example` wired.
- [ ] **User:** put `COMTRADE_API_KEY` in `.env`.
- [ ] Validate live (via the app) the key's real limits + keyed shape.
- [ ] **PR-1 (Bronze):** client + chunked/resumable pipeline + config + 3
      registries + tests. `embrapa ingest comtrade` functional.
- [ ] **PR-2 (dbt):** Silver + Gold + reference seeds + tests.
- [ ] **PR-3 (docs).**

## Risks

- **Daily quota** → the complete global backfill takes a few days (resumable by
  design; no loss). Mitigation: fine chunk + `--from-raw` to re-derive without
  re-calling the API.
- **Volume of global bilateral ch. 44** — many HS6 × ~200 reporters × ~200
  partners × years. Mitigation: split by HS6/reporter; clustered Bronze;
  consider incremental in Silver.
- **Mirror ≠ COMEX** — Comtrade uses reported data (revisions, "not
  specified", re-exports); document that it is the reported global base, not
  Brazil-customs.
