"""061 — ciclo de vida de la migración sobre PostgreSQL real (AUD-03).

Cierra la comprobación que el dictamen exige antes de integrar: la migración
``061_profile_delete_restrict`` debe funcionar igual en una base **nueva** y en una base
que **ya contiene perfiles asignados**, y su ``downgrade`` no puede dejar
inconsistencias.

Se ejecuta sobre una BD scratch efímera (``CREATE DATABASE`` / ``DROP DATABASE``) creada
por el test, nunca sobre ``DATABASE_URL``: el ``downgrade`` devuelve la FK a
``SET NULL`` y hacerlo sobre la base de desarrollo reabriría la desasignación silenciosa
que AUD-03 elimina.

Casos:

1. **Base nueva**: ``upgrade head`` desde vacío -> FK ``RESTRICT``; re-aplicar no recrea
   el constraint (idempotencia medida por ``oid``).
2. **Base heredada con datos**: esquema en ``060`` + FK forzada a ``SET NULL`` (como la
   base provisionada por el SQL de Prisma antiguo) + perfil asignado -> ``upgrade head``
   conserva la asignación, los recuentos y bloquea el ``DELETE`` crudo.
3. **Ventana transaccional**: un lector concurrente nunca observa la FK ausente ni en
   ``SET NULL`` mientras la 061 la recrea (el DROP+CREATE viaja en una transacción).
4. **Downgrade**: vuelve a ``SET NULL`` sin huérfanos ni pérdida de asignaciones; el
   ``upgrade`` posterior restaura ``RESTRICT`` y el bloqueo.

Gate: ``PROFILE_DELETE_MIGRATION_PG_REQUIRED=1`` convierte el skip en fallo duro.
"""

from __future__ import annotations

import threading
import time

import psycopg
import pytest
from _profile_pg_helpers import (
    account_ids_with_profile,
    admin_url,
    assigned_profile,
    counts,
    current_revision,
    fk_constraint_oid,
    fk_delete_action,
    force_fk_to_set_null,
    orphan_accounts,
    require_or_skip,
    scratch_database,
    seed_assigned_profile,
)

from bolsa_infrastructure.database.migrations import (
    alembic_head,
    downgrade_to,
    migrate_to,
)

_REQUIRED_ENV = "PROFILE_DELETE_MIGRATION_PG_REQUIRED"
_LEGACY_REVISION = "060_provider_check_policy"


@pytest.fixture(scope="module", autouse=True)
def _require_scratch_database() -> None:
    """Skip honesto sin PostgreSQL; fallo duro si el job PG exige la certificación."""
    try:
        with psycopg.connect(admin_url(), autocommit=True) as conn:
            row = conn.execute(
                "SELECT rolcreatedb OR rolsuper FROM pg_roles WHERE rolname = current_user"
            ).fetchone()
        if not row or not row[0]:
            raise RuntimeError("el usuario de BD no puede crear bases scratch (rolcreatedb)")
    except Exception as exc:  # noqa: BLE001 - el llamante decide skip/fail
        require_or_skip(exc, required_env=_REQUIRED_ENV, what="migración 061 sobre BD scratch")


def test_new_database_lands_in_restrict_and_reapplying_is_a_noop() -> None:
    with scratch_database("bolsa_061_new") as url:
        migrate_to("head", database_url=url)

        assert current_revision(url) == alembic_head()
        assert fk_delete_action(url) == "r", "una base nueva debe nacer con RESTRICT"

        oid = fk_constraint_oid(url)
        assert oid is not None

        migrate_to("head", database_url=url)  # segunda pasada: debe ser no-op

        assert fk_delete_action(url) == "r"
        assert fk_constraint_oid(url) == oid, "re-aplicar la 061 recreó la FK sin necesidad"


