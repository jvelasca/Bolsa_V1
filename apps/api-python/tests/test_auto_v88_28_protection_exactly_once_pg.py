"""AUTO v2.88.28 — exactly-once de los hechos de PROTECTION contra PostgreSQL real.

Qué certifica este fichero, y por qué sólo puede certificarse contra PG real:

1. **Cada ``kind`` del vocabulario con su ``revision_id`` es idempotente.** El MISMO hecho
   (misma clave determinista) escrito dos veces es UNA fila: ``INSERT ... ON CONFLICT DO
   NOTHING`` sobre el índice único PARCIAL de la ``048``. Un reintento del sumidero —o su
   recuperación tras un crash— deja de duplicar la transición de protección.
2. **Dos procesos que recuperan el mismo hecho escriben UNA fila.** Se demuestra con dos
   sesiones/conexiones independientes que publican la misma transición.
3. **Sin revisión durable nada cambia.** Un ``auto_protection_event`` sin identidad
   (``dedupe_key = NULL``) conserva el INSERT plano: dos altas son DOS filas. El índice es
   parcial, así que el histórico y los hechos sin revisión no cambian de comportamiento.

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
_MARKER = "v88-28-pg"
_ACCOUNT = f"acc-{_MARKER}"
_ENGINE = _MARKER
_CYCLE = f"cyc-{_MARKER}"


def _require_or_skip(exc: Exception) -> None:
    if os.environ.get(_REQUIRED_ENV) == "1":
        raise AssertionError(
            f"PostgreSQL requerido para el exactly-once de PROTECTION (v2.88.28) pero no "
            f"disponible: {exc}"
        ) from exc
    pytest.skip(f"PostgreSQL/patrón de hechos PROTECTION (v2.88.28) no disponible: {exc}")


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


def _dedupe_key(*, kind: str, revision_id: str) -> str | None:
    from bolsa_application.auto_operational_audit import durable_fact_dedupe_key
    from bolsa_application.auto_operational_monitor import AUTO_PROTECTION_EVENT

    return durable_fact_dedupe_key(
        event_type=AUTO_PROTECTION_EVENT,
        account_id=_ACCOUNT,
        engine_id=_ENGINE,
        cycle_id=_CYCLE,
        kind=kind,
        revision_id=revision_id,
    )


def _entry(*, kind: str, revision_id: str | None, dedupe_key: str | None) -> Any:
    from bolsa_application.auto_operational_monitor import AUTO_PROTECTION_EVENT
    from bolsa_domain.entities.cognitive_artifacts import DecisionJournalEntryRecord

    payload: dict[str, Any] = {"cycleId": _CYCLE, "engineId": _ENGINE, "kind": kind}
    if revision_id is not None:
        payload["revisionId"] = revision_id
    return DecisionJournalEntryRecord(
        id=f"JNL-{uuid.uuid4().hex[:12]}",
        decision_id=f"dec-{_MARKER}",
        event_type=AUTO_PROTECTION_EVENT,
        actor="auto-sim",
        created_at="2026-10-02T10:00:00Z",
        account_id=_ACCOUNT,
        instrument_id="AAA",
        payload=payload,
        dedupe_key=dedupe_key,
    )


def _protection_kinds() -> list[str]:
    from bolsa_application.protection_event_kind import PROTECTION_EVENT_KINDS

    return sorted(PROTECTION_EVENT_KINDS)


async def _count_by_key(factory: async_sessionmaker[AsyncSession], key: str) -> int:
    async with factory() as session:
        value = await session.scalar(
            text(f"SELECT COUNT(*) FROM {_TABLE} WHERE dedupe_key = :k"), {"k": key}
        )
        return int(value or 0)


async def _count_null(factory: async_sessionmaker[AsyncSession]) -> int:
    async with factory() as session:
        value = await session.scalar(
            text(
                f"SELECT COUNT(*) FROM {_TABLE} "
                f"WHERE decision_id = :d AND dedupe_key IS NULL AND event_type = 'auto_protection_event'"
            ),
            {"d": f"dec-{_MARKER}"},
        )
        return int(value or 0)


async def _cleanup(factory: async_sessionmaker[AsyncSession]) -> None:
    async with factory() as session:
        await session.execute(
            text(f"DELETE FROM {_TABLE} WHERE decision_id = :d"), {"d": f"dec-{_MARKER}"}
        )
        await session.commit()


@pytest.mark.asyncio
async def test_each_protection_kind_is_idempotent_under_retry(
    facts_pg_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Por cada ``kind``: dos altas del MISMO hecho (misma revisión) son UNA fila."""
    from bolsa_infrastructure.database.repositories.journal_repository import (
        SqlAlchemyJournalRepository,
    )

    try:
        for kind in _protection_kinds():
            revision = f"REV-{kind.lower()}"
            key = _dedupe_key(kind=kind, revision_id=revision)
            assert key is not None
            async with facts_pg_factory() as session:
                repository = SqlAlchemyJournalRepository(session)
                await repository.append(_entry(kind=kind, revision_id=revision, dedupe_key=key))
                await repository.append(_entry(kind=kind, revision_id=revision, dedupe_key=key))
                await session.commit()
            assert await _count_by_key(facts_pg_factory, key) == 1, kind
    finally:
        await _cleanup(facts_pg_factory)


@pytest.mark.asyncio
async def test_two_sessions_recovering_the_same_transition_write_one_row(
    facts_pg_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Dos procesos (sesiones/conexiones) que publican la MISMA transición ⇒ 1 fila.

    Cada proceso abre su propia sesión y commitea; la identidad determinista resuelve el
    segundo alta como no-op (``ON CONFLICT DO NOTHING``).
    """
    from bolsa_infrastructure.database.repositories.journal_repository import (
        SqlAlchemyJournalRepository,
    )

    kind = "TRAIL_ADVANCED"
    revision = "REV-shared"
    key = _dedupe_key(kind=kind, revision_id=revision)
    assert key is not None
    try:
        async with facts_pg_factory() as s1:
            await SqlAlchemyJournalRepository(s1).append(
                _entry(kind=kind, revision_id=revision, dedupe_key=key)
            )
            await s1.commit()
        async with facts_pg_factory() as s2:
            await SqlAlchemyJournalRepository(s2).append(
                _entry(kind=kind, revision_id=revision, dedupe_key=key)
            )
            await s2.commit()
        assert await _count_by_key(facts_pg_factory, key) == 1
    finally:
        await _cleanup(facts_pg_factory)


@pytest.mark.asyncio
async def test_without_a_revision_the_plain_insert_is_kept(
    facts_pg_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Sin revisión (``dedupe_key = NULL``) el comportamiento previo se conserva: dos filas."""
    from bolsa_infrastructure.database.repositories.journal_repository import (
        SqlAlchemyJournalRepository,
    )

    try:
        async with facts_pg_factory() as session:
            repository = SqlAlchemyJournalRepository(session)
            await repository.append(_entry(kind="PROTECT_APPLIED", revision_id=None, dedupe_key=None))
            await repository.append(_entry(kind="PROTECT_APPLIED", revision_id=None, dedupe_key=None))
            await session.commit()
        assert await _count_null(facts_pg_factory) == 2
    finally:
        await _cleanup(facts_pg_factory)
