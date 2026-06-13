"""Unit tests for the generic BCB SGS series pipeline (bcb/series.py).

The inflation and currency variants share all of this behaviour — it is tested
once here, parametrized over both specs. Per-variant knobs (overlap rule, label
column, schema) are pinned in test_bcb_inflation_pipeline.py /
test_bcb_currency_pipeline.py.
"""

from __future__ import annotations

import re
from datetime import date
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from embrapa_commodities.bcb import series as bcb_series
from embrapa_commodities.bcb.currency import SPEC as CURRENCY_SPEC
from embrapa_commodities.bcb.inflation import SPEC as INFLATION_SPEC
from embrapa_commodities.config import Settings


@pytest.fixture
def settings() -> Settings:
    return Settings(
        gcp_project_id="test-project",
        gcs_bucket="test-bucket",
        bcb_start_year=1980,
        bcb_end_year=2026,
        bcb_inflation_series="433:IPCA,189:IGPM,190:IGPDI",
        bcb_currency_series="3694:USD,4393:EUR",
        _env_file=None,
    )  # type: ignore[call-arg]


# (spec, label_column, expected codes, expected labels, kind)
SPECS = [
    pytest.param(
        INFLATION_SPEC,
        "series_name",
        {"433", "189", "190"},
        {"IPCA", "IGPM", "IGPDI"},
        id="inflation",
    ),
    pytest.param(CURRENCY_SPEC, "currency", {"3694", "4393"}, {"USD", "EUR"}, id="currency"),
]

FAKE = pd.DataFrame({"data": ["01/01/2020"], "valor": ["1.23"]})


# ─── effective_start_year ────────────────────────────────────────────────────
@pytest.mark.parametrize("spec, label, codes, labels", SPECS)
def test_effective_start_year_returns_configured_when_table_empty(
    spec, label, codes, labels
) -> None:
    bq = MagicMock()
    with patch("embrapa_commodities.bcb.series.latest_reference_date", return_value=None) as latest:
        result = bcb_series.effective_start_year(spec, bq, "proj.ds.tbl", "433", 1980)
    latest.assert_called_once_with(bq, "proj.ds.tbl", "433")
    assert result == 1980


@pytest.mark.parametrize("spec, label, codes, labels", SPECS)
def test_effective_start_year_honours_configured_floor(spec, label, codes, labels) -> None:
    """If the user set the start after the last load, the configured floor wins."""
    bq = MagicMock()
    with patch(
        "embrapa_commodities.bcb.series.latest_reference_date", return_value=date(1995, 6, 1)
    ):
        result = bcb_series.effective_start_year(spec, bq, "proj.ds.tbl", "433", 2010)
    assert result == 2010


# ─── extract: full vs delta ──────────────────────────────────────────────────
@pytest.mark.parametrize("spec, label, codes, labels", SPECS)
def test_extract_full_mode_skips_lookup_and_uses_configured_start(
    spec, label, codes, labels, settings
) -> None:
    bq = MagicMock()
    with (
        patch("embrapa_commodities.bcb.series.latest_reference_date") as latest,
        patch("embrapa_commodities.bcb.series.fetch_series", return_value=FAKE) as fetch,
    ):
        df = bcb_series.extract(spec, settings, bq, "proj.ds.tbl", full=True)
    latest.assert_not_called()
    assert not df.empty
    requested = {call.args[0] for call in fetch.call_args_list}
    assert requested == codes
    for call in fetch.call_args_list:
        assert call.args[1] == settings.bcb_start_year


@pytest.mark.parametrize("spec, label, codes, labels", SPECS)
def test_extract_delta_mode_anchors_per_series(spec, label, codes, labels, settings) -> None:
    bq = MagicMock()
    with (
        patch(
            "embrapa_commodities.bcb.series.latest_reference_date", return_value=date(2025, 6, 1)
        ) as latest,
        patch("embrapa_commodities.bcb.series.fetch_series", return_value=FAKE),
    ):
        bcb_series.extract(spec, settings, bq, "proj.ds.tbl", full=False)
    assert latest.call_count == len(codes)


