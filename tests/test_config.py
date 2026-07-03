"""Tests for runtime settings (validators, parsers, default-derivation, helpers)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from embrapa_dashboard import config as config_module
from embrapa_dashboard.config import (
    Settings,
    _parse_code_label,
    get_credentials,
    get_settings,
)


# ─── _parse_code_label ───────────────────────────────────────────────────────
def test_parse_code_label_simple_pair() -> None:
    assert _parse_code_label("433:IPCA") == {"433": "IPCA"}


def test_parse_code_label_multiple_pairs() -> None:
    assert _parse_code_label("433:IPCA,189:IGPM,190:IGPDI") == {
        "433": "IPCA",
        "189": "IGPM",
        "190": "IGPDI",
    }


def test_parse_code_label_strips_whitespace() -> None:
    # Spaces and tabs around items / inside pairs are all stripped.
    assert _parse_code_label(" 433 : IPCA ,  189:IGPM ") == {"433": "IPCA", "189": "IGPM"}


def test_parse_code_label_skips_empty_items() -> None:
    # Trailing comma must not introduce an empty entry.
    assert _parse_code_label("433:IPCA,,") == {"433": "IPCA"}


def test_parse_code_label_empty_string_returns_empty_map() -> None:
    assert _parse_code_label("") == {}


def test_parse_code_label_missing_colon_raises() -> None:
    with pytest.raises(ValueError, match="Expected 'CODE:LABEL'"):
        _parse_code_label("433_no_colon")


def test_parse_code_label_empty_code_raises() -> None:
    with pytest.raises(ValueError, match="Empty code or label"):
        _parse_code_label(":IPCA")


def test_parse_code_label_empty_label_raises() -> None:
    with pytest.raises(ValueError, match="Empty code or label"):
        _parse_code_label("433:")


def test_parse_code_label_duplicate_code_raises() -> None:
    with pytest.raises(ValueError, match="Duplicate series code"):
        _parse_code_label("433:IPCA,433:IGPM")


def test_parse_code_label_transposed_pair_raises() -> None:
    # A transposed 'LABEL:CODE' (e.g. 'IPCA:433') has a non-numeric code and
    # must fail loudly here, naming the offending item, instead of silently
    # parsing to {'IPCA': '433'} and failing downstream with a confusing error.
    with pytest.raises(ValueError, match="must be numeric") as exc_info:
        _parse_code_label("IPCA:433")
    assert "IPCA" in str(exc_info.value)


def test_parse_code_label_non_numeric_code_raises() -> None:
    with pytest.raises(ValueError, match="must be numeric"):
        _parse_code_label("433:IPCA,abc:IGPM")


def test_parse_code_label_rejects_unicode_digit_code() -> None:
    # Fullwidth digits pass str.isdigit() (and even int()), but are not valid
    # ASCII SGS/NCM ids — the isascii() guard must reject them. (RUF001 ambiguous-
    # unicode is globally ignored for the pt-BR typography this project uses.)
    assert "４３３".isdigit()
    with pytest.raises(ValueError, match="must be numeric"):
        _parse_code_label("４３３:IPCA")


# ─── default bucket derivation ──────────────────────────────────────────────
def _make_settings(**overrides: object) -> Settings:
    """Build a Settings instance without picking up the user's local .env."""
    base = {"gcp_project_id": "test-project", "_env_file": None}
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


def test_default_bucket_derives_from_project_when_unset() -> None:
    s = _make_settings()
    assert s.gcs_bucket == "test-project-datalake"


def test_default_bucket_respects_explicit_value() -> None:
    s = _make_settings(gcs_bucket="my-custom-bucket")
    assert s.gcs_bucket == "my-custom-bucket"


def test_default_bucket_treats_empty_string_as_unset() -> None:
    # The validator checks `if not self.gcs_bucket`, so "" also triggers the default.
    s = _make_settings(gcs_bucket="")
    assert s.gcs_bucket == "test-project-datalake"


# ─── series-map properties ──────────────────────────────────────────────────
def test_inflation_series_map_parses_default() -> None:
    s = _make_settings()
    assert s.inflation_series_map == {"433": "IPCA", "189": "IGPM", "190": "IGPDI"}


def test_currency_series_map_parses_default() -> None:
    s = _make_settings()
    # Daily PTAX venda: SGS 1 = USD, 21619 = EUR.
    assert s.currency_series_map == {"1": "USD", "21619": "EUR"}


