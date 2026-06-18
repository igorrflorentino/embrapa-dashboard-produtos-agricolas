# COMEX source — `gold_comex_flows`

> **Status:** **IMPLEMENTED & IN PROD.** PR-1/2/3 shipped; the real
> Bronze→Silver→Gold→tests path is validated against the user's BQ, and the
> 1997-2026 full historical backfill (multi-GB) has been ingested and
> materialized into `gold`. Recorded findings: IMP = EXP + `VL_FRETE`/`VL_SEGURO`
> (schema-union); host omits the TLS intermediate (chain in `comex/_ca.py`);
> delta by `(flow,year)` + continue-on-failure absorbed a transient BrokenPipe on
> the re-run.

## Context

The backend is prepared for multi-source (registries `cli.INGESTS`,
`doctor.SOURCE_CHECKS`/`BRONZE_TARGETS`, primitives `core/http.py` +
`core/raw.py`, guide `docs/adding_a_data_source.md`). Today there is only one
*production* source (IBGE PEVS → `gold_pevs_production`) enriched with BCB
FX/inflation.

Adding **COMEX (foreign trade, MDIC)** is the biggest value multiplier
for Embrapa's scientific audience: it crosses **production × trade × FX ×
inflation** for the same product, and validates the `gold_<source>_<form>`
design (the `flows` form — origin→destination flow — did not exist yet).

## Scope

**Included (decided with the user):**

- **Data source:** Comex Stat bulk CSV — `EXP_<ano>.csv` / `IMP_<ano>.csv`
  at `https://balanca.economia.gov.br/balanca/bd/comexstat-bd/ncm/`
  (`;`-separated, latin-1, one file per year per flow, history since 1997).
  **Do NOT use the JSON API** (see Risks).
- **Flow:** export **and** import (`flow` column).
- **Products:** castanha-do-pará/brasil (NCM `08012100` with shell, `08012200`
  shelled) + **the entire chapter 44** (wood and charcoal — any NCM
  whose first 2 digits are `44`).
- **Gold grain:** month × NCM × country × UF → `gold_comex_flows` (`flows` form).
- Monetary deflation reusing the shared Silver tables
  (`silver_bcb_inflation`, `silver_bcb_currency`) via `ref()`, applying the 4
  project conventions (`val_yearfx_*`, `val_real_{ipca,igpm,igpdi}_*`) over
  `VL_FOB` (US$).

**Excluded:**

- Pre-aggregations (state-year, national): aggregate at query time via
  `GROUP BY` — ONE comprehensive table per source.
- Forcing COMEX into `gold_pevs_production` (incompatible grains).
- Frontend / Looker (consumes Gold afterward, out of this scope).

## Technical Design

Following the 11 steps in `docs/adding_a_data_source.md`. Package
`src/embrapa_commodities/comex/`.

**1. Client (`comex/client.py`) — CSV downloader, not JSON API.**
- Download via **GET** of the yearly files (tens/hundreds of MB) — **stream
  to a temporary disk file**, not drain-in-memory (a large file legitimately
  takes minutes; re-evaluate/relax the slow-byte deadline in `core/http.py`,
  which was designed for small responses).
- `ComexRequestError` / `ComexTransientError(SourceTransientError)` errors to
  inherit the shared retry.
- Parsing with pandas (`sep=";"`, `encoding="latin-1"`, `dtype=str`), filtering
  locally: `CO_NCM in ncm_codes OR CO_NCM[:2] in chapter_codes`.
- Source columns **CONFIRMED live** (2026-05-30):
  - **EXP (11 cols):**
    `CO_ANO;CO_MES;CO_NCM;CO_UNID;CO_PAIS;SG_UF_NCM;CO_VIA;CO_URF;QT_ESTAT;KG_LIQUIDO;VL_FOB`
  - **IMP (13 cols):** the 11 from EXP **+ `VL_FRETE;VL_SEGURO`**.
  - Mixed quoting: text columns wrapped in `"`, numeric ones (`QT_ESTAT` onward)
    unquoted — `pandas(sep=";", quotechar='"', dtype=str)` reads both cases.
  - `CO_NCM` 8 digits zero-padded and quoted; `CO_MES` 2 digits
    zero-padded; `CO_PAIS` is a **numeric code** (e.g. `160`, `764` — needs the
    `country_iso` seed for a name); `SG_UF_NCM` is the 2-letter UF acronym.
  - **The filter must be column-precise on `CO_NCM`/`CO_NCM[:2]`** — a substring
    grep `"44` on the raw line falsely matches `CO_PAIS=445`, etc.

