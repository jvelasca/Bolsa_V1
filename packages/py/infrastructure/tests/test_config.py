"""Tests de Settings (F2·6): credenciales BD por composición y secreto de firmas."""

from __future__ import annotations

import os

import pytest

from bolsa_infrastructure.config import Settings


def test_owner_principal_default_app() -> None:
    with _env_cleanup("APP_OWNER_ID", "APP_PASSWORD", "APP_AUTH_SECRET"):
        s = Settings(_env_file=None)
        assert s.app_owner_id == "app"
        assert s.owner_principal() == "app"


def test_owner_principal_blank_falls_back_to_app() -> None:
    with _env_cleanup("APP_OWNER_ID", "APP_PASSWORD", "APP_AUTH_SECRET"):
        s = Settings(_env_file=None, APP_OWNER_ID="   ")
        assert s.owner_principal() == "app"


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


# F-SEG-1: fail-closed production.


def test_prod_sin_password_falla() -> None:
    with _env_cleanup("APP_PASSWORD", "APP_AUTH_SECRET", "ENVIRONMENT"):
        with pytest.raises(ValueError, match="ENVIRONMENT=production exige APP_PASSWORD"):
            Settings(
                _env_file=None,
                environment="production",
                APP_PASSWORD=None,
                APP_AUTH_SECRET="",
            )


def test_prod_con_password_sin_secreto_falla() -> None:
    # En prod, con APP_PASSWORD activa y secreto vacío: lo rechaza la rama de
    # "APP_PASSWORD activa requiere APP_AUTH_SECRET" (F2·6). El fail-closed prod
    # añade además el bloqueo de arranque cuando NO hay password (test previo).
    with _env_cleanup("APP_PASSWORD", "APP_AUTH_SECRET", "ENVIRONMENT"):
        with pytest.raises(ValueError, match="APP_PASSWORD activa requiere APP_AUTH_SECRET"):
            Settings(
                _env_file=None,
                environment="prod",
                APP_PASSWORD="x",
                APP_AUTH_SECRET="   ",
            )


def test_prod_con_secreto_devel_rechazado() -> None:
    with _env_cleanup("APP_PASSWORD", "APP_AUTH_SECRET", "ENVIRONMENT"):
        with pytest.raises(ValueError, match="bolsa-dev-secret"):
            Settings(
                _env_file=None,
                environment="production",
                APP_PASSWORD="x",
                APP_AUTH_SECRET="bolsa-dev-secret",
            )


def test_prod_con_password_y_secreto_real_ok() -> None:
    with _env_cleanup("APP_PASSWORD", "APP_AUTH_SECRET", "ENVIRONMENT"):
        s = Settings(
            _env_file=None,
            environment="production",
            APP_PASSWORD="x",
            APP_AUTH_SECRET="UN-SECRETO-ALEATORIO",
        )
        assert s.environment == "production"


def test_dev_sin_password_sigue_ok_no_rompe() -> None:
    # Regresión: el fail-closed NO debe activarse en development (tests/CI/dev corren
    # así por defecto sin password).
    with _env_cleanup("APP_PASSWORD", "APP_AUTH_SECRET", "ENVIRONMENT"):
        s = Settings(_env_file=None, environment="development", APP_PASSWORD=None, APP_AUTH_SECRET="")
        assert s.app_auth_secret == ""


# F-SEG-2: redacción — un `repr(Settings)` o un error de validación no debe exponer
# el valor real de la password, el secreto de firma ni las credenciales de la BD.


def test_repr_no_expone_password_ni_secret() -> None:
    real_password = "P4ssw0rd-SUPERSECRET-OK9"  # noqa: S105
    real_secret = "Sk-REAL-SIGNING-SECRET-7f6e"  # noqa: S105
    with _env_cleanup("APP_PASSWORD", "APP_AUTH_SECRET", "DATABASE_URL", "DB_PASSWORD"):
        s = Settings(
            _env_file=None,
            APP_PASSWORD=real_password,
            APP_AUTH_SECRET=real_secret,
            DATABASE_URL=None,
            DB_PASSWORD="db-secret-x",
        )
    rendered = repr(s)
    assert real_password not in rendered
    assert real_secret not in rendered
    assert "app_password=********" in rendered
    assert "app_auth_secret=********" in rendered


def test_repr_redacta_credenciales_db() -> None:
    with _env_cleanup("DATABASE_URL", "APP_PASSWORD", "APP_AUTH_SECRET"):
        s = Settings(
            _env_file=None,
            DATABASE_URL=None,
            DB_PASSWORD="db-s3cr3t",
        )
    rendered = repr(s)
    assert "db-s3cr3t" not in rendered
    assert "bolsa:***@localhost" in rendered
    assert "bolsa:db-s3cr3t@localhost" not in rendered


def test_error_validacion_no_filtra_secreto_real() -> None:
    # Cuando falla la validación, el secreto real aportado por el usuario no debe
    # aparecer ni en la excepción ni en su mensaje (salvo el valor dev conocido
    # "bolsa-dev-secret", que ya es público por diseño).
    real_secret = "Sk-REAL-SIGNING-SECRET-9d2e"  # noqa: S105
    with _env_cleanup("APP_PASSWORD", "APP_AUTH_SECRET", "ENVIRONMENT"):
        with pytest.raises(ValueError) as excinfo:
            Settings(
                _env_file=None,
                environment="production",
                APP_PASSWORD=None,
                APP_AUTH_SECRET=real_secret,
            )
    rendered = str(excinfo.value)
    assert real_secret not in rendered


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
