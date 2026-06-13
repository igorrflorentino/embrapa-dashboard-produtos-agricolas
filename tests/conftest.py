"""Shared pytest fixtures.

Centralizes the one isolation hazard several suites repeat by hand: ``Settings``
reads ``.env`` at repo root (``config.Settings.model_config env_file=".env"``),
and the documented dev setup (``cp .env.example .env``) puts a real one there. A
test that constructs ``Settings(...)`` without ``_env_file=None`` therefore reads
whatever the developer happens to have in ``.env`` / their shell, which makes
default-dependent assertions flaky. ``settings_factory`` builds an isolated
``Settings`` (``_env_file=None``) so new tests can opt in without re-deriving the
trick.
"""

from __future__ import annotations

import pytest


@pytest.fixture
def settings_factory():
    """Return a builder for env-isolated ``Settings`` (never reads ``.env``)."""
    from embrapa_commodities.config import Settings

    def _build(**overrides):
        overrides.setdefault("gcp_project_id", "test-project")
        return Settings(_env_file=None, **overrides)

    return _build
