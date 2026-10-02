"""AUTO v2.88.27 — identidad determinista de los hechos M2 sobre PostgreSQL real.

Qué certifica este fichero, y por qué solo se puede certificar contra PG real:

1. **La inserción es idempotente por ``dedupe_key``.** El MISMO hecho (misma clave) escrito dos
   veces es UNA fila: ``INSERT ... ON CONFLICT DO NOTHING`` sobre el índice único PARCIAL. Es lo
   que convierte un reintento del sumidero —o la recuperación de un ``SETTLEMENT`` que un crash
   dejó sin publicar— en un no-op en vez de un duplicado.
2. **Sin identidad natural nada cambia.** Un hecho sin ``dedupe_key`` (``NULL``) se inserta plano:
   dos altas del mismo contenido son DOS filas. El índice es parcial (``WHERE dedupe_key IS NOT
   NULL``), así que los ``NULL`` no colisionan y el histórico/productores sin identidad conservan
   el comportamiento previo.
3. **La migración 048 es aditiva y reversible.** ``downgrade`` a ``047_fill_price_source`` retira
   la columna y el índice; ``upgrade head`` los recrea. Sin roundtrip, "reversible" sería una
   lectura del código, no un hecho medido.

GOBIERNO DE HONESTIDAD (patrón del repo): sin PostgreSQL real hace ``pytest.skip``; con
``AUTO_OPERATIONAL_MONITOR_PG_REQUIRED=1`` un skip silencioso es un FALLO duro. NUNCA abre el
bridge LIVE (todo es SIMULATED).
"""

from __future__ import annotations

import asyncio
import os
import sys
import uuid
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

if sys.platform == "win32":  # psycopg async no soporta ProactorEventLoop.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

_DOTENV = Path(__file__).resolve().parents[3] / ".env"
_REQUIRED_ENV = "AUTO_OPERATIONAL_MONITOR_PG_REQUIRED"
_TABLE = "decision_journal_entries"
_COLUMN = "dedupe_key"
_INDEX = "uq_decision_journal_entries_dedupe_key"
_PREVIOUS_REVISION = "047_fill_price_source"
_MARKER = "v88-27-pg"


def _require_or_skip(exc: Exception) -> None:
    if os.environ.get(_REQUIRED_ENV) == "1":
        raise AssertionError(
            f"PostgreSQL requerido para los hechos durables M2 (v2.88.27) pero no disponible: {exc}"
        ) from exc
    pytest.skip(f"PostgreSQL/Alembic (hechos durables M2 v2.88.27) no disponible: {exc}")


@pytest_asyncio.fixture
async def facts_pg_factory() -> async_sessionmaker[AsyncSession]:
    from dotenv import load_dotenv

    load_dotenv(_DOTENV, override=False)
    from bolsa_infrastructure.config import get_settings
    from bolsa_infrastructure.database.migrations import ensure_migrated
    from bolsa_infrastructure.database.session import create_engine, create_session_factory

    get_settings.cache_clear()
    settings = get_settings()
    try:
        await asyncio.to_thread(ensure_migrated)
        engine = create_engine(settings)
    except Exception as exc:  # noqa: BLE001 — skip/fail gate honesto por env.
        _require_or_skip(exc)
        raise
    factory = create_session_factory(engine)
    try:
        yield factory
    finally:
        await engine.dispose()


def _index_present(connection: Any, name: str) -> bool:
    return (
        connection.execute(
            text("SELECT 1 FROM pg_indexes WHERE schemaname='public' AND indexname=:n"),
            {"n": name},
        ).scalar_one_or_none()
        is not None
    )


def _column_present(connection: Any, table: str, column: str) -> bool:
    return (
        connection.execute(
            text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_schema='public' AND table_name=:t AND column_name=:c"
            ),
            {"t": table, "c": column},
        ).scalar_one_or_none()
        is not None
    )


def _entry(*, event_type: str, dedupe_key: str | None) -> Any:
    from bolsa_domain.entities.cognitive_artifacts import DecisionJournalEntryRecord

    return DecisionJournalEntryRecord(
        id=f"JNL-{uuid.uuid4().hex[:12]}",
        decision_id=f"dec-{_MARKER}",
        event_type=event_type,
        actor="auto-sim",
        created_at="2026-10-02T10:00:00Z",
        account_id=f"acc-{_MARKER}",
        instrument_id="AAA",
        payload={"cycleId": f"cyc-{_MARKER}", "engineId": _MARKER},
        dedupe_key=dedupe_key,
    )


