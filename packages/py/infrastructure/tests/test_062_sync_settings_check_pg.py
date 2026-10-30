"""062 — ciclo de vida del ``CHECK`` de ``sync_settings`` sobre PostgreSQL real.

Cierra el defecto de idempotencia de la ``060``: la creación del
``sync_settings_provider_check_interval_check`` estaba atada a la creación de la columna,
y en una base nueva la baseline ya trae la columna **desde los metadatos**, así que el
``CHECK`` quedaba ausente (drift real). La ``060`` ya está corregida; esta revisión
repara las bases **heredadas** que ya tienen la ``060`` (o la ``061``) estampada.

Se ejecuta sobre una BD scratch efímera creada por el test, nunca sobre ``DATABASE_URL``.

Casos:

1. **Base nueva**: ``upgrade head`` -> el ``CHECK`` existe con la definición 15..3600;
   la ``060`` corregida lo crea y la ``062`` no lo duplica.
2. **Base heredada**: esquema en ``061``, se elimina el ``CHECK`` para simular el defecto
   -> ``upgrade head`` lo recrea y la fila de ``sync_settings`` queda intacta.
3. **Idempotencia**: re-aplicar ``head`` conserva el ``oid`` (no hay DROP + CREATE).
4. **Fail-closed**: un ``CHECK`` homónimo con otra definición aborta el upgrade y NO
   marca la revisión como aplicada.
5. **Downgrade**: ``downgrade_to("061…")`` retira el ``CHECK``; ``upgrade`` lo restaura.

Gate: ``SYNC_SETTINGS_CHECK_PG_REQUIRED=1`` convierte el skip en fallo duro.
"""

from __future__ import annotations

import re
from typing import Any

import pytest
from _profile_pg_helpers import (
    admin_url,
    current_revision,
    require_or_skip,
    scratch_database,
)

from bolsa_infrastructure.database.migrations import (
    alembic_head,
    downgrade_to,
    migrate_to,
)

_REQUIRED_ENV = "SYNC_SETTINGS_CHECK_PG_REQUIRED"
_CHECK_NAME = "sync_settings_provider_check_interval_check"
_TABLE = "sync_settings"
_COLUMN = "provider_check_interval_seconds"
_LEGACY_REVISION = "061_profile_delete_restrict"


def _connect(url: str) -> Any:
    import psycopg

    return psycopg.connect(url, autocommit=True, connect_timeout=10)


@pytest.fixture(scope="module", autouse=True)
def _require_scratch_database() -> None:
    """Skip honesto sin PostgreSQL; fallo duro si el job PG exige la certificación."""
    try:
        with _connect(admin_url()) as conn:
            row = conn.execute(
                "SELECT rolcreatedb OR rolsuper FROM pg_roles WHERE rolname = current_user"
            ).fetchone()
        if not row or not row[0]:
            raise RuntimeError("el usuario de BD no puede crear bases scratch (rolcreatedb)")
    except Exception as exc:  # noqa: BLE001 - el llamante decide skip/fail
        require_or_skip(exc, required_env=_REQUIRED_ENV, what="migración 062 sobre BD scratch")


def _check_oid(url: str) -> int | None:
    with _connect(url) as conn:
        row = conn.execute(
            "SELECT oid FROM pg_constraint "
            "WHERE conname = %s AND contype = 'c' AND conrelid = %s::regclass",
            (_CHECK_NAME, _TABLE),
        ).fetchone()
    return None if row is None else int(row[0])


def _check_definition(url: str) -> str | None:
    with _connect(url) as conn:
        row = conn.execute(
            "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
            "WHERE conname = %s AND contype = 'c' AND conrelid = %s::regclass",
            (_CHECK_NAME, _TABLE),
        ).fetchone()
    return None if row is None else str(row[0])


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9_<>=]", "", text.lower())


def _assert_expected_definition(url: str) -> None:
    definition = _check_definition(url)
    assert definition is not None, "falta el CHECK de sync_settings"
    normalized = _normalize(definition)
    assert f"{_COLUMN}>=15" in normalized, definition
    assert f"{_COLUMN}<=3600" in normalized, definition


