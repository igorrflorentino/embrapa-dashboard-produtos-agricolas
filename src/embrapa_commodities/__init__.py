"""Embrapa commodities pipeline (Bronze layer ingestion + dbt orchestration)."""

from importlib.metadata import PackageNotFoundError, version

try:
    # Single source of truth: the installed package version (pyproject.toml).
    __version__ = version("embrapa-commodities")
except PackageNotFoundError:  # running from a source tree without an install
    __version__ = "0.0.0"