**2. Pipeline (`comex/pipeline.py`) — its own `run()`** (shape ≠ SGS, so it does
not use `bcb.series`):
- **Delta by `(flow, year)`** (the implemented form — diverges from the original
  draft "year lookup in Bronze"): it enumerates the entire window on each run and
  re-extracts a `(flow, year)` only when the source's **ETag/Last-Modified/Content-Length**
  changes (`_raw_is_current`) — catching revisions of **any** year, not just
  the current one. The Bronze load (Phase 2) is gated by a `bronze_loaded_at`
  marker in the raw metadata (`mark_raw_bronze_loaded`/
  `raw_bronze_loaded`), not by a year lookup in Bronze.
- The extract→raw→load tail goes through the two-phase raw zone (`core/raw.py`:
  `land_raw_file`/`download_raw`/`raw_provenance`) — do not rewrite.
- Bronze: all columns STRING + `ingestion_timestamp`; natural key
  `(flow, CO_ANO, CO_MES, CO_NCM, CO_PAIS, SG_UF_NCM)`.
- **EXP+IMP schema-union:** Bronze is ONE table with the 13 IMP columns;
  export rows write `VL_FRETE`/`VL_SEGURO` as NULL. The client must
  reindex the DataFrame to the column superset before the load (do not rely
  on per-flow order/count). The `flow` column (`export`/`import`) is added
  by the pipeline; it does not come from the CSV.

**3. Config (`config.py` + `.env.example`):** `BQ_BRONZE_COMEX_DATASET`,
`BQ_BRONZE_COMEX_FLOWS_TABLE`, `COMEX_CSV_BASE_URL`, `COMEX_FLOWS`
(`export,import`), `COMEX_NCM_CODES` (CODE:LABEL), `COMEX_CHAPTER_CODES`
(CODE:LABEL), `COMEX_START_YEAR=1997`, `COMEX_END_YEAR`. Properties mirroring
`*_map` / `*_list` with validation (reuse `_parse_code_label`).

**4. Registries:** `cli.INGESTS` += spec; hand-maintained `ingest comex` command
(multi-chunk per year → copy the structure of `ingest_ibge_batch`, which emits
`chunk_*` per year, instead of the single-shot `pipeline_run`); `doctor.SOURCE_CHECKS`
+= `_check_comex`; `doctor.BRONZE_TARGETS` += COMEX entry.

**5–7. dbt:** `_sources.yml` (`bronze_comex` block); `silver_comex_flows.sql`
(dedup via `qualify row_number()` on the natural key; `safe_numeric()` on
`VL_FOB`/`KG_LIQUIDO`); `gold_comex_flows.sql` (grain month×NCM×country×UF + deflation
CTEs via `ref(silver_bcb_*)`). Tests in `_silver.yml` / `_gold.yml`.

**8. Seeds (optional):** `hs_ncm.csv` (NCM→readable label) if we want names
instead of codes; `country_iso.csv` to resolve `CO_PAIS`.

**9. Python tests:** `test_comex_client.py` (local CSV fixture, no network —
parsing + ch.44/NCM filter); `test_comex_pipeline.py` (delta by year + GCP
mocks, copy the pattern of `test_bcb_series.py`).

**10. Secret:** none — public source, no auth. **But:** the host
`balanca.economia.gov.br` serves only the leaf cert and **omits the TLS
intermediate** (Sectigo R36) — `requests`/certifi fails with `CERTIFICATE_VERIFY_FAILED`
(`curl` gets by because it fetches the intermediate via AIA / the OS trust store).
Without it the real ingestion does not work anywhere (incl. CI Linux/Cloud Run).
Mitigation **without disabling verification**: the public intermediate is
vendored in `comex/_ca.py` and the client appends it to the `certifi` bundle at
runtime (`verify=`). Re-vendor it if the host rotates the CA (valid until 2036).