async def _count(factory: async_sessionmaker[AsyncSession], *, dedupe_key: str | None) -> int:
    async with factory() as session:
        if dedupe_key is None:
            statement = text(
                f"SELECT COUNT(*) FROM {_TABLE} WHERE decision_id = :d AND {_COLUMN} IS NULL"
            )
            value = await session.scalar(statement, {"d": f"dec-{_MARKER}"})
        else:
            statement = text(f"SELECT COUNT(*) FROM {_TABLE} WHERE {_COLUMN} = :k")
            value = await session.scalar(statement, {"k": dedupe_key})
        return int(value or 0)


async def _cleanup(factory: async_sessionmaker[AsyncSession]) -> None:
    async with factory() as session:
        await session.execute(
            text(f"DELETE FROM {_TABLE} WHERE decision_id = :d"), {"d": f"dec-{_MARKER}"}
        )
        await session.commit()


@pytest.mark.asyncio
async def test_append_same_dedupe_key_is_idempotent(
    facts_pg_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Dos altas del MISMO hecho (misma clave) son UNA fila: el reintento es un no-op."""
    from bolsa_infrastructure.database.repositories.journal_repository import (
        SqlAlchemyJournalRepository,
    )

    key = f"auto_cycle_settlement:acc-{_MARKER}:{_MARKER}:cyc-{_MARKER}"
    try:
        async with facts_pg_factory() as session:
            repository = SqlAlchemyJournalRepository(session)
            await repository.append(_entry(event_type="auto_cycle_settlement", dedupe_key=key))
            await repository.append(_entry(event_type="auto_cycle_settlement", dedupe_key=key))
            await session.commit()
        assert await _count(facts_pg_factory, dedupe_key=key) == 1
    finally:
        await _cleanup(facts_pg_factory)


@pytest.mark.asyncio
async def test_append_without_dedupe_key_keeps_plain_insert(
    facts_pg_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Sin identidad natural (``NULL``) el comportamiento previo se conserva: dos filas."""
    from bolsa_infrastructure.database.repositories.journal_repository import (
        SqlAlchemyJournalRepository,
    )

    try:
        async with facts_pg_factory() as session:
            repository = SqlAlchemyJournalRepository(session)
            await repository.append(_entry(event_type="auto_entry_decision", dedupe_key=None))
            await repository.append(_entry(event_type="auto_entry_decision", dedupe_key=None))
            await session.commit()
        assert await _count(facts_pg_factory, dedupe_key=None) == 2
    finally:
        await _cleanup(facts_pg_factory)


@pytest.mark.asyncio
async def test_migration_048_roundtrip_creates_and_drops_the_dedupe_key(
    facts_pg_factory: async_sessionmaker[AsyncSession],
) -> None:
    """``downgrade`` a 047 retira la columna y su índice único parcial; ``upgrade head`` los recrea."""
    pytest.importorskip("alembic")
    from dotenv import load_dotenv

    load_dotenv(_DOTENV, override=False)

    from alembic import command
    from sqlalchemy import create_engine

    from bolsa_infrastructure.config import get_settings
    from bolsa_infrastructure.database.migrations import _alembic_config, alembic_head

    get_settings.cache_clear()
    settings = get_settings()
    url = settings.database_url
    assert url is not None
    url = url.replace("postgresql://", "postgresql+psycopg://", 1).split("?", 1)[0]

    assert alembic_head() == "048_journal_entry_dedupe_key"

    engine = create_engine(url)
    cfg = _alembic_config()
    try:
        with engine.connect() as connection:
            assert _column_present(connection, _TABLE, _COLUMN), "048 debe crear dedupe_key"
            assert _index_present(connection, _INDEX), "048 debe crear el índice único parcial"

        with engine.connect() as connection:
            cfg.attributes["connection"] = connection
            command.downgrade(cfg, _PREVIOUS_REVISION)
            cfg.attributes.pop("connection", None)

        with engine.connect() as connection:
            assert not _column_present(connection, _TABLE, _COLUMN), (
                "downgrade retira la columna dedupe_key"
            )
            assert not _index_present(connection, _INDEX), "downgrade retira el índice"

        with engine.connect() as connection:
            cfg.attributes["connection"] = connection
            command.upgrade(cfg, "head")
            cfg.attributes.pop("connection", None)

        with engine.connect() as connection:
            assert _column_present(connection, _TABLE, _COLUMN), "upgrade recrea dedupe_key"
            assert _index_present(connection, _INDEX), "upgrade recrea el índice"
    finally:
        engine.dispose()