@pytest.mark.parametrize("spec, label, codes, labels", SPECS)
def test_extract_delta_empty_returns_empty_df(spec, label, codes, labels, settings) -> None:
    bq = MagicMock()
    with (
        patch(
            "embrapa_commodities.bcb.series.latest_reference_date", return_value=date(2026, 1, 1)
        ),
        patch("embrapa_commodities.bcb.series.fetch_series", return_value=pd.DataFrame()),
    ):
        df = bcb_series.extract(spec, settings, bq, "proj.ds.tbl", full=False)
    assert df.empty


@pytest.mark.parametrize("spec, label, codes, labels", SPECS)
def test_extract_full_empty_raises(spec, label, codes, labels, settings) -> None:
    bq = MagicMock()
    with (
        patch("embrapa_commodities.bcb.series.latest_reference_date"),
        patch("embrapa_commodities.bcb.series.fetch_series", return_value=pd.DataFrame()),
        pytest.raises(RuntimeError, match=f"no {spec.kind} data"),
    ):
        bcb_series.extract(spec, settings, bq, "proj.ds.tbl", full=True)


@pytest.mark.parametrize("spec, label, codes, labels", SPECS)
def test_extract_canonical_columns_and_labels(spec, label, codes, labels, settings) -> None:
    bq = MagicMock()
    with (
        patch(
            "embrapa_commodities.bcb.series.latest_reference_date", return_value=date(2025, 1, 1)
        ),
        patch("embrapa_commodities.bcb.series.fetch_series", return_value=FAKE),
    ):
        df = bcb_series.extract(spec, settings, bq, "proj.ds.tbl", full=False)
    # Verbatim: extract no longer stamps ingestion_timestamp (Phase 2 does).
    assert set(df.columns) == {"series_code", label, "reference_date_str", "value_str"}
    assert set(df[label]) == labels


@pytest.mark.parametrize("spec, label, codes, labels", SPECS)
def test_extract_full_raises_when_any_single_series_is_empty(
    spec, label, codes, labels, settings
) -> None:
    """--full must not silently absorb one misconfigured/empty series just because
    the others returned data: the run would report success while that series stays
    permanently absent from Bronze (its Gold columns NULL with no error anywhere).
    The raise must name the offending series."""
    empty_code = sorted(codes)[0]

    def fetch(code, start, end):
        return pd.DataFrame() if code == empty_code else FAKE.copy()

    bq = MagicMock()
    with (
        patch("embrapa_commodities.bcb.series.latest_reference_date"),
        patch("embrapa_commodities.bcb.series.fetch_series", side_effect=fetch),
        pytest.raises(RuntimeError, match=empty_code),
    ):
        bcb_series.extract(spec, settings, bq, "proj.ds.tbl", full=True)


@pytest.mark.parametrize("spec, label, codes, labels", SPECS)
def test_extract_delta_keeps_going_when_one_series_is_empty(
    spec, label, codes, labels, settings
) -> None:
    """In delta mode a single empty series just means 'nothing new' for it — the
    other series' rows still flow through."""
    empty_code = sorted(codes)[0]

    def fetch(code, start, end):
        return pd.DataFrame() if code == empty_code else FAKE.copy()

    bq = MagicMock()
    with (
        patch(
            "embrapa_commodities.bcb.series.latest_reference_date", return_value=date(2025, 1, 1)
        ),
        patch("embrapa_commodities.bcb.series.fetch_series", side_effect=fetch),
    ):
        df = bcb_series.extract(spec, settings, bq, "proj.ds.tbl", full=False)
    assert set(df["series_code"]) == codes - {empty_code}


