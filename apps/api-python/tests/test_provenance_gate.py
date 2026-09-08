"""V2.15 — provenance gate (readiness item): PRD==identidad de release obligatoria en producción.

Tests offline (sin BD): cubren la consistencia/monkeypatched source y el fail-fast
``require_release_identity_env``. Se ejecutan en el tag CI sin PostgreSQL.
"""

import pytest

from bolsa_api import provenance as prov_module


@pytest.fixture
def clear_env(monkeypatch) -> None:
    monkeypatch.delenv("PRODUCT_VERSION", raising=False)
    monkeypatch.delenv("API_CONTRACT_VERSION", raising=False)


def test_release_env_keys_absent_are_reported(clear_env) -> None:
    missing = prov_module.missing_release_identity_env()
    assert set(missing) == {"PRODUCT_VERSION", "API_CONTRACT_VERSION"}


def test_release_env_fully_defined(clear_env, monkeypatch) -> None:
    monkeypatch.setenv("PRODUCT_VERSION", "V2.15")
    monkeypatch.setenv("API_CONTRACT_VERSION", "V1")
    assert prov_module.missing_release_identity_env() == []


def test_require_release_identity_ok_in_dev(clear_env) -> None:
    # En dev/test/staging la identidad es opcional (no rompe CI/local).
    prov_module.require_release_identity_env("development")
    prov_module.require_release_identity_env("testing")


def test_require_release_identity_raises_in_prod_when_missing(clear_env) -> None:
    with pytest.raises(RuntimeError):
        prov_module.require_release_identity_env("production")


def test_require_release_identity_passes_in_prod_when_defined(clear_env, monkeypatch) -> None:
    monkeypatch.setenv("PRODUCT_VERSION", "V2.15")
    monkeypatch.setenv("API_CONTRACT_VERSION", "V1")
    # No eleva: identidad presente en el build productivo.
    prov_module.require_release_identity_env("production")
