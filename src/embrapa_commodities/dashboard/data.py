"""In-memory snapshot of `gold.gold_commodity_matrix` with TTL refresh.

A single `GoldStore` is instantiated lazily by `app.py` and shared across all
Dash callbacks. The first request triggers a `SELECT * FROM gold` (small —
one row per year/state/city/product), pandas holds it, and subsequent
callbacks filter in-memory. The store re-queries BQ when `cache_ttl_seconds`
has elapsed.

All filtering / aggregation helpers return small DataFrames purpose-built for
a specific chart. They never mutate the cached snapshot.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

import pandas as pd
from google.cloud import bigquery

from embrapa_commodities.config import Settings as IngestionSettings
from embrapa_commodities.dashboard.config import DashboardSettings, get_credentials
from embrapa_commodities.dashboard.formatting import value_column

logger = logging.getLogger(__name__)

Convention = Literal["ipca", "igpm", "yearfx"]
Currency = Literal["BRL", "USD", "EUR", "CNY"]


@dataclass(frozen=True)
class GoldSnapshot:
    df: pd.DataFrame
    loaded_at: datetime
    rows: int

    @property
    def last_refresh(self) -> datetime | None:
        """Max(last_refresh) across all rows — i.e. when ingestion last touched the table."""
        if "last_refresh" not in self.df.columns or self.df["last_refresh"].isna().all():
            return None
        return self.df["last_refresh"].max().to_pydatetime()


class GoldStore:
    """Thread-safe TTL cache around `gold.gold_commodity_matrix`."""

    def __init__(self, ingestion: IngestionSettings, dashboard: DashboardSettings) -> None:
        self._ingestion = ingestion
        self._dashboard = dashboard
        self._snapshot: GoldSnapshot | None = None
        self._lock = threading.Lock()
        self._table_fqn = (
            f"{ingestion.gcp_project_id}.{ingestion.bq_gold_dataset}.{dashboard.bq_gold_table}"
        )

    # ── Public API ────────────────────────────────────────────────────────────
    def snapshot(self) -> GoldSnapshot:
        """Return the cached snapshot, refreshing if stale or absent."""
        if self._is_fresh():
            return self._snapshot  # type: ignore[return-value]
        with self._lock:
            if self._is_fresh():  # double-checked locking
                return self._snapshot  # type: ignore[return-value]
            self._snapshot = self._load()
        return self._snapshot

    def df(self) -> pd.DataFrame:
        return self.snapshot().df

    def last_refresh(self) -> datetime | None:
        return self.snapshot().last_refresh

    def loaded_at(self) -> datetime:
        return self.snapshot().loaded_at

    def year_range(self) -> tuple[int, int]:
        df = self.df()
        return int(df["reference_year"].min()), int(df["reference_year"].max())

    def products(self) -> pd.DataFrame:
        """Distinct products with description. Ordered by description."""
        df = self.df()
        out = (
            df[["product_code", "product_description"]]
            .dropna()
            .drop_duplicates()
            .sort_values("product_description")
            .reset_index(drop=True)
        )
        return out

    def states(self) -> pd.DataFrame:
        """Distinct states (UF acronym + name + region)."""
        df = self.df()
        out = (
            df[["state_acronym", "state_name", "region"]]
            .dropna(subset=["state_acronym"])
            .drop_duplicates()
            .sort_values("state_name")
            .reset_index(drop=True)
        )
        return out

    # ── Slicers — small purpose-built frames for charts ───────────────────────
    def filtered(
        self,
        *,
        years: tuple[int, int] | None = None,
        product_code: str | None = None,
        state_acronym: str | None = None,
        only_ok: bool = False,
    ) -> pd.DataFrame:
        df = self.df()
        if years:
            lo, hi = years
            df = df[(df["reference_year"] >= lo) & (df["reference_year"] <= hi)]
        if product_code:
            df = df[df["product_code"] == product_code]
        if state_acronym:
            df = df[df["state_acronym"] == state_acronym]
        if only_ok:
            df = df[df["data_quality_flag"] == "OK"]
        return df

    def time_series(
        self,
        *,
        convention: Convention,
        currency: Currency,
        years: tuple[int, int] | None = None,
        product_code: str | None = None,
        state_acronym: str | None = None,
    ) -> pd.DataFrame:
        """Returns columns: reference_year, value, quantity."""
        col = value_column(convention, currency)
        df = self.filtered(years=years, product_code=product_code, state_acronym=state_acronym)
        if df.empty:
            return pd.DataFrame(columns=["reference_year", "value", "quantity"])
        # Quantity: prefer tons, fall back to m³ (they are exclusive per product).
        df = df.assign(
            _qty=df["quantity_tons"].fillna(df["quantity_m3"]),
        )
        grouped = (
            df.groupby("reference_year", as_index=False)
            .agg(value=(col, "sum"), quantity=("_qty", "sum"))
            .sort_values("reference_year")
        )
        return grouped

    def top_states(
        self,
        *,
        year: int,
        convention: Convention,
        currency: Currency,
        product_code: str | None = None,
        n: int = 8,
    ) -> pd.DataFrame:
        """Top-N states for a given year by total value. Cols: state_acronym, state_name, value."""
        col = value_column(convention, currency)
        df = self.filtered(years=(year, year), product_code=product_code)
        if df.empty:
            return pd.DataFrame(columns=["state_acronym", "state_name", "value"])
        grouped = (
            df.groupby(["state_acronym", "state_name"], as_index=False)
            .agg(value=(col, "sum"))
            .sort_values("value", ascending=False)
            .head(n)
        )
        return grouped

    def product_mix(
        self,
        *,
        year: int,
        convention: Convention,
        currency: Currency,
        state_acronym: str | None = None,
        top_n: int = 6,
    ) -> pd.DataFrame:
        """Share-of-value by product for one year.

        Returns columns: product_code, product_description, value, share.
        """
        col = value_column(convention, currency)
        df = self.filtered(years=(year, year), state_acronym=state_acronym)
        if df.empty:
            return pd.DataFrame(columns=["product_code", "product_description", "value", "share"])
        grouped = (
            df.groupby(["product_code", "product_description"], as_index=False)
            .agg(value=(col, "sum"))
            .sort_values("value", ascending=False)
        )
        total = grouped["value"].sum()
        if total <= 0:
            grouped["share"] = 0.0
            return grouped
        if len(grouped) > top_n:
            head = grouped.head(top_n)
            tail_value = grouped.tail(len(grouped) - top_n)["value"].sum()
            other = pd.DataFrame(
                [
                    {
                        "product_code": "_other",
                        "product_description": "Outros",
                        "value": tail_value,
                    }
                ]
            )
            grouped = pd.concat([head, other], ignore_index=True)
        grouped["share"] = grouped["value"] / total
        return grouped

    def top_cities(
        self,
        *,
        year: int,
        convention: Convention,
        currency: Currency,
        product_code: str | None = None,
        state_acronym: str | None = None,
        n: int = 20,
    ) -> pd.DataFrame:
        col = value_column(convention, currency)
        df = self.filtered(
            years=(year, year),
            product_code=product_code,
            state_acronym=state_acronym,
        )
        if df.empty:
            return pd.DataFrame(columns=["city_name", "state_acronym", "value", "quantity"])
        df = df.assign(_qty=df["quantity_tons"].fillna(df["quantity_m3"]))
        grouped = (
            df.groupby(["city_name", "state_acronym"], as_index=False)
            .agg(value=(col, "sum"), quantity=("_qty", "sum"))
            .sort_values("value", ascending=False)
            .head(n)
        )
        return grouped

    def quality_summary(self) -> dict[str, float | int]:
        df = self.df()
        if df.empty:
            return {"pct_ok": 0.0, "rows_total": 0}
        flag = df["data_quality_flag"]
        rows_total = len(df)
        rows_ok = int((flag == "OK").sum())
        pct_ok = round(100.0 * rows_ok / rows_total, 1) if rows_total else 0.0
        return {
            "pct_ok": pct_ok,
            "rows_total": rows_total,
            "rows_ok": rows_ok,
            "rows_missing_value": int((flag == "MISSING_VALUE").sum()),
            "rows_missing_quantity": int((flag == "MISSING_QUANTITY").sum()),
            "rows_incomplete": int((flag == "INCOMPLETE").sum()),
        }

    def coverage_summary(self, year: int | None = None) -> dict[str, int]:
        df = self.df()
        if year is not None:
            df = df[df["reference_year"] == year]
        return {
            "states": int(df["state_acronym"].nunique()),
            "cities": int(df["city_name"].nunique()),
            "products": int(df["product_code"].nunique()),
        }

    # ── Internals ─────────────────────────────────────────────────────────────
    def _is_fresh(self) -> bool:
        if self._snapshot is None:
            return False
        age = (datetime.now() - self._snapshot.loaded_at).total_seconds()
        return age < self._dashboard.cache_ttl_seconds

    def _load(self) -> GoldSnapshot:
        creds = get_credentials(self._ingestion)
        client = bigquery.Client(
            project=self._ingestion.gcp_project_id,
            location=self._ingestion.bq_location,
            credentials=creds,
        )
        started = time.monotonic()
        logger.info("Loading snapshot from %s", self._table_fqn)
        query = f"SELECT * FROM `{self._table_fqn}`"
        # Use the BigQuery Storage API for the row download — binary Arrow
        # stream, 5–10x faster than the default REST/JSON path for tables
        # of this size. Requires roles/bigquery.readSessionUser on the SA.
        df = client.query(query).result().to_dataframe(create_bqstorage_client=True)
        elapsed = time.monotonic() - started
        logger.info("Gold snapshot loaded: %d rows in %.1fs", len(df), elapsed)
        return GoldSnapshot(df=df, loaded_at=datetime.now(), rows=len(df))
