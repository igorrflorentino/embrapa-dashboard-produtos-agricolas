"""Spec-contract tests for the BCB currency variant.

The shared pipeline behaviour lives in test_bcb_series.py. This file pins only
what makes currency different from inflation: the 30-day overlap (rewind a year
only when the last load is in January), the ``currency`` label column, and the
Bronze schema.
"""

from __future__ import annotations

from datetime import date

from embrapa_dashboard.bcb import currency as bcb_currency


def test_spec_label_column_is_currency() -> None:
    assert bcb_currency.SPEC.label_column == "currency"
    assert bcb_currency.SPEC.kind == "currency"


def test_overlap_rewinds_a_year_only_in_january() -> None:
    """Daily granularity, 30-day overlap: mid-year stays in the same calendar year;
    a January last-load rewinds to the prior year (30 days back crosses the boundary)."""
    assert bcb_currency.SPEC.overlap_start_year(date(2025, 6, 15)) == 2025
    assert bcb_currency.SPEC.overlap_start_year(date(2025, 12, 31)) == 2025
    assert bcb_currency.SPEC.overlap_start_year(date(2025, 1, 15)) == 2024
    assert bcb_currency.SPEC.overlap_start_year(date(2025, 1, 1)) == 2024


def test_schema_carries_currency() -> None:
    names = {f.name for f in bcb_currency.BRONZE_SCHEMA}
    assert names == {
        "series_code",
        "currency",
        "reference_date_str",
        "value_str",
        "ingestion_timestamp",
    }
