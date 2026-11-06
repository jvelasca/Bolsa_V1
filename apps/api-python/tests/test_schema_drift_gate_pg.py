"""Gate de drift de esquema contra PostgreSQL real.

``alembic check`` pasó de ruido a gate útil: la allowlist de ``schema_contract`` declara
las divergencias históricas (con motivo) y este test exige que **no quede ninguna otra**.
El valor está en fallar cuando alguien toca el esquema sin migración o añade una tabla,
columna, índice o constraint que la BD no tiene.

No escribe en la BD: ``compare_metadata`` solo lee catálogo. No aplica migraciones ni
crea objetos; si alguien amplía la allowlist para «arreglar» el test, el diff de la PR
tiene que explicar el motivo.
"""

from __future__ import annotations

import asyncio
import sys
from typing import Any

import pytest
import sqlalchemy as sa

from tests._estudio_pg_helpers import make_pg_session_factory, require_or_skip

if sys.platform == "win32":  # psycopg async no soporta ProactorEventLoop.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

_REQUIRED_ENV = "SCHEMA_DRIFT_PG_REQUIRED"

#: ``pg_constraint.confdeltype`` / ``confupdtype`` -> acción declarable en SQLAlchemy.
#: ``a`` es «sin acción» (Alembic/SQLAlchemy lo representan como ``None``).
_FK_ACTIONS: dict[str, str | None] = {
    "a": None,
    "r": "RESTRICT",
    "c": "CASCADE",
    "n": "SET NULL",
    "d": "SET DEFAULT",
}


@pytest.mark.asyncio
async def test_metadata_and_database_are_in_sync() -> None:
    """Sin diferencias no declaradas entre ``Base.metadata`` y la BD."""
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext

    from bolsa_infrastructure.database.models import Base
    from bolsa_infrastructure.database.schema_contract import alembic_include_object

    try:
        _factory, engine = await make_pg_session_factory()
    except Exception as exc:  # noqa: BLE001 — skip honesto fuera del job PG
        require_or_skip(exc, required_env=_REQUIRED_ENV, what="drift de esquema")
        return

    try:
        async with engine.connect() as connection:

            def _compare(sync_connection: Any) -> list[Any]:
                context = MigrationContext.configure(
                    sync_connection,
                    opts={"include_object": alembic_include_object()},
                )
                return list(compare_metadata(context, Base.metadata))

            differences = await connection.run_sync(_compare)
    finally:
        await engine.dispose()

    formatted = "\n".join(repr(item) for item in differences)
    assert differences == [], (
        "Drift de esquema no declarado. O falta la migración, o falta declarar el objeto "
        "en Base.metadata. NO amplíes la allowlist sin motivo:\n" + formatted
    )


def test_allowlist_is_not_empty_and_has_reasons() -> None:
    """La allowlist es deuda declarada: cada entrada lleva motivo no vacío."""
    from bolsa_infrastructure.database.schema_contract import KNOWN_SCHEMA_DIVERGENCES

    assert KNOWN_SCHEMA_DIVERGENCES, "La allowlist vacía indicaría que el drift desapareció"
    for item in KNOWN_SCHEMA_DIVERGENCES:
        assert item.name
        assert len(item.reason.strip()) >= 20, f"Motivo insuficiente para {item.name}"


@pytest.mark.asyncio
async def test_foreign_key_actions_match_metadata() -> None:
    """``ON DELETE`` / ``ON UPDATE`` de TODAS las FK: lo que ``alembic check`` no ve.

    Alembic 1.19.1 compara la existencia de la FK, **no sus acciones**: el drift de
    ``investment_accounts.active_profile_id`` (BD ``RESTRICT`` + ``ON UPDATE CASCADE``
    frente a metadata ``SET NULL`` sin ``onupdate``) pasaba el gate sin ser detectado.
    Este test lee ``pg_constraint`` y exige que metadata y BD digan lo mismo.

    Solo se tolera lo que la allowlist declara como deuda (``custody_obligation``): una
    FK en BD sin equivalente en metadata falla, y una FK de metadata sin equivalente en
    BD también.
    """
    from bolsa_infrastructure.database.models import Base
    from bolsa_infrastructure.database.schema_contract import is_known_divergence

    try:
        _factory, engine = await make_pg_session_factory()
    except Exception as exc:  # noqa: BLE001 — skip honesto fuera del job PG
        require_or_skip(exc, required_env=_REQUIRED_ENV, what="acciones de FK")
        return

    query = sa.text(
        """
        SELECT rel.relname, att.attname, c.confdeltype, c.confupdtype
        FROM pg_constraint c
        JOIN pg_class rel ON rel.oid = c.conrelid
        JOIN pg_namespace n ON n.oid = rel.relnamespace
        JOIN pg_attribute att ON att.attrelid = c.conrelid AND att.attnum = c.conkey[1]
        WHERE c.contype = 'f' AND n.nspname = 'public'
        ORDER BY rel.relname, att.attname
        """
    )

    try:
        async with engine.connect() as connection:

            def _read(sync_connection: Any) -> list[tuple[str, str, str, str]]:
                return [
                    (str(row[0]), str(row[1]), str(row[2]), str(row[3]))
                    for row in sync_connection.execute(query)
                ]

            db_rows = await connection.run_sync(_read)
    finally:
        await engine.dispose()

    expected: dict[tuple[str, str], tuple[str | None, str | None]] = {}
    for table in Base.metadata.tables.values():
        for fk in table.foreign_keys:
            expected[(table.name, fk.parent.name)] = (fk.ondelete, fk.onupdate)

    problems: list[str] = []
    seen: set[tuple[str, str]] = set()
    for table, column, deltype, updtype in db_rows:
        key = (table, column)
        if key not in expected:
            if is_known_divergence(table, "table"):
                continue
            problems.append(f"{table}.{column}: FK en la BD sin FK equivalente en metadata")
            continue
        seen.add(key)
        expected_delete, expected_update = expected[key]
        db_delete = _FK_ACTIONS.get(deltype, f"?{deltype}")
        db_update = _FK_ACTIONS.get(updtype, f"?{updtype}")
        if (expected_delete or None) != db_delete:
            problems.append(
                f"{table}.{column}: ON DELETE metadata={expected_delete!r} BD={db_delete!r}"
            )
        if (expected_update or None) != db_update:
            problems.append(
                f"{table}.{column}: ON UPDATE metadata={expected_update!r} BD={db_update!r}"
            )

    for table, column in sorted(set(expected) - seen):
        problems.append(f"{table}.{column}: FK declarada en metadata pero ausente en la BD")

    formatted = "\n".join(problems)
    assert problems == [], (
        "Acciones de FK divergentes entre metadata y BD (Alembic no las compara). "
        "Alinea la metadata con la BD (o migra la FK), no amplíes la allowlist:\n" + formatted
    )
