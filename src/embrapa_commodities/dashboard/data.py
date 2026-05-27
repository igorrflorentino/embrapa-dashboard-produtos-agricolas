"""BigQuery-backed accessor for the Gold layer.

`GoldRepository` is the single data-access surface for every Dash callback.
Each public method targets the smallest Gold table that has the grain it
needs, rather than wholesale-loading `gold_commodity_matrix` and filtering
in pandas:

- `time_series`, `top_states`, `product_mix`, `coverage_summary` (and the
  metadata helpers `year_range`, `products`, `states`, `last_refresh`) hit
  the small pre-aggregated tables (`gold_commodity_year_product`,
  `gold_commodity_state_year`, `gold_commodity_state_total_year`).
- `top_cities`, `filtered`, `quality_summary`, `df()` need municipal grain
  or row-level quality flags and therefore hit `gold_commodity_matrix`.

Tables are cached independently with the same TTL (`cache_ttl_seconds`).
The first BQ load fires the `bq_snapshot` health stage; subsequent loads
update it. Thread-safety is one lock shared across all caches —
contention is low (callbacks are short-lived and most reads hit warm cache).
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

# Logical table names. Fixed by dbt model names — not user-configurable.
_T_MATRIX = "gold_commodity_matrix"
_T_STATE_YEAR = "gold_commodity_state_year"
_T_YEAR_PRODUCT = "gold_commodity_year_product"
_T_STATE_TOTAL_YEAR = "gold_commodity_state_total_year"


@dataclass(frozen=True)
class GoldSnapshot:
    """A single cached Gold-table snapshot."""

    df: pd.DataFrame
    loaded_at: datetime
    rows: int

    @property
    def last_refresh(self) -> datetime | None:
        """Max(last_refresh) across all rows — when ingestion last touched the data."""
        if "last_refresh" not in self.df.columns or self.df["last_refresh"].isna().all():
            return None
        return self.df["last_refresh"].max().to_pydatetime()


class GoldRepository:
    """Per-table TTL cache over the Gold layer.

    Same public API as the legacy `GoldStore` so existing callbacks don't
    need to change; the difference is that small queries (time series, top
    states, product mix, coverage) now hit the pre-aggregated tables
    instead of scanning `gold_commodity_matrix` in pandas.
    """

    def __init__(self, ingestion: IngestionSettings, dashboard: DashboardSettings) -> None:
        self._ingestion = ingestion
        self._dashboard = dashboard
        self._lock = threading.Lock()
        self._client: bigquery.Client | None = None
        self._snapshots: dict[str, GoldSnapshot] = {}

    # ── Public API ────────────────────────────────────────────────────────────
    def snapshot(self) -> GoldSnapshot:
        """Snapshot of the matrix (kept for back-compat with code that inspects rows)."""
        return self._cached(_T_MATRIX)

    def df(self) -> pd.DataFrame:
        """Full matrix DataFrame. Use only for raw-data exports or row-level scans."""
        return self._cached(_T_MATRIX).df

    def last_refresh(self) -> datetime | None:
        """When the most recent ingestion run touched the Gold data.

        Read from `gold_commodity_year_product` (smallest table with the
        `last_refresh` column) so this never forces a full matrix load.
        """
        return self._cached(_T_YEAR_PRODUCT).last_refresh

    def loaded_at(self) -> datetime:
        """When the year_product cache was populated (the metadata baseline)."""
        return self._cached(_T_YEAR_PRODUCT).loaded_at

    def year_range(self) -> tuple[int, int]:
        df = self._cached(_T_YEAR_PRODUCT).df
        return int(df["reference_year"].min()), int(df["reference_year"].max())

    def products(self) -> pd.DataFrame:
        """Distinct products with description. Ordered by description."""
        df = self._cached(_T_YEAR_PRODUCT).df
        return (
            df[["product_code", "product_description"]]
            .dropna()
            .drop_duplicates()
            .sort_values("product_description")
            .reset_index(drop=True)
        )

    def states(self) -> pd.DataFrame:
        """Distinct states (UF acronym + name + region)."""
        df = self._cached(_T_STATE_TOTAL_YEAR).df
        return (
            df[["state_acronym", "state_name", "region"]]
            .dropna(subset=["state_acronym"])
            .drop_duplicates()
            .sort_values("state_name")
            .reset_index(drop=True)
        )

    # ── Slicers — small purpose-built frames for charts ───────────────────────
    def filtered(
        self,
        *,
        years: tuple[int, int] | None = None,
        commodity_codes: list[str] | None = None,
        state_acronym: str | None = None,
        flags: list[str] | None = None,
    ) -> pd.DataFrame:
        """Filtered slice of the matrix. Used by the Qualidade drill-down table."""
        df = self._cached(_T_MATRIX).df
        if years:
            lo, hi = years
            df = df[(df["reference_year"] >= lo) & (df["reference_year"] <= hi)]
        if commodity_codes:
            df = df[df["product_code"].isin(commodity_codes)]
        if state_acronym:
            df = df[df["state_acronym"] == state_acronym]
        if flags:
            df = df[df["data_quality_flag"].isin(flags)]
        return df

    def time_series(
        self,
        *,
        convention: Convention,
        currency: Currency,
        years: tuple[int, int] | None = None,
        commodity_codes: list[str] | None = None,
        state_acronym: str | None = None,
    ) -> pd.DataFrame:
        """Year-by-year value + quantity. Routes to the smallest table with the needed grain.

        Filter combinations → source table:
        - no filter / commodities only       → gold_commodity_year_product
        - state only                          → gold_commodity_state_total_year
        - state + commodities                 → gold_commodity_state_year

        Returns columns: reference_year, value, quantity. With multi-commodity
        baskets the row sums across the selected products.
        """
        col = value_column(convention, currency)
        if state_acronym and commodity_codes:
            df = self._cached(_T_STATE_YEAR).df
            df = df[
                (df["state_acronym"] == state_acronym) & (df["product_code"].isin(commodity_codes))
            ]
        elif state_acronym:
            df = self._cached(_T_STATE_TOTAL_YEAR).df
            df = df[df["state_acronym"] == state_acronym]
        elif commodity_codes:
            df = self._cached(_T_YEAR_PRODUCT).df
            df = df[df["product_code"].isin(commodity_codes)]
        else:
            df = self._cached(_T_YEAR_PRODUCT).df

        if years:
            lo, hi = years
            df = df[(df["reference_year"] >= lo) & (df["reference_year"] <= hi)]

        if df.empty:
            return pd.DataFrame(columns=["reference_year", "value", "quantity"])

        # Quantity: prefer tons, fall back to m³. In year_product / state_year
        # for a single product, exactly one is non-null; in state_total_year
        # (sums across all products) both can be non-null and the fillna
        # collapses to "give a single representative number" — semantics are
        # by definition imprecise for multi-commodity baskets.
        df = df.assign(_qty=df["quantity_tons"].fillna(df["quantity_m3"]))
        return (
            df.groupby("reference_year", as_index=False)
            .agg(value=(col, "sum"), quantity=("_qty", "sum"))
            .sort_values("reference_year")
        )

    def top_states(
        self,
        *,
        year: int,
        convention: Convention,
        currency: Currency,
        commodity_codes: list[str] | None = None,
        n: int = 8,
    ) -> pd.DataFrame:
        """Top-N states for a given year by total value.

        Source: state_year when filtering by commodity; state_total_year
        otherwise (avoids summing products in pandas).

        Returns columns: state_acronym, state_name, region, value.
        """
        col = value_column(convention, currency)
        if commodity_codes:
            df = self._cached(_T_STATE_YEAR).df
            df = df[(df["reference_year"] == year) & (df["product_code"].isin(commodity_codes))]
        else:
            df = self._cached(_T_STATE_TOTAL_YEAR).df
            df = df[df["reference_year"] == year]

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
        year: int,
        convention: Convention,
        currency: Currency,
        state_acronym: str | None = None,
        top_n: int = 6,
    ) -> pd.DataFrame:
        """Share-of-value by product for one year.

        Source: gold_commodity_year_product (no state filter) or
        gold_commodity_state_year (with state filter).

        Returns columns: product_code, product_description, value, share.
        """
        col = value_column(convention, currency)
        if state_acronym:
            df = self._cached(_T_STATE_YEAR).df
            df = df[(df["reference_year"] == year) & (df["state_acronym"] == state_acronym)]
        else:
            df = self._cached(_T_YEAR_PRODUCT).df
            df = df[df["reference_year"] == year]

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
        commodity_codes: list[str] | None = None,
        state_acronym: str | None = None,
        n: int = 20,
    ) -> pd.DataFrame:
        """Top-N municipalities. Always queries the matrix — no pre-aggregate has city grain.

        Returns columns: city_code, city_name, state_acronym, value, quantity.
        """
        col = value_column(convention, currency)
        df = self._cached(_T_MATRIX).df
        df = df[df["reference_year"] == year]
        if commodity_codes:
            df = df[df["product_code"].isin(commodity_codes)]
        if state_acronym:
            df = df[df["state_acronym"] == state_acronym]

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

    def quality_summary(self) -> dict[str, float | int]:
        """Row-level flag counts. Needs matrix (the pre-aggregates lose row-level flags)."""
        df = self._cached(_T_MATRIX).df
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
        """Distinct counts of states, cities, and products.

        Cities still need matrix (only table with `city_name`); state and
        product counts come from the small pre-aggregates.
        """
        states_df = self._cached(_T_STATE_TOTAL_YEAR).df
        products_df = self._cached(_T_YEAR_PRODUCT).df
        matrix_df = self._cached(_T_MATRIX).df
        if year is not None:
            states_df = states_df[states_df["reference_year"] == year]
            products_df = products_df[products_df["reference_year"] == year]
            matrix_df = matrix_df[matrix_df["reference_year"] == year]
        return {
            "states": int(states_df["state_acronym"].nunique()),
            "cities": int(matrix_df["city_name"].nunique()),
            "products": int(products_df["product_code"].nunique()),
        }

    # ── Analytical helpers for the new views (Qualidade / Valor e Volume / Geografia) ──
    def quality_breakdown_by_year(self, years: tuple[int, int] | None = None) -> pd.DataFrame:
        """Row count by (year, data_quality_flag). Feeds the Qualidade stacked area."""
        df = self._cached(_T_MATRIX).df
        if years:
            df = df[(df["reference_year"] >= years[0]) & (df["reference_year"] <= years[1])]
        if df.empty:
            return pd.DataFrame(columns=["reference_year", "data_quality_flag", "count"])
        return df.groupby(["reference_year", "data_quality_flag"]).size().reset_index(name="count")

    def quality_by_uf_year(self, years: tuple[int, int] | None = None) -> pd.DataFrame:
        """% of OK rows by (UF, year). Feeds the Qualidade heatmap (diverging green→red)."""
        df = self._cached(_T_MATRIX).df
        if years:
            df = df[(df["reference_year"] >= years[0]) & (df["reference_year"] <= years[1])]
        if df.empty:
            return pd.DataFrame(columns=["state_acronym", "reference_year", "pct_ok"])
        grouped = df.groupby(["state_acronym", "reference_year"], as_index=False).agg(
            total=("data_quality_flag", "size"),
            ok=("data_quality_flag", lambda s: int((s == "OK").sum())),
        )
        grouped["pct_ok"] = grouped["ok"] / grouped["total"]
        return grouped[["state_acronym", "reference_year", "pct_ok"]]

    def top_quality_problem_products(self, *, top_n: int = 10) -> pd.DataFrame:
        """Products with worst data quality (% of non-OK rows). Feeds the Qualidade ranking."""
        df = self._cached(_T_MATRIX).df
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

    def last_refresh_by_uf(self) -> pd.DataFrame:
        """Days since `last_refresh` per UF. Feeds the Qualidade defasagem bar."""
        df = self._cached(_T_STATE_TOTAL_YEAR).df
        if df.empty:
            return pd.DataFrame(
                columns=["state_acronym", "state_name", "last_refresh", "days_since"]
            )
        grouped = df.groupby(["state_acronym", "state_name"], as_index=False).agg(
            last_refresh=("last_refresh", "max"),
        )
        # Use the timestamp tz from the column so we don't mix naive/aware.
        ref = grouped["last_refresh"].iloc[0]
        now = pd.Timestamp.now(tz=ref.tz) if getattr(ref, "tz", None) else pd.Timestamp.now()
        grouped["days_since"] = (now - grouped["last_refresh"]).dt.days
        return grouped.sort_values("days_since", ascending=False)

    def regional_aggregate(
        self,
        *,
        convention: Convention,
        currency: Currency,
        commodity_codes: list[str] | None = None,
        years: tuple[int, int] | None = None,
    ) -> pd.DataFrame:
        """Value by (region, year). Feeds the Geografia heatmap_region_year."""
        col = value_column(convention, currency)
        if commodity_codes:
            df = self._cached(_T_STATE_YEAR).df
            df = df[df["product_code"].isin(commodity_codes)]
        else:
            df = self._cached(_T_STATE_TOTAL_YEAR).df
        if years:
            df = df[(df["reference_year"] >= years[0]) & (df["reference_year"] <= years[1])]
        if df.empty:
            return pd.DataFrame(columns=["region", "reference_year", "value"])
        return df.groupby(["region", "reference_year"], as_index=False).agg(value=(col, "sum"))

    def municipal_breakdown(
        self,
        *,
        state_acronym: str,
        year: int,
        convention: Convention,
        currency: Currency,
        commodity_codes: list[str] | None = None,
    ) -> pd.DataFrame:
        """Value by city within a state. Feeds the Geografia municipal choropleth drill-down."""
        col = value_column(convention, currency)
        df = self._cached(_T_MATRIX).df
        df = df[(df["state_acronym"] == state_acronym) & (df["reference_year"] == year)]
        if commodity_codes:
            df = df[df["product_code"].isin(commodity_codes)]
        if df.empty:
            return pd.DataFrame(columns=["city_code", "city_name", "value"])
        return (
            df.groupby(["city_code", "city_name"], as_index=False)
            .agg(value=(col, "sum"))
            .sort_values("value", ascending=False)
        )

    # ── Internals ─────────────────────────────────────────────────────────────
    def _cached(self, table_short: str) -> GoldSnapshot:
        """Return the cached snapshot of a Gold table, refreshing if stale or absent."""
        existing = self._snapshots.get(table_short)
        if existing is not None and self._is_fresh(existing):
            return existing
        with self._lock:
            existing = self._snapshots.get(table_short)
            if existing is not None and self._is_fresh(existing):  # double-checked
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
        # All four Gold tables fire into the same `bq_snapshot` health stage —
        # users see "BigQuery snapshot loaded" once per fresh-cache miss
        # regardless of which table triggered it; the table name lands in
        # the stage `detail` so the status page is still useful.
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
