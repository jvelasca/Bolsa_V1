"""Tests de Settings (F2·6): credenciales BD por composición y secreto de firmas."""

from __future__ import annotations

import os

import pytest

from bolsa_infrastructure.config import Settings


def test_database_url_se_compone_desde_db_vars_vacio() -> None:
    with _env_cleanup("DATABASE_URL", "DB_PASSWORD", "APP_PASSWORD", "APP_AUTH_SECRET"):
        s = Settings(
            _env_file=None,
            DATABASE_URL=None,
            DB_PASSWORD="",
        )
        assert s.database_url == "postgresql+psycopg://bolsa@localhost:5432/bolsa_v1"


def test_database_url_incluye_password_si_se_provee() -> None:
    with _env_cleanup("DATABASE_URL", "APP_PASSWORD", "APP_AUTH_SECRET"):
        s = Settings(_env_file=None, DATABASE_URL=None, DB_PASSWORD="s3cr3t")
        assert s.database_url == "postgresql+psycopg://bolsa:s3cr3t@localhost:5432/bolsa_v1"


def test_database_url_override_con_databse_url() -> None:
    with _env_cleanup("DATABASE_URL", "DB_PASSWORD", "APP_PASSWORD", "APP_AUTH_SECRET"):
        s = Settings(
            _env_file=None,
            DATABASE_URL="postgresql://miuser:miclave@db.example:5544/midb?schema=public",
        )
        # quita ?schema=public y normaliza a +psycopg
        assert s.database_url == "postgresql+psycopg://miuser:miclave@db.example:5544/midb"


def test_secret_vacio_permitido_sin_password() -> None:
    with _env_cleanup("APP_PASSWORD", "APP_AUTH_SECRET"):
        s = Settings(_env_file=None, APP_PASSWORD=None, APP_AUTH_SECRET="")
        assert s.app_auth_secret == ""


def test_secret_requerido_si_hay_password() -> None:
    with _env_cleanup("APP_PASSWORD", "APP_AUTH_SECRET"):
        with pytest.raises(ValueError, match="APP_PASSWORD activa requiere APP_AUTH_SECRET"):
            Settings(_env_file=None, APP_PASSWORD="x", APP_AUTH_SECRET="    ")


def test_secret_devel_rechazado_si_hay_password() -> None:
    with _env_cleanup("APP_PASSWORD", "APP_AUTH_SECRET"):
        with pytest.raises(ValueError, match="bolsa-dev-secret"):
            Settings(_env_file=None, APP_PASSWORD="x", APP_AUTH_SECRET="bolsa-dev-secret")


def test_secret_real_aceptado_si_hay_password() -> None:
    with _env_cleanup("APP_PASSWORD", "APP_AUTH_SECRET"):
        s = Settings(_env_file=None, APP_PASSWORD="x", APP_AUTH_SECRET="UN-SECRETO-ALEATORIO")
        assert s.app_auth_secret == "UN-SECRETO-ALEATORIO"


class _EnvCleanup:
    """Context manager: garantiza que las variables no se cuelen de pytest env."""

    def __init__(self, *names: str) -> None:
        self._names = names
        self._saved = {}

    def __enter__(self) -> _EnvCleanup:
        for n in self._names:
            self._saved[n] = os.environ.pop(n, None)
        return self

    def __exit__(self, *exc) -> None:
        for n, v in self._saved.items():
            if v is None:
                os.environ.pop(n, None)
            else:
                os.environ[n] = v


def _env_cleanup(*names: str) -> _EnvCleanup:
    return _EnvCleanup(*names)