def test_inflation_series_map_reflects_override() -> None:
    s = _make_settings(bcb_inflation_series="999:CUSTOM")
    assert s.inflation_series_map == {"999": "CUSTOM"}


def test_currency_series_map_propagates_parse_errors() -> None:
    s = _make_settings(bcb_currency_series="bad-no-colon")
    with pytest.raises(ValueError, match="Expected 'CODE:LABEL'"):
        _ = s.currency_series_map


# ─── product_codes helper ───────────────────────────────────────────────────
def test_product_codes_splits_and_strips() -> None:
    s = _make_settings(ibge_product_codes=" 3405, 3435 ,3450 ")
    assert s.product_codes == ["3405", "3435", "3450"]


def test_product_codes_drops_empty_entries() -> None:
    s = _make_settings(ibge_product_codes="3405,,3435,")
    assert s.product_codes == ["3405", "3435"]


def test_product_codes_raises_when_empty() -> None:
    s = _make_settings(ibge_product_codes="  , ,")
    with pytest.raises(ValueError, match="IBGE_PRODUCT_CODES is empty"):
        _ = s.product_codes


# ─── defaults sanity ────────────────────────────────────────────────────────
def test_defaults_match_documented_values() -> None:
    s = _make_settings()
    assert s.bq_location == "US"
    assert s.bq_bronze_ibge_dataset == "bronze_ibge"
    assert s.bq_bronze_bcb_dataset == "bronze_bcb"
    assert s.bq_silver_dataset == "silver"
    assert s.bq_gold_dataset == "gold"
    assert s.ibge_table_id == "289"
    assert s.ibge_classification_id == "193"
    # IBGE_START_YEAR is intentionally None — the discover step must populate it.
    assert s.ibge_start_year is None
    assert s.bcb_start_year == 1980


def test_get_settings_returns_settings_instance(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    # get_settings() reads GCP_PROJECT_ID from the environment via pydantic-settings.
    # Chdir into an empty tmp dir so any developer-local .env can't bleed in.
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GCP_PROJECT_ID", "env-project")
    s = get_settings()
    assert isinstance(s, Settings)
    assert s.gcp_project_id == "env-project"


def test_get_settings_returns_fresh_instance_each_call(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """get_settings has no @lru_cache — each call re-reads the environment.

    This is intentional (see config.py); callers that want a singleton should
    keep their own reference rather than relying on caching here.
    """
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GCP_PROJECT_ID", "first-project")
    first = get_settings()

    monkeypatch.setenv("GCP_PROJECT_ID", "second-project")
    second = get_settings()

    assert first.gcp_project_id == "first-project"
    assert second.gcp_project_id == "second-project"
    assert first is not second


# ─── get_credentials ────────────────────────────────────────────────────────
def test_get_credentials_returns_none_without_impersonation() -> None:
    s = _make_settings()
    assert get_credentials(s) is None


def test_get_credentials_builds_impersonated_creds() -> None:
    s = _make_settings(gcp_impersonation_sa="sa@test-project.iam.gserviceaccount.com")
    fake_source = MagicMock(name="source-creds")
    with (
        patch("google.auth.default", return_value=(fake_source, "test-project")) as default,
        patch("google.auth.impersonated_credentials.Credentials") as creds_cls,
    ):
        result = get_credentials(s)

    default.assert_called_once()
    creds_cls.assert_called_once()
    kwargs = creds_cls.call_args.kwargs
    assert kwargs["source_credentials"] is fake_source
    assert kwargs["target_principal"] == "sa@test-project.iam.gserviceaccount.com"
    assert kwargs["target_scopes"] == ["https://www.googleapis.com/auth/cloud-platform"]
    assert result is creds_cls.return_value


def test_get_credentials_uses_get_settings_when_none_passed() -> None:
    """When `settings` is None, get_credentials() falls back to get_settings()."""
    fake_settings = _make_settings(gcp_impersonation_sa="sa@x.iam")
    fake_source = MagicMock()
    with (
        patch.object(config_module, "get_settings", return_value=fake_settings) as gs,
        patch("google.auth.default", return_value=(fake_source, "p")),
        patch("google.auth.impersonated_credentials.Credentials") as creds_cls,
    ):
        get_credentials()

    gs.assert_called_once()
    creds_cls.assert_called_once()
