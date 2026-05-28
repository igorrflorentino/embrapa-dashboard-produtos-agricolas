"""BigQuery-backed accessor for the Gold layer.

`GoldRepository` is the single data-access surface for every Dash callback.
As per the new architectural requirement, it relies solely on `gold_commodity_matrix`
for all views to ensure a consistent single-table approach.
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
from embrapa_commodities.dashboard.health import health

logger = logging.getLogger(__name__)

Convention = Literal["ipca", "igpm", "igpdi", "yearfx"]
Currency = Literal["BRL", "USD", "EUR", "CNY"]

_T_MATRIX = "gold_commodity_matrix"


@dataclass(frozen=True)
class GoldSnapshot:
    """A single cached Gold-table snapshot."""

    df: pd.DataFrame
    loaded_at: datetime
    rows: int

    @property
    def last_refresh(self) -> datetime | None:
        if "last_refresh" not in self.df.columns or self.df["last_refresh"].isna().all():
            return None
        return self.df["last_refresh"].max().to_pydatetime()


class GoldRepository:
    """Per-table TTL cache over the Gold layer."""

    def __init__(self, ingestion: IngestionSettings, dashboard: DashboardSettings) -> None:
        self._ingestion = ingestion
        self._dashboard = dashboard
        self._lock = threading.Lock()
        self._client: bigquery.Client | None = None
        self._snapshots: dict[str, GoldSnapshot] = {}

    def snapshot(self) -> GoldSnapshot:
        return self._cached(_T_MATRIX)

    def df(self) -> pd.DataFrame:
        return self._cached(_T_MATRIX).df

    def last_refresh(self) -> datetime | None:
        return self._cached(_T_MATRIX).last_refresh

    def loaded_at(self) -> datetime:
        return self._cached(_T_MATRIX).loaded_at

    def year_range(self) -> tuple[int, int]:
        df = self._cached(_T_MATRIX).df
        return int(df["reference_year"].min()), int(df["reference_year"].max())

    def products(self) -> pd.DataFrame:
        df = self._cached(_T_MATRIX).df
        return (
            df[["product_code", "product_description"]]
            .dropna()
            .drop_duplicates()
            .sort_values("product_description")
            .reset_index(drop=True)
        )

    def regions(self) -> pd.DataFrame:
        df = self._cached(_T_MATRIX).df
        return (
            df[["region"]]
            .dropna()
            .drop_duplicates()
            .sort_values("region")
            .reset_index(drop=True)
        )

    def states(self) -> pd.DataFrame:
        df = self._cached(_T_MATRIX).df
        return (
            df[["state_acronym", "state_name", "region"]]
            .dropna(subset=["state_acronym"])
            .drop_duplicates()
            .sort_values("state_name")
            .reset_index(drop=True)
        )

    def cities(self) -> pd.DataFrame:
        df = self._cached(_T_MATRIX).df
        return (
            df[["city_code", "city_name", "state_acronym"]]
            .dropna(subset=["city_code"])
            .drop_duplicates()
            .sort_values("city_name")
            .reset_index(drop=True)
        )

    def _apply_filters(self, df: pd.DataFrame, filters: dict) -> pd.DataFrame:
        """Apply the global filter state to a dataframe."""
        f = filters or {}
        
        # Qualidade
        flags = f.get("quality_flags")
        if flags:
            df = df[df["data_quality_flag"].isin(flags)]
            
        # Período
        y_start = f.get("start_year")
        y_end = f.get("end_year")
        if y_start and y_end:
            df = df[(df["reference_year"] >= int(y_start)) & (df["reference_year"] <= int(y_end))]
            
        # Commodities
        commodities = f.get("commodity")
        if commodities:
            df = df[df["product_code"].isin(commodities)]
            
        # Geografia
        # Note: 'nations' is ignored as we only have BR in PEVS
        regions = f.get("regions")
        if regions:
            df = df[df["region"].isin(regions)]
            
        states = f.get("states")
        if states:
            df = df[df["state_acronym"].isin(states)]
            
        munis = f.get("munis")
        if munis:
            df = df[df["city_code"].isin(munis)]
            
        return df

    def filtered(self, *, filters: dict) -> pd.DataFrame:
        df = self._cached(_T_MATRIX).df
        return self._apply_filters(df, filters)

    def time_series(
        self,
        *,
        filters: dict,
    ) -> pd.DataFrame:
        col = value_column(filters.get("convention", "ipca"), filters.get("currency", "BRL"))
        df = self._cached(_T_MATRIX).df
        df = self._apply_filters(df, filters)

        if df.empty:
            return pd.DataFrame(columns=["reference_year", "value", "quantity"])

        df = df.assign(_qty=df["quantity_tons"].fillna(df["quantity_m3"]))
        return (
            df.groupby("reference_year", as_index=False)
            .agg(value=(col, "sum"), quantity=("_qty", "sum"))
            .sort_values("reference_year")
        )

    def top_states(
        self,
        *,
        filters: dict,
        n: int = 8,
    ) -> pd.DataFrame:
        col = value_column(filters.get("convention", "ipca"), filters.get("currency", "BRL"))
        df = self._cached(_T_MATRIX).df
        
        # Ensure we filter exactly by the end year for "top N" (usually it's for a specific year)
        # But if the view expects an aggregate across all selected years, we use all selected years.
        # Let's filter by the dashboard's standard: usually it's the `end_year`.
        # I'll modify the filters copy to ensure year == end_year.
        f = dict(filters)
        hi_year = int(f.get("end_year", 2024))
        f["start_year"] = hi_year
        f["end_year"] = hi_year
        
        df = self._apply_filters(df, f)

        if df.empty:
            return pd.DataFrame(columns=["state_acronym", "state_name", "region", "value"])

        return (
            df.groupby(["state_acronym", "state_name", "region"], as_index=False)
            .agg(value=(col, "sum"))
            .sort_values("value", ascending=False)
            .head(n)
        )

    def product_mix(
        self,
        *,
        filters: dict,
        top_n: int = 6,
    ) -> pd.DataFrame:
        col = value_column(filters.get("convention", "ipca"), filters.get("currency", "BRL"))
        df = self._cached(_T_MATRIX).df
        
        f = dict(filters)
        hi_year = int(f.get("end_year", 2024))
        f["start_year"] = hi_year
        f["end_year"] = hi_year

        df = self._apply_filters(df, f)

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
        filters: dict,
        n: int = 20,
    ) -> pd.DataFrame:
        col = value_column(filters.get("convention", "ipca"), filters.get("currency", "BRL"))
        df = self._cached(_T_MATRIX).df
        
        f = dict(filters)
        hi_year = int(f.get("end_year", 2024))
        f["start_year"] = hi_year
        f["end_year"] = hi_year

        df = self._apply_filters(df, f)

        if df.empty:
            return pd.DataFrame(
                columns=["city_code", "city_name", "state_acronym", "value", "quantity"]
            )

        df = df.assign(_qty=df["quantity_tons"].fillna(df["quantity_m3"]))
        return (
            df.groupby(["city_code", "city_name", "state_acronym"], as_index=False)
            .agg(value=(col, "sum"), quantity=("_qty", "sum"))
            .sort_values("value", ascending=False)
            .head(n)
        )

    def quality_summary(self, *, filters: dict) -> dict[str, float | int]:
        df = self._cached(_T_MATRIX).df
        # Apply filters except quality flags!
        # Because we want to show the quality distribution for the selected slice.
        f = dict(filters)
        f.pop("quality_flags", None)
        df = self._apply_filters(df, f)
        
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

    def coverage_summary(self, *, filters: dict) -> dict[str, int]:
        df = self._cached(_T_MATRIX).df
        
        f = dict(filters)
        hi_year = int(f.get("end_year", 2024))
        f["start_year"] = hi_year
        f["end_year"] = hi_year
        df = self._apply_filters(df, f)

        return {
            "states": int(df["state_acronym"].nunique()),
            "cities": int(df["city_name"].nunique()),
            "products": int(df["product_code"].nunique()),
        }

    def quality_breakdown_by_year(self, *, filters: dict) -> pd.DataFrame:
        df = self._cached(_T_MATRIX).df
        f = dict(filters)
        f.pop("quality_flags", None)
        df = self._apply_filters(df, f)
        if df.empty:
            return pd.DataFrame(columns=["reference_year", "data_quality_flag", "count"])
        return df.groupby(["reference_year", "data_quality_flag"]).size().reset_index(name="count")

    def quality_by_uf_year(self, *, filters: dict) -> pd.DataFrame:
        df = self._cached(_T_MATRIX).df
        f = dict(filters)
        f.pop("quality_flags", None)
        df = self._apply_filters(df, f)
        if df.empty:
            return pd.DataFrame(columns=["state_acronym", "reference_year", "pct_ok"])
        grouped = df.groupby(["state_acronym", "reference_year"], as_index=False).agg(
            total=("data_quality_flag", "size"),
            ok=("data_quality_flag", lambda s: int((s == "OK").sum())),
        )
        grouped["pct_ok"] = grouped["ok"] / grouped["total"]
        return grouped[["state_acronym", "reference_year", "pct_ok"]]

    def top_quality_problem_products(self, *, filters: dict, top_n: int = 10) -> pd.DataFrame:
        df = self._cached(_T_MATRIX).df
        f = dict(filters)
        f.pop("quality_flags", None)
        df = self._apply_filters(df, f)
        if df.empty:
            return pd.DataFrame(
                columns=["product_code", "product_description", "pct_problem", "rows"]
            )
        grouped = df.groupby(["product_code", "product_description"], as_index=False).agg(
            rows=("data_quality_flag", "size"),
            problem=("data_quality_flag", lambda s: int((s != "OK").sum())),
        )
        grouped["pct_problem"] = grouped["problem"] / grouped["rows"]
        return (
            grouped[["product_code", "product_description", "pct_problem", "rows"]]
            .sort_values("pct_problem", ascending=False)
            .head(top_n)
        )

    def last_refresh_by_uf(self, *, filters: dict) -> pd.DataFrame:
        df = self._cached(_T_MATRIX).df
        df = self._apply_filters(df, filters)
        if df.empty:
            return pd.DataFrame(
                columns=["state_acronym", "state_name", "last_refresh", "days_since"]
            )
        grouped = df.groupby(["state_acronym", "state_name"], as_index=False).agg(
            last_refresh=("last_refresh", "max"),
        )
        ref = grouped["last_refresh"].iloc[0]
        now = pd.Timestamp.now(tz=ref.tz) if getattr(ref, "tz", None) else pd.Timestamp.now()
        grouped["days_since"] = (now - grouped["last_refresh"]).dt.days
        return grouped.sort_values("days_since", ascending=False)

    def regional_aggregate(
        self,
        *,
        filters: dict,
    ) -> pd.DataFrame:
        col = value_column(filters.get("convention", "ipca"), filters.get("currency", "BRL"))
        df = self._cached(_T_MATRIX).df
        df = self._apply_filters(df, filters)
        if df.empty:
            return pd.DataFrame(columns=["region", "reference_year", "value"])
        return df.groupby(["region", "reference_year"], as_index=False).agg(value=(col, "sum"))

    def municipal_breakdown(
        self,
        *,
        filters: dict,
        state_acronym: str,
    ) -> pd.DataFrame:
        col = value_column(filters.get("convention", "ipca"), filters.get("currency", "BRL"))
        df = self._cached(_T_MATRIX).df
        
        f = dict(filters)
        hi_year = int(f.get("end_year", 2024))
        f["start_year"] = hi_year
        f["end_year"] = hi_year
        f["states"] = [state_acronym]  # override to just this state
        
        df = self._apply_filters(df, f)
        if df.empty:
            return pd.DataFrame(columns=["city_code", "city_name", "value"])
        return (
            df.groupby(["city_code", "city_name"], as_index=False)
            .agg(value=(col, "sum"))
            .sort_values("value", ascending=False)
        )

    def _cached(self, table_short: str) -> GoldSnapshot:
        existing = self._snapshots.get(table_short)
        if existing is not None and self._is_fresh(existing):
            return existing
        with self._lock:
            existing = self._snapshots.get(table_short)
            if existing is not None and self._is_fresh(existing):
                return existing
            self._snapshots[table_short] = self._load(table_short)
        return self._snapshots[table_short]

    def _is_fresh(self, snap: GoldSnapshot) -> bool:
        age = (datetime.now() - snap.loaded_at).total_seconds()
        return age < self._dashboard.cache_ttl_seconds

    def _bq(self) -> bigquery.Client:
        if self._client is None:
            self._client = bigquery.Client(
                project=self._ingestion.gcp_project_id,
                location=self._ingestion.bq_location,
                credentials=get_credentials(self._ingestion),
            )
        return self._client

    def _table_fqn(self, table_short: str) -> str:
        return f"{self._ingestion.gcp_project_id}.{self._ingestion.bq_gold_dataset}.{table_short}"

    def _load(self, table_short: str) -> GoldSnapshot:
        fqn = self._table_fqn(table_short)
        client = self._bq()
        health.stage_started("bq_snapshot", detail=f"SELECT * FROM {fqn}")
        started = time.monotonic()
        logger.info("Loading Gold table %s", fqn)
        try:
            df = (
                client.query(f"SELECT * FROM `{fqn}`")
                .result()
                .to_dataframe(create_bqstorage_client=True)
            )
        except Exception as exc:
            health.stage_error("bq_snapshot", str(exc), table=fqn)
            raise
        elapsed = time.monotonic() - started
        logger.info("Gold table %s loaded: %d rows in %.1fs", table_short, len(df), elapsed)
        health.stage_ok(
            "bq_snapshot",
            detail=f"{table_short}: {len(df):,} linhas em {elapsed:.1f}s",
            rows=len(df),
            elapsed_seconds=round(elapsed, 2),
            table=fqn,
        )
        return GoldSnapshot(df=df, loaded_at=datetime.now(), rows=len(df))