def _drop_check(url: str) -> None:
    with _connect(url) as conn:
        conn.execute(f"ALTER TABLE {_TABLE} DROP CONSTRAINT {_CHECK_NAME}")


def _seed_settings_row(url: str, interval: int = 120) -> None:
    """Inserta la fila única con TODOS los ``NOT NULL`` explícitos.

    La baseline crea ``sync_settings`` desde los metadatos y los ``default`` de
    SQLAlchemy son de lado Python (sin ``server_default``): un INSERT parcial viola
    ``NOT NULL``. Se siembra completa para medir que la migración no toca los datos.
    """
    with _connect(url) as conn:
        conn.execute(
            f"INSERT INTO {_TABLE} ("
            "id, auto_sync_enabled, scan_interval_minutes, min_delay_seconds, "
            "post_market_only, max_retries, retry_backoff_minutes, scope, "
            "provider_check_enabled, provider_check_interval_seconds, updated_at"
            ") VALUES ('default', true, 30, 3, false, 5, 45, 'lists', true, %s, now())",
            (interval,),
        )


def _interval_of_default_row(url: str) -> int | None:
    with _connect(url) as conn:
        row = conn.execute(
            f"SELECT provider_check_interval_seconds FROM {_TABLE} WHERE id = 'default'"
        ).fetchone()
    return None if row is None else int(row[0])


def test_new_database_gets_the_check_from_060_and_062_is_a_noop() -> None:
    with scratch_database("bolsa_062_new") as url:
        migrate_to("head", database_url=url)

        assert current_revision(url) == alembic_head()
        _assert_expected_definition(url)

        oid = _check_oid(url)
        assert oid is not None

        migrate_to("head", database_url=url)  # segunda pasada: no-op
        _assert_expected_definition(url)
        assert _check_oid(url) == oid, "re-aplicar la 062 recreó el CHECK sin necesidad"


def test_legacy_database_missing_the_check_is_repaired_without_touching_data() -> None:
    with scratch_database("bolsa_062_legacy") as url:
        migrate_to(_LEGACY_REVISION, database_url=url)
        assert current_revision(url) == _LEGACY_REVISION
        # La 060 corregida ya lo crea; se retira para modelar una base heredada defectuosa.
        _drop_check(url)
        assert _check_definition(url) is None

        _seed_settings_row(url, interval=120)

        migrate_to("head", database_url=url)

        assert current_revision(url) == alembic_head()
        _assert_expected_definition(url)
        assert _interval_of_default_row(url) == 120, "la migración tocó los datos"


def test_homonymous_check_with_another_definition_fails_closed() -> None:
    with scratch_database("bolsa_062_conflict") as url:
        migrate_to(_LEGACY_REVISION, database_url=url)
        _drop_check(url)
        with _connect(url) as conn:
            conn.execute(
                f"ALTER TABLE {_TABLE} ADD CONSTRAINT {_CHECK_NAME} "
                f"CHECK ({_COLUMN} >= 30 AND {_COLUMN} <= 3600)"
            )

        with pytest.raises(Exception) as excinfo:  # noqa: BLE001 — Alembic puede envolverla
            migrate_to("head", database_url=url)
        assert "definición distinta" in str(excinfo.value)

        # La revisión NO se marca como aplicada: el operador decide.
        assert current_revision(url) == _LEGACY_REVISION


def test_downgrade_removes_the_check_and_upgrade_restores_it() -> None:
    with scratch_database("bolsa_062_down") as url:
        migrate_to("head", database_url=url)
        _assert_expected_definition(url)
        _seed_settings_row(url, interval=90)

        downgrade_to(_LEGACY_REVISION, database_url=url)

        assert current_revision(url) == _LEGACY_REVISION
        assert _check_definition(url) is None, "el downgrade debe retirar el CHECK"
        assert _interval_of_default_row(url) == 90, "el downgrade tocó los datos"

        migrate_to("head", database_url=url)

        _assert_expected_definition(url)
        assert _interval_of_default_row(url) == 90
