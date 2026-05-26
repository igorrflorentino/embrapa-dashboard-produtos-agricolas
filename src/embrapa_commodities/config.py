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
    bq_location: str = Field(default="US")
    gcp_impersonation_sa: str | None = Field(
        default=None,
        description="SA email to impersonate via ADC (enterprise mode). "
        "Set to sa-secret-reader-prod@<project>.iam.gserviceaccount.com.",
    )

    # ─── BigQuery dataset / table names ───────────────────────────────────────
    bq_bronze_ibge_dataset: str = Field(default="bronze_ibge")
    bq_bronze_bcb_dataset: str = Field(default="bronze_bcb")
    bq_bronze_ibge_table: str = Field(default="sidra_t289_raw")
    bq_bronze_bcb_inflation_table: str = Field(default="inflation_series_raw")
    bq_bronze_bcb_currency_table: str = Field(default="currency_series_raw")
    bq_silver_dataset: str = Field(default="silver")
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

    # ─── BCB ──────────────────────────────────────────────────────────────────
    bcb_inflation_series: str = Field(default="433:IPCA,189:IGPM,190:IGPDI")
    bcb_currency_series: str = Field(default="3694:USD,4393:EUR,20542:CNY")
    bcb_start_year: int = Field(default=1980)
    bcb_end_year: int = Field(default_factory=_current_year)

    # ─── Cold-storage backup ──────────────────────────────────────────────────
    # `embrapa doctor` warns when the most recent gs://${GCS_BUCKET}/backups/
    # snapshot is older than this. Default 14d matches a typical bi-weekly
    # release cadence — bump it for projects that ship monthly.
    backup_staleness_days: int = Field(default=14)

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
    def currency_series_map(self) -> dict[str, str]:
        return _parse_code_label(self.bcb_currency_series)


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
