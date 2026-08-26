"""F5 — is_production_environment allowlist (fail-closed prod)."""

from __future__ import annotations

import pytest

from bolsa_infrastructure.config import (
    NON_PRODUCTION_ENVIRONMENTS,
    Settings,
    get_settings,
    is_production_environment,
)


@pytest.mark.parametrize(
    "environment",
    sorted(NON_PRODUCTION_ENVIRONMENTS),
)
def test_non_production_allowlist(environment: str) -> None:
    assert is_production_environment(environment) is False
    assert is_production_environment(f"  {environment.upper()}  ") is False


@pytest.mark.parametrize("environment", ("production", "prod", "PRODUCTION"))
def test_production_names_fail_closed(environment: str) -> None:
    assert is_production_environment(environment) is True


def test_settings_production_requires_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("APP_PASSWORD", raising=False)
    monkeypatch.delenv("APP_AUTH_SECRET", raising=False)
    get_settings.cache_clear()
    with pytest.raises(ValueError, match="APP_PASSWORD"):
        Settings()
    get_settings.cache_clear()
