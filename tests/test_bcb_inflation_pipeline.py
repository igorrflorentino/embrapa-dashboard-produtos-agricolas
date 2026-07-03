"""Spec-contract tests for the BCB inflation variant.

The shared pipeline behaviour lives in test_bcb_series.py. This file pins only
what makes inflation different from currency: the 12-month overlap (always
rewind a full year), the ``series_name`` label column, and the Bronze schema.
"""

from __future__ import annotations

from datetime import date

from embrapa_dashboard.bcb import inflation as bcb_inflation


def test_delta_overlap_is_twelve_months() -> None:
    """CLAUDE.md documents a 12-month overlap to absorb BCB revisions. Don't drift."""
    assert bcb_inflation.DELTA_OVERLAP_MONTHS == 12


def test_spec_label_column_is_series_name() -> None:
    assert bcb_inflation.SPEC.label_column == "series_name"
    assert bcb_inflation.SPEC.kind == "inflation"


def test_overlap_always_rewinds_a_full_year() -> None:
    """Monthly granularity: regardless of month, the 12-month overlap rewinds one year."""
    assert bcb_inflation.SPEC.overlap_start_year(date(2025, 6, 1)) == 2024
    assert bcb_inflation.SPEC.overlap_start_year(date(2025, 1, 1)) == 2024
    assert bcb_inflation.SPEC.overlap_start_year(date(2025, 12, 31)) == 2024


def test_schema_carries_series_name() -> None:
    names = {f.name for f in bcb_inflation.BRONZE_SCHEMA}
    assert names == {
        "series_code",
        "series_name",
        "reference_date_str",
        "value_str",
        "ingestion_timestamp",
    }
