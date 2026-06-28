"""Coverage tests for config.py validator/parse error branches + __init__ version fallback.

Targets the uncovered ``raise ValueError`` branches in the PPM/PAM/COMEX/COMTRADE
list-property getters (each raises when the parsed list is empty or — for the flow
properties — contains an invalid entry), and the ``PackageNotFoundError`` fallback
in ``embrapa_commodities.__init__``.

Mirrors tests/test_config.py: build Settings without picking up the developer-local
.env via ``_env_file=None``, then read the property to trigger the branch.
"""

from __future__ import annotations

import importlib
from unittest.mock import patch

import pytest

from embrapa_commodities.config import Settings


def _make_settings(**overrides: object) -> Settings:
    """Build a Settings instance without picking up the user's local .env."""
    base = {"gcp_project_id": "test-project", "_env_file": None}
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


# ─── PAM variable codes (line 474) ──────────────────────────────────────────
def test_pam_variable_codes_list_raises_when_empty() -> None:
    s = _make_settings(pam_variable_codes="  , ,")
    with pytest.raises(ValueError, match="PAM_VARIABLE_CODES is empty"):
        _ = s.pam_variable_codes_list


def test_pam_variable_codes_list_parses_and_strips() -> None:
    s = _make_settings(pam_variable_codes=" 8331 ,216, 214 ")
    assert s.pam_variable_codes_list == ["8331", "216", "214"]


# ─── PPM herd product codes (line 483) ──────────────────────────────────────
def test_ppm_herd_product_codes_list_raises_when_empty() -> None:
    s = _make_settings(ppm_herd_product_codes=",,")
    with pytest.raises(ValueError, match="PPM_HERD_PRODUCT_CODES is empty"):
        _ = s.ppm_herd_product_codes_list


def test_ppm_herd_product_codes_list_parses() -> None:
    s = _make_settings(ppm_herd_product_codes="2670, 2675")
    assert s.ppm_herd_product_codes_list == ["2670", "2675"]


# ─── PPM animal product codes (line 491) ────────────────────────────────────
def test_ppm_animal_product_codes_list_raises_when_empty() -> None:
    s = _make_settings(ppm_animal_product_codes="   ")
    with pytest.raises(ValueError, match="PPM_ANIMAL_PRODUCT_CODES is empty"):
        _ = s.ppm_animal_product_codes_list


def test_ppm_animal_product_codes_list_parses() -> None:
    s = _make_settings(ppm_animal_product_codes="2682,2685")
    assert s.ppm_animal_product_codes_list == ["2682", "2685"]


# ─── PPM herd variable codes (lines 497-500) ────────────────────────────────
def test_ppm_herd_variable_codes_list_raises_when_empty() -> None:
    s = _make_settings(ppm_herd_variable_codes=", ,")
    with pytest.raises(ValueError, match="PPM_HERD_VARIABLE_CODES is empty"):
        _ = s.ppm_herd_variable_codes_list


def test_ppm_herd_variable_codes_list_parses() -> None:
    s = _make_settings(ppm_herd_variable_codes=" 105 ")
    assert s.ppm_herd_variable_codes_list == ["105"]


# ─── PPM animal variable codes (lines 505-508) ──────────────────────────────
def test_ppm_animal_variable_codes_list_raises_when_empty() -> None:
    s = _make_settings(ppm_animal_variable_codes="")
    with pytest.raises(ValueError, match="PPM_ANIMAL_VARIABLE_CODES is empty"):
        _ = s.ppm_animal_variable_codes_list


def test_ppm_animal_variable_codes_list_parses() -> None:
    s = _make_settings(ppm_animal_variable_codes="106, 215")
    assert s.ppm_animal_variable_codes_list == ["106", "215"]


# ─── COMEX flows (lines 534 empty + 537 invalid) ────────────────────────────
def test_comex_flows_list_raises_when_empty() -> None:
    s = _make_settings(comex_flows="  , ,")
    with pytest.raises(ValueError, match="COMEX_FLOWS is empty"):
        _ = s.comex_flows_list


def test_comex_flows_list_raises_on_invalid_flow() -> None:
    s = _make_settings(comex_flows="export,reexport")
    with pytest.raises(ValueError, match="COMEX_FLOWS has invalid flow"):
        _ = s.comex_flows_list


def test_comex_flows_list_normalizes_case() -> None:
    s = _make_settings(comex_flows="EXPORT, Import")
    assert s.comex_flows_list == ["export", "import"]


# ─── COMTRADE flows (line 566 empty + the invalid branch) ───────────────────
def test_comtrade_flows_list_raises_when_empty() -> None:
    s = _make_settings(comtrade_flows=", ,")
    with pytest.raises(ValueError, match="COMTRADE_FLOWS is empty"):
        _ = s.comtrade_flows_list


def test_comtrade_flows_list_raises_on_invalid_flow() -> None:
    s = _make_settings(comtrade_flows="X,ZZ")
    with pytest.raises(ValueError, match="COMTRADE_FLOWS has invalid flow"):
        _ = s.comtrade_flows_list


def test_comtrade_flows_list_normalizes_case() -> None:
    s = _make_settings(comtrade_flows="x, m ,rx")
    assert s.comtrade_flows_list == ["X", "M", "RX"]


# ─── __init__ version fallback (lines 8-9) ──────────────────────────────────
def test_version_falls_back_when_package_not_found() -> None:
    """When importlib.metadata.version raises PackageNotFoundError (running from a
    source tree without an install), __version__ falls back to '0.0.0'."""
    from importlib.metadata import PackageNotFoundError

    import embrapa_commodities

    with patch(
        "importlib.metadata.version", side_effect=PackageNotFoundError("embrapa-commodities")
    ):
        reloaded = importlib.reload(embrapa_commodities)
        try:
            assert reloaded.__version__ == "0.0.0"
        finally:
            # Restore the real, installed version for any later-importing tests.
            importlib.reload(reloaded)
