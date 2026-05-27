"""Dashboard runtime settings.

Extends the ingestion-side `Settings` class so we share `GCP_PROJECT_ID`,
`BQ_GOLD_DATASET`, `BQ_LOCATION`, and the impersonation helper. Adds a
single dashboard-only knob (cache TTL). Gold table names are hard-coded
in `GoldRepository` — they are fixed by the dbt model names and there is
no value in making them runtime-configurable.
"""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from embrapa_commodities.config import Settings as IngestionSettings
from embrapa_commodities.config import get_credentials as _get_credentials


class DashboardSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    cache_ttl_seconds: int = Field(
        default=21_600,  # 6 hours
        description="How long each cached Gold-table snapshot is reused before re-querying BQ.",
    )


def get_settings() -> tuple[IngestionSettings, DashboardSettings]:
    """Return (shared, dashboard-only) settings.

    Pydantic-settings reads the same `.env` and process env for both.
    """
    return IngestionSettings(), DashboardSettings()  # type: ignore[call-arg]


get_credentials = _get_credentials  # re-exported for callers who only import this module
