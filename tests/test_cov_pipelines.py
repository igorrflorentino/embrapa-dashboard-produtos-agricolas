"""Coverage tests for the three IBGE Bronze pipelines' --from-raw empty-window guard.

Each of ``pipeline`` (PEVS), ``pam_pipeline``, and ``ppm_pipeline`` has the SAME
two-line branch: when ``run(..., from_raw=True)`` is asked to rebuild Bronze from
the archived raw trail but ``list_raw`` finds NOTHING archived for the dataset, it
emits a warning and returns ``""`` (no read_raw / no load). These tests drive that
empty-archive path for all three (lines pipeline.py 273-274, pam_pipeline.py
246-247, ppm_pipeline.py 277-278).

Mocking style mirrors the existing test_ibge_pipeline / test_pam_pipeline /
test_ppm_pipeline ``--from-raw`` tests: patch storage/bigquery clients,
ensure_dataset, and list_raw at the module path; assert the downstream
read_raw/load_dataframe were never reached.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from embrapa_dashboard.config import Settings
from embrapa_dashboard.ibge import pam_pipeline, ppm_pipeline
from embrapa_dashboard.ibge import pipeline as ibge_pipeline


@pytest.fixture
def ibge_settings() -> Settings:
    return Settings(
        gcp_project_id="test-project",
        gcs_bucket="test-bucket",
        ibge_start_year=2020,
        ibge_end_year=2020,
        ibge_product_codes="3405",
        _env_file=None,
    )  # type: ignore[call-arg]


@pytest.fixture
def pam_settings() -> Settings:
    return Settings(
        gcp_project_id="test-project",
        gcs_bucket="test-bucket",
        pam_start_year=2020,
        pam_end_year=2020,
        pam_product_codes="40124",
        _env_file=None,
    )  # type: ignore[call-arg]


@pytest.fixture
def ppm_settings() -> Settings:
    return Settings(
        gcp_project_id="test-project",
        gcs_bucket="test-bucket",
        ppm_start_year=2020,
        ppm_end_year=2020,
        ppm_herd_product_codes="2670",
        ppm_animal_product_codes="2682",
        _env_file=None,
    )  # type: ignore[call-arg]


# ─── PEVS (pipeline.py 273-274) ──────────────────────────────────────────────
def test_ibge_run_from_raw_empty_archive_returns_empty(ibge_settings: Settings) -> None:
    """--from-raw with NO archived raw → warn + return "" (lines 272-274), never
    touching read_raw / load_dataframe."""
    with (
        patch("embrapa_dashboard.ibge.pipeline.fetch_sidra_dataframe") as fetch,
        patch("embrapa_dashboard.ibge.pipeline.storage.Client"),
        patch("embrapa_dashboard.ibge.pipeline.bigquery.Client"),
        patch("embrapa_dashboard.ibge.pipeline.ensure_dataset"),
        patch("embrapa_dashboard.ibge.pipeline.list_raw", return_value=[]),
        patch("embrapa_dashboard.ibge.pipeline._order_by_fetched_at") as order,
        patch("embrapa_dashboard.ibge.pipeline.read_raw") as read_raw,
        patch("embrapa_dashboard.ibge.pipeline.load_dataframe") as load,
    ):
        destination = ibge_pipeline.run(ibge_settings, from_raw=True)

    assert destination == ""
    fetch.assert_not_called()
    order.assert_not_called()  # short-circuited before the replay ordering
    read_raw.assert_not_called()
    load.assert_not_called()


# ─── PAM (pam_pipeline.py 246-247) ───────────────────────────────────────────
def test_pam_run_from_raw_empty_archive_returns_empty(pam_settings: Settings) -> None:
    """PAM --from-raw with an empty raw archive → warn + return "" (lines 245-247)."""
    with (
        patch("embrapa_dashboard.ibge.pam_pipeline.fetch_sidra_dataframe") as fetch,
        patch("embrapa_dashboard.ibge.pam_pipeline.storage.Client"),
        patch("embrapa_dashboard.ibge.pam_pipeline.bigquery.Client"),
        patch("embrapa_dashboard.ibge.pam_pipeline.ensure_dataset"),
        patch("embrapa_dashboard.ibge.pam_pipeline.list_raw", return_value=[]),
        patch("embrapa_dashboard.ibge.pam_pipeline._order_by_fetched_at") as order,
        patch("embrapa_dashboard.ibge.pam_pipeline.read_raw") as read_raw,
        patch("embrapa_dashboard.ibge.pam_pipeline.load_dataframe") as load,
    ):
        destination = pam_pipeline.run(pam_settings, from_raw=True)

    assert destination == ""
    fetch.assert_not_called()
    order.assert_not_called()
    read_raw.assert_not_called()
    load.assert_not_called()


# ─── PPM (ppm_pipeline.py 277-278, via _run_spec per table) ──────────────────
def test_ppm_run_from_raw_empty_archive_returns_empty(ppm_settings: Settings) -> None:
    """PPM --from-raw with an empty raw archive for BOTH specs → each ``_run_spec``
    warns + returns "" (lines 276-278), so ``run`` yields no destinations → ""."""
    P = "embrapa_dashboard.ibge.ppm_pipeline"
    with (
        patch(f"{P}.fetch_sidra_dataframe") as fetch,
        patch(f"{P}.storage.Client"),
        patch(f"{P}.bigquery.Client"),
        patch(f"{P}.ensure_dataset"),
        patch(f"{P}.list_raw", return_value=[]),
        patch(f"{P}._order_by_fetched_at") as order,
        patch(f"{P}.read_raw") as read_raw,
        patch(f"{P}.load_dataframe") as load,
    ):
        destination = ppm_pipeline.run(ppm_settings, from_raw=True)

    assert destination == ""
    fetch.assert_not_called()
    order.assert_not_called()
    read_raw.assert_not_called()
    load.assert_not_called()