def test_legacy_database_with_assigned_profiles_upgrades_without_touching_data() -> None:
    with scratch_database("bolsa_061_legacy") as url:
        migrate_to(_LEGACY_REVISION, database_url=url)
        force_fk_to_set_null(url)
        assert fk_delete_action(url) == "n", "no se pudo simular la base heredada"
        assert current_revision(url) == _LEGACY_REVISION

        account_id, profile_id = seed_assigned_profile(url, tag="legacy")
        before_counts = counts(url)
        before_map = account_ids_with_profile(url)

        migrate_to("head", database_url=url)

        assert fk_delete_action(url) == "r"
        assert current_revision(url) == alembic_head()
        # Ni una cuenta desasignada, ni una fila perdida por el camino.
        assert counts(url) == before_counts
        assert account_ids_with_profile(url) == before_map
        assert assigned_profile(url, account_id) == profile_id

        with pytest.raises(psycopg.errors.ForeignKeyViolation):
            with psycopg.connect(url, autocommit=True) as conn:
                conn.execute("DELETE FROM investor_profiles WHERE id = %s", (profile_id,))

        assert assigned_profile(url, account_id) == profile_id


def test_concurrent_reader_never_sees_a_missing_or_set_null_fk() -> None:
    """El DROP+CREATE de la 061 es transaccional: no hay ventana observable."""
    with scratch_database("bolsa_061_window") as url:
        migrate_to(_LEGACY_REVISION, database_url=url)
        force_fk_to_set_null(url)

        samples: list[str | None] = []
        failures: list[BaseException] = []
        stop = threading.Event()

        def probe() -> None:
            try:
                with psycopg.connect(url, autocommit=True) as conn:
                    while not stop.is_set():
                        row = conn.execute(
                            "SELECT confdeltype FROM pg_constraint "
                            "WHERE conname = 'investment_accounts_active_profile_id_fkey' "
                            "AND conrelid = 'investment_accounts'::regclass"
                        ).fetchone()
                        samples.append(None if row is None else str(row[0]))
                        time.sleep(0.002)
            except BaseException as exc:  # noqa: BLE001 - se re-lanza en el hilo principal
                failures.append(exc)

        reader = threading.Thread(target=probe, name="fk-window-probe", daemon=True)
        reader.start()
        try:
            migrate_to("head", database_url=url)
        finally:
            stop.set()
            reader.join(timeout=10)

        assert not failures, f"el lector falló durante la migración: {failures!r}"
        assert samples, "el lector no llegó a muestrear la FK"
        assert None not in samples, "la FK desapareció en algún instante (DROP+CREATE no atómico)"
        assert set(samples) <= {"n", "r"}, f"acción inesperada observada: {set(samples)!r}"
        assert fk_delete_action(url) == "r"


def test_downgrade_restores_set_null_without_orphans_and_upgrade_returns() -> None:
    with scratch_database("bolsa_061_down") as url:
        migrate_to("head", database_url=url)
        account_id, profile_id = seed_assigned_profile(url, tag="down")
        before_map = account_ids_with_profile(url)

        downgrade_to(_LEGACY_REVISION, database_url=url)

        assert current_revision(url) == _LEGACY_REVISION
        assert fk_delete_action(url) == "n", "el downgrade debe devolver SET NULL"
        assert orphan_accounts(url) == [], "el downgrade dejó cuentas huérfanas"
        assert account_ids_with_profile(url) == before_map, "el downgrade tocó asignaciones"

        # Semántica de rollback declarada: con SET NULL el DELETE vuelve a desasignar en
        # silencio. Es exactamente por esto que el downgrade NO se ejecuta en la BD viva
        # mientras la API nueva promete 409.
        with psycopg.connect(url, autocommit=True) as conn:
            conn.execute("DELETE FROM investor_profiles WHERE id = %s", (profile_id,))
        assert assigned_profile(url, account_id) is None

        migrate_to("head", database_url=url)
        assert fk_delete_action(url) == "r"
        assert orphan_accounts(url) == []

        _other_account, other_profile = seed_assigned_profile(url, tag="down2")
        with pytest.raises(psycopg.errors.ForeignKeyViolation):
            with psycopg.connect(url, autocommit=True) as conn:
                conn.execute("DELETE FROM investor_profiles WHERE id = %s", (other_profile,))

        assert orphan_accounts(url) == []
