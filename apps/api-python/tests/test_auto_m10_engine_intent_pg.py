"""M10 — la intención del operador contra PostgreSQL REAL.

Certifica lo que sólo se puede medir con base de datos:

1. La migración ``065_auto_engine_intent`` existe y la tabla acepta la fila.
2. Un ``OFF`` escrito por un proceso se LEE en otro (``WORKER 1 → OFF → restart → WORKER 2``):
   el latch del apagado sobrevive al reinicio aunque el env siga en ``ON``.
3. ``version`` cuenta escrituras y la última intención gana.
4. Un estado fuera de ``ON``/``OFF`` no se escribe (no es una decisión).

GOBIERNO DE HONESTIDAD (patrón del repo): sin PostgreSQL real hace ``pytest.skip``; con
``AUTO_ENGINE_INTENT_PG_REQUIRED=1`` un skip silencioso es un FALLO duro.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bolsa_application.auto_engine_intent_store import (
    INTENT_OFF,
    INTENT_ON,
    AutoEngineIntent,
    PostgresAutoEngineIntentStore,
)

if sys.platform == "win32":  # psycopg async no soporta ProactorEventLoop.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

_DOTENV = Path(__file__).resolve().parents[3] / ".env"
_REQUIRED_ENV = "AUTO_ENGINE_INTENT_PG_REQUIRED"
_ACCOUNT = "acc-m10-pg"
_ENGINE = "eng-m10-pg"


def _require_or_skip(exc: Exception) -> None:
    if os.environ.get(_REQUIRED_ENV) == "1":
        raise AssertionError(
            f"PostgreSQL requerido para la intención durable AUTO (M10) pero no disponible: {exc}"
        ) from exc
    pytest.skip(f"PostgreSQL/Alembic (intención durable M10) no disponible: {exc}")


@pytest_asyncio.fixture
async def intent_pg_factory() -> async_sessionmaker[AsyncSession]:
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
        await _cleanup(factory)
        yield factory
    finally:
        await _cleanup(factory)
        await engine.dispose()


async def _cleanup(factory: async_sessionmaker[AsyncSession]) -> None:
    from bolsa_infrastructure.database.models.tables import AutoEngineIntentRow

    async with factory() as session:
        await session.execute(
            delete(AutoEngineIntentRow).where(AutoEngineIntentRow.account_id == _ACCOUNT)
        )
        await session.commit()


def _intent(state: str, *, reason: str | None = None) -> AutoEngineIntent:
    from datetime import UTC, datetime

    return AutoEngineIntent(
        account_id=_ACCOUNT,
        engine_id=_ENGINE,
        desired_state=state,
        reason=reason,
        actor="pytest",
        updated_at=datetime.now(UTC).isoformat(),
    )


@pytest.mark.asyncio
async def test_absent_intent_is_absent_not_off(
    intent_pg_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with intent_pg_factory() as session:
        assert await PostgresAutoEngineIntentStore(session).load(_ACCOUNT, _ENGINE) is None


@pytest.mark.asyncio
async def test_off_survives_a_restart_in_another_session(
    intent_pg_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with intent_pg_factory() as session:
        await PostgresAutoEngineIntentStore(session).save(_intent(INTENT_OFF, reason="maint"))

    # Otra sesión = otro proceso: cero RAM compartida, sólo la fila durable.
    async with intent_pg_factory() as session:
        loaded = await PostgresAutoEngineIntentStore(session).load(_ACCOUNT, _ENGINE)

    assert loaded is not None
    assert loaded.is_off is True
    assert loaded.reason == "maint"
    assert loaded.actor == "pytest"


@pytest.mark.asyncio
async def test_last_intent_wins_and_version_counts(
    intent_pg_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with intent_pg_factory() as session:
        store = PostgresAutoEngineIntentStore(session)
        assert await store.save(_intent(INTENT_OFF)) is True
        assert await store.save(_intent(INTENT_ON)) is False
        loaded = await store.load(_ACCOUNT, _ENGINE)

    assert loaded is not None
    assert loaded.desired_state == INTENT_ON
    assert loaded.version == 2


@pytest.mark.asyncio
async def test_unknown_state_is_refused_not_persisted(
    intent_pg_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with intent_pg_factory() as session:
        store = PostgresAutoEngineIntentStore(session)
        with pytest.raises(ValueError):
            await store.save(_intent("AUTO"))

    async with intent_pg_factory() as session:
        assert await PostgresAutoEngineIntentStore(session).load(_ACCOUNT, _ENGINE) is None
