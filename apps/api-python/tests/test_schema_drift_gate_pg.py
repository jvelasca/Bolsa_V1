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

from tests._estudio_pg_helpers import make_pg_session_factory, require_or_skip

if sys.platform == "win32":  # psycopg async no soporta ProactorEventLoop.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

_REQUIRED_ENV = "SCHEMA_DRIFT_PG_REQUIRED"


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