def test_extract_empty_series_config_raises(settings) -> None:
    settings.bcb_inflation_series = "  "
    bq = MagicMock()
    with pytest.raises(RuntimeError, match="empty"):
        bcb_series.extract(INFLATION_SPEC, settings, bq, "proj.ds.tbl", full=True)


# ─── run() (two-phase) ───────────────────────────────────────────────────────
def _raw_roundtrip():
    """land_raw captures the verbatim frame; read_raw replays it (Phase 1→2)."""
    holder: dict = {}

    def land(df, **_kw):
        holder["df"] = df
        return "gs://test/raw"

    def read(*_a, **_kw):
        return holder["df"].copy()

    return land, read


@pytest.mark.parametrize("spec, label, codes, labels", SPECS)
def test_run_delta_short_circuits_with_no_new_data(spec, label, codes, labels, settings) -> None:
    with (
        patch("embrapa_commodities.bcb.series.bigquery.Client"),
        patch("embrapa_commodities.bcb.series.storage.Client"),
        patch("embrapa_commodities.bcb.series.ensure_dataset"),
        patch(
            "embrapa_commodities.bcb.series.latest_reference_date", return_value=date(2026, 1, 1)
        ),
        patch("embrapa_commodities.bcb.series.fetch_series", return_value=pd.DataFrame()),
        patch("embrapa_commodities.bcb.series.land_raw") as land,
        patch("embrapa_commodities.bcb.series.load_dataframe") as load,
    ):
        destination = bcb_series.run(spec, settings, full=False)
    assert destination == ""
    land.assert_not_called()
    load.assert_not_called()


@pytest.mark.parametrize("spec, label, codes, labels", SPECS)
def test_run_full_passes_partition_and_cluster_keys(spec, label, codes, labels, settings) -> None:
    land, read = _raw_roundtrip()
    with (
        patch("embrapa_commodities.bcb.series.bigquery.Client"),
        patch("embrapa_commodities.bcb.series.storage.Client"),
        patch("embrapa_commodities.bcb.series.ensure_dataset"),
        patch("embrapa_commodities.bcb.series.fetch_series", return_value=FAKE),
        patch("embrapa_commodities.bcb.series.land_raw", side_effect=land),
        patch("embrapa_commodities.bcb.series.read_raw", side_effect=read),
        patch("embrapa_commodities.bcb.series.load_dataframe") as load,
    ):
        bcb_series.run(spec, settings, full=True)
    load_kwargs = load.call_args.kwargs
    assert load_kwargs["time_partitioning_field"] == "ingestion_timestamp"
    assert load_kwargs["clustering_fields"] == ["series_code", "reference_date_str"]


@pytest.mark.parametrize("spec, label, codes, labels", SPECS)
def test_run_raw_basename_is_runstamped_under_kind(spec, label, codes, labels, settings) -> None:
    land, read = _raw_roundtrip()
    with (
        patch("embrapa_commodities.bcb.series.bigquery.Client"),
        patch("embrapa_commodities.bcb.series.storage.Client"),
        patch("embrapa_commodities.bcb.series.ensure_dataset"),
        patch("embrapa_commodities.bcb.series.fetch_series", return_value=FAKE),
        patch("embrapa_commodities.bcb.series.land_raw", side_effect=land) as land_mock,
        patch("embrapa_commodities.bcb.series.read_raw", side_effect=read),
        patch("embrapa_commodities.bcb.series.load_dataframe"),
    ):
        bcb_series.run(spec, settings, full=True)
    kwargs = land_mock.call_args.kwargs
    assert kwargs["source"] == "bcb"
    assert kwargs["dataset"] == spec.kind
    # Run-stamped, append-only trail: <run_ts>_<from>_<to>, where <from>/<to> are
    # the actual data years archived (FAKE holds a single 01/01/2020 reading), not
    # the configured 1980-2026 window.
    assert re.fullmatch(r"\d{8}T\d{6}Z_2020_2020", kwargs["basename"])
    assert kwargs["provenance"]["window"] == "2020-2020"
