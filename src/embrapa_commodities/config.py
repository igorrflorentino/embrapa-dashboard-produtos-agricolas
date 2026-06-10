"""Runtime settings loaded from environment / .env file."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _current_year() -> int:
    return datetime.now(UTC).year


def _parse_code_label(raw: str) -> dict[str, str]:
    """Parse 'CODE:LABEL,CODE:LABEL' into {code: label}.

    Whitespace around items is ignored. Duplicate codes raise ValueError.
    """
    result: dict[str, str] = {}
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        if ":" not in item:
            raise ValueError(f"Expected 'CODE:LABEL', got {item!r}")
        code, label = item.split(":", 1)
        code, label = code.strip(), label.strip()
        if not code or not label:
            raise ValueError(f"Empty code or label in {item!r}")
        if code in result:
            raise ValueError(f"Duplicate series code {code!r}")
        result[code] = label
    return result


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ─── GCP / GCS ────────────────────────────────────────────────────────────
    gcp_project_id: str = Field(..., description="GCP project that owns BigQuery + GCS")
    gcs_bucket: str | None = Field(default=None, description="Defaults to <project>-datalake")
    gcs_landing_prefix: str = Field(default="landing")
    # Verbatim source extracts (two-phase ingestion): raw/<source>/<dataset>/...
    # Bronze derives from this; re-filtering never re-hits the source.
    gcs_raw_prefix: str = Field(default="raw")
    # "US" multi-region is a portable fallback; .env.example and
    # dbt/profiles.yml use the project's actual region (us-central1). Keep
    # BQ_LOCATION set so this default never silently disagrees with them.
    bq_location: str = Field(default="US")
    gcp_impersonation_sa: str | None = Field(
        default=None,
        description="SA email to impersonate via ADC (enterprise mode). "
        "Set to sa-secret-reader-prod@<project>.iam.gserviceaccount.com.",
    )

    # ─── BigQuery dataset / table names ───────────────────────────────────────
    bq_bronze_ibge_dataset: str = Field(default="bronze_ibge")
    bq_bronze_bcb_dataset: str = Field(default="bronze_bcb")
    bq_bronze_comex_dataset: str = Field(default="bronze_comex")
    bq_bronze_ibge_table: str = Field(default="sidra_t289_raw")
    bq_bronze_bcb_inflation_table: str = Field(default="inflation_series_raw")
    bq_bronze_bcb_currency_table: str = Field(default="currency_series_raw")
    bq_bronze_comex_flows_table: str = Field(default="comex_flows_raw")
    bq_silver_dataset: str = Field(default="silver")  # consumed by dbt, not Python runtime
    # Un-prefixed name. dbt's generate_schema_name macro adds the dev prefix
    # (dev → dbt_dev_gold, prod → gold), so this must stay "gold". Also what
    # `backup-gold` / doctor read.
    bq_gold_dataset: str = Field(default="gold")

    # ─── IBGE ─────────────────────────────────────────────────────────────────
    ibge_table_id: str = Field(default="289")
    ibge_classification_id: str = Field(default="193")
    ibge_product_codes: str = Field(default="3405,3435,3450")
    ibge_start_year: int | None = Field(
        default=None,
        description="None requires user to run `embrapa discover ibge-periods` first.",
    )
    ibge_end_year: int = Field(default_factory=_current_year)
    # Delta overlap (years). A routine `ingest ibge` (and `ingest all`) re-fetches
    # only from (latest Bronze year − this) forward — absorbing PEVS revisions of
    # recent years and picking up a newly published year — instead of re-pulling
    # the whole 1986→today window (a huge SIDRA request that can blow the slow-byte
    # deadline on an unattended Cloud Run job). `--full` ignores this; a cold
    # Bronze table also falls back to the full configured window.
    ibge_delta_overlap_years: int = Field(default=1)

    # ─── BCB ──────────────────────────────────────────────────────────────────
    bcb_inflation_series: str = Field(default="433:IPCA,189:IGPM,190:IGPDI")
    # The 3 series codes the Gold pivot wires into val_real_{ipca,igpm,igpdi}_*.
    # dbt reads each via env_var(); each MUST appear in bcb_inflation_series or
    # the matching Gold columns silently come out NULL. `embrapa doctor`
    # validates this (see doctor._check_inflation_pivot_codes).
    bcb_inflation_series_ipca_code: str = Field(default="433")
    bcb_inflation_series_igpm_code: str = Field(default="189")
    bcb_inflation_series_igpdi_code: str = Field(default="190")
    # Daily PTAX "venda" rates (BRL per foreign unit): SGS 1 = USD, 21619 = EUR.
    # The Gold deflation averages these per year (PEVS) / per month (COMEX), so a
    # daily series is the most accurate base. The previous 3694/4393/20542 were
    # wrong: 3694 is annual, and 4393/20542 are not BRL-per-unit FX at all.
    # CNY is intentionally absent — the BCB publishes no BRL/CNY (nor USD/CNY)
    # series in SGS or PTAX, so it would need an external source (see CHANGELOG).
    bcb_currency_series: str = Field(default="1:USD,21619:EUR")
    bcb_start_year: int = Field(default=1980)
    bcb_end_year: int = Field(default_factory=_current_year)

    # ─── COMEX (MDIC Comex Stat bulk CSV) ─────────────────────────────────────
    comex_csv_base_url: str = Field(
        default="https://balanca.economia.gov.br/balanca/bd/comexstat-bd/ncm"
    )
    # Which flows to ingest — closed domain {export, import}, mapped to the
    # EXP_/IMP_ file prefixes by the client.
    comex_flows: str = Field(default="export,import")
    # CODE:LABEL of full 8-digit NCMs to keep regardless of chapter.
    comex_ncm_codes: str = Field(default="08012100:castanha_com_casca,08012200:castanha_sem_casca")
    # CODE:LABEL of 2-digit HS chapters to keep wholesale (44 = wood & charcoal).
    comex_chapter_codes: str = Field(default="44:madeira_carvao")
    comex_start_year: int = Field(default=1997)
    comex_end_year: int = Field(default_factory=_current_year)

    # ─── UN COMTRADE (global trade, keyed API) ────────────────────────────────
    # Free registered subscription key — read from .env, never committed. Empty
    # means "not configured" (doctor warns; ingest errors with a clear message).
    comtrade_api_key: str = Field(default="")
    comtrade_api_base_url: str = Field(default="https://comtradeapi.un.org/data/v1/get")
    bq_bronze_comtrade_dataset: str = Field(default="bronze_comtrade")
    bq_bronze_comtrade_flows_table: str = Field(default="comtrade_flows_raw")
    # HS code prefixes to keep (CODE:LABEL) — mirror the COMEX scope so Brazil can
    # be compared against the world for the same commodities. These are the SCOPE
    # codes; the ingest expands them to their 6-digit HS leaves (Comtrade returns
    # data only at the requested code level).
    comtrade_cmd_codes: str = Field(default="0801:castanha,44:madeira_carvao")
    # Flow codes (UN Comtrade flowCode): X=export, M=import, RX=re-export,
    # RM=re-import. The four primary regimes the frontend's `flow` filter exposes.
    comtrade_flows: str = Field(default="X,M,RX,RM")
    # Reporters to pull ("all" = every reporting country, expanded by the client
    # from the Comtrade Reporters reference; or a comma list of M49 codes). The
    # keyed endpoint rejects "all" literally, so the client enumerates and batches.
    comtrade_reporters: str = Field(default="all")
    # ISO-A3 of the reporter treated as "home" (Brazil) when the serving layer
    # splits Brazil's own trade from the world total — COMTRADE ingests ALL
    # reporters, so this filter is applied at query time (serving), never at
    # ingestion. Backs crossSeries: exp_value/imp_value filter to this reporter;
    # world_exp sums over all reporters.
    comtrade_brazil_iso: str = Field(default="BRA")
    # DEV window — kept small/recent on purpose while building and testing (avoid
    # the massive full backfill). Lower COMTRADE_START_YEAR for older history once
    # the pipeline is validated; raise COMTRADE_END_YEAR past 2023 when ready.
    comtrade_start_year: int = Field(default=2022)
    comtrade_end_year: int = Field(default=2023)

    # ─── Cold-storage backup ──────────────────────────────────────────────────
    # `embrapa doctor` warns when the most recent gs://${GCS_BUCKET}/backups/
    # snapshot is older than this. Default 14d matches a typical bi-weekly
    # release cadence — bump it for projects that ship monthly.
    backup_staleness_days: int = Field(default=14)

    # `embrapa backup-gold` lists the Gold dataset and snapshots every table
    # whose name starts with this prefix. "gold_" matches every dbt-produced
    # Gold table while excluding ad-hoc / temp exploration tables.
    backup_gold_prefix: str = Field(default="gold_")

    # ─── Serving layer / dashboard data access ────────────────────────────────
    # Pre-aggregated marts + the SCD2 curation view the stateless Dash app reads
    # via Pushdown Computing. Un-prefixed name (dbt's generate_schema_name adds
    # the dev prefix: dev → dbt_dev_serving, prod → serving). Point the deployed
    # dashboard at "serving"; a developer testing against dev data sets it to
    # "dbt_dev_serving".
    bq_serving_dataset: str = Field(default="serving")
    # Append-only researcher curation inputs (written by the dashboard, not dbt).
    bq_research_inputs_dataset: str = Field(default="research_inputs")
    bq_curation_log_table: str = Field(default="commodity_processing_stage_log")
    # Per-CODE industrialization log — the finer-grained companion to the commodity
    # processing-stage log. Backs dim_code_industrialization_scd2 + the value-added
    # analysis (COMEX exports split by the curated bruta/processada level).
    bq_code_industrialization_log_table: str = Field(default="code_industrialization_log")
    # Append-only log of the (customs procedure × flow) → economic-purpose market
    # curation (consumo/processamento). Backs the market-nature analysis.
    bq_flow_market_log_table: str = Field(default="flow_market_log")

    # ─── Cache (flask-caching) ────────────────────────────────────────────────
    # SimpleCache (per-instance) scales to N Cloud Run instances for free: marts
    # converge within cache_default_timeout (nightly data), and the curation read
    # uses a SHORT TTL (cache_classification_timeout) so cross-instance staleness
    # is bounded — eventual consistency, no shared Redis. CACHE_TYPE=RedisCache +
    # CACHE_REDIS_URL is optional, only for *instant* cross-instance consistency
    # (see src/embrapa_commodities/serving/cache.py).
    cache_type: str = Field(default="SimpleCache")
    cache_default_timeout: int = Field(default=600, description="Seconds; mart read TTL.")
    # Short TTL for the curation classification read; gateway.py reads the same
    # env var (CACHE_CLASSIFICATION_TIMEOUT) at decoration time. Keep it small —
    # it's the bound on cross-instance staleness that makes multi-instance free.
    cache_classification_timeout: int = Field(default=30, description="Seconds; curation read TTL.")
    cache_redis_url: str | None = Field(default=None)
    # Author email used when the IAP header is absent (local dev only). Leave
    # unset in production — IAP always supplies the header, and an unset fallback
    # makes an un-attributed write fail loudly instead of writing 'unknown'.
    curation_dev_author: str | None = Field(default=None)
    # IAP backend audience for verifying the signed X-Goog-IAP-JWT-Assertion.
    # When SET (production behind IAP), the curation author is taken from the
    # cryptographically verified JWT, not the spoofable plaintext email header —
    # a direct request to the backend can no longer forge the audit author. Format
    # for Cloud Run behind a load balancer:
    # /projects/<PROJECT_NUMBER>/global/backendServices/<BACKEND_SERVICE_ID>.
    # Leave UNSET for local dev (no IAP): the plaintext header + curation_dev_author
    # path is used. See src/embrapa_commodities/serving/iap.py.
    iap_audience: str | None = Field(default=None)

    @model_validator(mode="after")
    def _default_bucket(self) -> Settings:
        if not self.gcs_bucket:
            self.gcs_bucket = f"{self.gcp_project_id}-datalake"
        return self

    # ─── Helpers ──────────────────────────────────────────────────────────────
    @property
    def product_codes(self) -> list[str]:
        codes = [c.strip() for c in self.ibge_product_codes.split(",") if c.strip()]
        if not codes:
            raise ValueError("IBGE_PRODUCT_CODES is empty.")
        return codes

    @property
    def inflation_series_map(self) -> dict[str, str]:
        return _parse_code_label(self.bcb_inflation_series)

    @property
    def inflation_pivot_codes(self) -> dict[str, str]:
        """{label: code} the Gold val_real_* pivot uses; each must be a key in
        ``inflation_series_map`` or the corresponding column comes out NULL."""
        return {
            "IPCA": self.bcb_inflation_series_ipca_code,
            "IGPM": self.bcb_inflation_series_igpm_code,
            "IGPDI": self.bcb_inflation_series_igpdi_code,
        }

    @property
    def currency_series_map(self) -> dict[str, str]:
        return _parse_code_label(self.bcb_currency_series)

    @property
    def comex_flows_list(self) -> list[str]:
        """Validated flow names. Each must be 'export' or 'import' (file prefixes)."""
        allowed = {"export", "import"}
        flows = [f.strip().lower() for f in self.comex_flows.split(",") if f.strip()]
        if not flows:
            raise ValueError("COMEX_FLOWS is empty.")
        invalid = [f for f in flows if f not in allowed]
        if invalid:
            raise ValueError(
                f"COMEX_FLOWS has invalid flow(s) {invalid}; allowed: {sorted(allowed)}"
            )
        return flows

    @property
    def comex_ncm_map(self) -> dict[str, str]:
        return _parse_code_label(self.comex_ncm_codes)

    @property
    def comex_chapter_map(self) -> dict[str, str]:
        return _parse_code_label(self.comex_chapter_codes)

    @property
    def comtrade_cmd_map(self) -> dict[str, str]:
        return _parse_code_label(self.comtrade_cmd_codes)

    @property
    def comtrade_flows_list(self) -> list[str]:
        """Validated UN Comtrade flow codes: X=export, M=import, RX=re-export,
        RM=re-import (the four primary regimes)."""
        allowed = {"X", "M", "RX", "RM"}
        flows = [f.strip().upper() for f in self.comtrade_flows.split(",") if f.strip()]
        if not flows:
            raise ValueError("COMTRADE_FLOWS is empty.")
        invalid = [f for f in flows if f not in allowed]
        if invalid:
            raise ValueError(f"COMTRADE_FLOWS has invalid flow(s) {invalid}; allowed: X, M, RX, RM")
        return flows


def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


def get_credentials(settings: Settings | None = None):
    """Return GCP credentials, impersonating GCP_IMPERSONATION_SA when set.

    Returns None to let the google-cloud libraries fall back to ADC directly.
    """
    import google.auth
    from google.auth import impersonated_credentials

    cfg = settings or get_settings()
    if not cfg.gcp_impersonation_sa:
        return None

    source_creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    return impersonated_credentials.Credentials(
        source_credentials=source_creds,
        target_principal=cfg.gcp_impersonation_sa,
        target_scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )
