# Raw Zone Architecture — two-phase ingestion for ALL sources

> **Status:** **IMPLEMENTED** (branch `feat/raw-zone-architecture`, on top of
> `feat/comex-flows`/PR #38). Two-phase standardized across COMEX, IBGE and BCB;
> `core/raw.py` + `--from-raw` in all sources; `core/bronze.land_and_load`
> removed. 285 tests green. Pending: live validation against the user's BQ.

## Principle

Every source follows **two** explicit phases:

1. **Extract → Raw.** Fetch the source's extract *verbatim* and archive it in GCS at
   `raw/<source>/<dataset>/<basename>.parquet`, with **provenance metadata**
   (source URL, ETag/Last-Modified when available, `fetched_at`, `rows`).
2. **Raw → Bronze.** Read the raw Parquet back from GCS, apply the
   source-specific filter/shaping and load the **Bronze** BigQuery table.

From there on the medallion (Silver → Gold, dbt) is **unchanged**.

**Why.** Decouple *fetch* from *load*: re-filtering, changing rules, or
re-deriving Bronze never hits the source again — only a real data revision
(detected via provenance, e.g. HTTP ETag) triggers a re-fetch. Gains:
homogeneity across sources, simple maintenance, adding a product/rule becomes
cheap (re-run only Phase 2, reading from GCS, no internet), resilience to
source unavailability, and scientific lineage/reproducibility.

## GCS layout

```
gs://<bucket>/raw/<source>/<dataset>/<basename>.parquet   (verbatim + metadata)
```

- The current filtered `landing/` prefix is **retired** — there were 2 artifacts
  (filtered parquet in GCS + Bronze in BQ); now there is 1 (raw in GCS) and the
  Bronze BQ derives from it via `load_table_from_dataframe`.
- Lifecycle: `raw/` gets the same rules as `landing/` (Nearline@30 →
  Coldline@90 → Archive@365, never deletes — audit trail).

## Shared contract — `core/raw.py`

| Function | Role |
|---|---|
| `raw_object_name(settings, source, dataset, basename)` | canonical path |
| `land_raw(df, *, settings, storage_client, source, dataset, basename, provenance)` | Phase 1: writes verbatim parquet + metadata; returns gs URI |
| `read_raw(storage_client, *, settings, source, dataset, basename)` | Phase 2: reads the raw parquet → DataFrame |
| `raw_provenance(storage_client, *, settings, source, dataset, basename)` | provenance metadata (None if absent) — basis for the freshness check |

The BQ tail (Phase 2) uses the existing `gcp/bigquery.load_dataframe`. The old
`core/bronze.land_and_load` (which coupled filtered-GCS + BQ) is
removed/retired as the sources migrate.

## Per-source map

| Source | Phase 1 (raw) | Phase 2 (bronze) | Freshness |
|---|---|---|---|
| **COMEX** | download CSV → **complete** Parquet (all NCM) → raw | reads raw → filters NCM/chapter → Bronze | **ETag/Last-Modified** per file (HEAD) — re-extracts only if changed; catches revisions of any year |
| **IBGE PEVS** | SIDRA fetch (already filtered by the query) → Parquet → raw | reads raw → (typed STRING) → Bronze | re-extracts the window/chunks per run (POST without ETag) |
| **BCB** (infl/FX) | SGS fetch per series/window → Parquet → raw | reads raw → column projection → Bronze | delta by `max(reference_date)` (overlap), as today |

## CLI

- `embrapa ingest <source>` → P1 + P2 (extract→raw→bronze).
- `embrapa ingest <source> --from-raw` → only P2 (reprocesses Bronze from raw, **no
  internet**) — to re-filter / apply new rules / change products.
- `embrapa ingest <source> --full` → P1 + P2 ignoring the freshness check
  (re-extracts everything, even without a source revision). (There is no `--raw-only` flag.)

## Implementation order (tests green at each step)

1. `core/raw.py` + tests + `raw/` lifecycle + `gcs_raw_prefix` in config. **(ref.)**
2. **COMEX** migrated (reference) — the client separates extract-raw from filter;
   2-phase pipeline; ETag; CLI; tests.
3. **IBGE** migrated.
4. **BCB** (`series.py` + inflation/currency) migrated.
5. doctor (optional raw check), docs (README/ARCHITECTURE/CHANGELOG).

dbt unchanged (the Bronze tables/sources stay identical).

## Risks & notes

- **Memory in COMEX:** the complete raw is per (flow, year) (~7 MB Parquet each),
  so Phase 2 reads one file at a time and filters — without loading 1 GB at once.
- **Asymmetry with the old form:** IBGE/BCB already filter via API parameters,
  so their raw == what the filtered landing used to be (~same content); the
  structural gain is the homogeneity + reprocessing without re-fetch.
- **Migration of existing buckets:** old data in `landing/` stays
  (lifecycle kept); the new flow writes to `raw/`. No destructive migration.