**11. Docs:** README/ARCHITECTURE (Bronze+Consumption boxes), CONTRIBUTING (`comex`
scope), CHANGELOG (`[Unreleased]/Added`).

## Tasks

- [x] **Validate CSV live** (local, 2026-05-30): headers of
      `EXP_{1997,2023,2026}` / `IMP_{1997,2023,2026}` confirmed via range
      requests; `;` separator + latin-1 + mixed quoting; castanha
      (`08012100`/`08012200`) and ch.44 (`44072920`/`44091000`) rows present in
      EXP_2023. **Gate cleared.** Finding: IMP = EXP + `VL_FRETE`/`VL_SEGURO`.
- [x] Review/approve this plan in light of the confirmed shape.
- [x] **PR-1 (end-to-end Bronze):** `comex/` package (`client.py` stream-to-
      disk + column-precise filter, `pipeline.py` delta by `(flow, year)`,
      `_ca.py` TLS chain), config + properties, 3 registries, multi-chunk `ingest
      comex` command, `_check_comex` in doctor. `test_comex_client.py` +
      `test_comex_pipeline.py` (274 tests green). `embrapa ingest comex`
      functional — validated live: EXP_2026 downloaded and filtered (6157 rows,
      only ch. 08+44, 126 castanha). **Pending:** run the real `ingest comex`
      against the user's BQ (needs ADC + project).
- [x] **PR-2 (dbt):** `_sources.yml` (`bronze_comex` block);
      `silver_comex_flows.sql` (dedup on the full source grain via `qualify`,
      `safe_numeric` on VL_FOB/KG/QT/freight/insurance); `gold_comex_flows.sql`
      (grain flow×month×NCM×country×UF; monthly deflation: VL_FOB US$ → BRL at the
      month's FX → IPCA/IGPM/IGPDI index → today, reconverted at the current FX;
      `state_name`/`region` via macro, nulls for the special UF). Tests in
      `_silver.yml`/`_gold.yml`. `dbt parse` + `dbt compile` green. **Pending:**
      `dbt build` in dev (depends on the real COMEX Bronze — same gate as ingest).
      Dimension seeds **DONE** (separate PR): `comex_unit` /
      `comex_country` / `comex_ncm` from the MDIC auxiliary tables
      (`bd/tabelas/`), with `ncm_description`/`country_name`/`stat_unit` in Gold.
- [x] **PR-3 (docs):** README (pipeline diagram + sources + CLI),
      ARCHITECTURE (flow boxes, `comex/` structure, Silver/Gold/Consumption),
      CONTRIBUTING (`comex` scope), CHANGELOG (`[Unreleased]/Added`).

## Risks & Mitigations

- **JSON API dropped for integrity.** The POST `/general` API
  **silently returned the aggregated Brazil total when the filter came in
  malformed, with HTTP 200** — a risk of ingesting wrong data with no error. So
  we use the bulk CSV (authoritative raw base, filtered and inspected locally).
- **Host blocked in the web environment.** `balanca.economia.gov.br` fails on
  the Claude Code on the web proxy (`upstream connect error ... CERTIFICATE_VERIFY_FAILED`,
  host outside the allowlist). **Mitigation:** develop on local Claude Code
  (network open). Alternative: adjust the environment's network policy
  (code.claude.com/docs) + recreate the session.
- **Large files.** Stream-to-disk + early filter; re-evaluate the slow-byte
  deadline in `core/http.py` (designed for small payloads).
- **Volume of the entire chapter 44.** Many NCMs × countries × UFs × months ×
  decades. Mitigation: cluster Bronze by natural key; partition by
  `ingestion_timestamp`; consider incremental in Silver (like
  `silver_ibge_pevs`).

## Acceptance Criteria

- `uv run pytest` green (includes `test_comex_*`); `ruff check`/`format` clean.
- `embrapa ingest comex` lands Bronze; `embrapa doctor` includes the `comex`
  check; `ingest --help` lists the subcommand.
- `dbt build --select silver_comex_flows+ gold_comex_flows+` green in dev.
- `embrapa backup-gold` cites `gold_comex_flows` automatically (introspection).
- Data sanity: rows match month×NCM×country×UF; `VL_FOB` deflated in the 4
  conventions; castanha + ch.44 present, other NCMs absent.
