"""V2.46.x (AUTO-6 hardening) — recuperación de la parada dura contra PostgreSQL REAL.

El gemelo hermético (``test_auto_v46_hardkill_recovery.py``) certifica la mecánica con los
stores in-memory. Este fichero certifica lo que solo se puede medir con PostgreSQL y con
procesos distintos:

1. **El HALT durable es la autoridad entre procesos** — un worker lo activa y lo persiste;
   un worker NUEVO (otra sesión, cero RAM compartida) lo RESTAURA al arrancar. Es el
   ``WORKER 1 → KILL → CRASH → WORKER 2`` que la auditoría de ``v2.46-beta`` marcó como P0
   abierto (el Crash Day certificaba crash con ``RISK_OFF``/``time_exit``, no con HARD KILL).
2. **La liberación exige ``reconciliation_id`` y viaja por la vía de producción** — la
   escribe el endpoint real (``POST /api/risk/kill-switch/durable-release``) y el worker la
   ADOPTA en su siguiente turno sin reiniciarse (``_v2_load_kill_state``), siempre que la
   liberación sea POSTERIOR a la activación.
3. **Una liberación más ANTIGUA que el halt no lo levanta** — una re-activación posterior
   manda sobre un release previo (se comparan instantes, no texto).

GOBIERNO DE HONESTIDAD (patrón del repo): sin PostgreSQL real hace ``pytest.skip``; con
``AUTO_HARDKILL_PG_REQUIRED=1`` un skip silencioso es un FALLO duro. NUNCA abre el bridge LIVE.
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

if sys.platform == "win32":  # psycopg async no soporta ProactorEventLoop.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

_DOTENV = Path(__file__).resolve().parents[3] / ".env"
_REQUIRED_ENV = "AUTO_HARDKILL_PG_REQUIRED"
_ENGINE_ID = "auto-sim"


def _require_or_skip(exc: Exception) -> None:
    if os.environ.get(_REQUIRED_ENV) == "1":
        raise AssertionError(
            f"PostgreSQL requerido para la recuperación de la parada dura AUTO-6 pero no "
            f"disponible: {exc}"
        ) from exc
    pytest.skip(f"PostgreSQL/Alembic (parada dura AUTO-6) no disponible: {exc}")


@pytest_asyncio.fixture
async def hardkill_pg_factory() -> async_sessionmaker[AsyncSession]:
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


async def _cleanup(
    factory: async_sessionmaker[AsyncSession], *, account_id: str
) -> None:
    from bolsa_infrastructure.database.models.tables import AutoKillStateRow

    async with factory() as session:
        await session.execute(
            delete(AutoKillStateRow).where(AutoKillStateRow.account_id == account_id)
        )
        await session.commit()


def _worker(session: AsyncSession, *, account_id: str) -> object:
    """Worker mínimo cableado a la parada durable real (sin el resto del motor)."""
    from bolsa_api.background.auto_simulation_worker import AutoSimulationWorker
    from bolsa_application.kill_switch_store import PostgresKillSwitchStore

    return AutoSimulationWorker(
        engine_id=_ENGINE_ID,
        account_id=account_id,
        kill_switch_store=PostgresKillSwitchStore(session),
    )


@pytest.mark.asyncio
async def test_the_full_hardkill_lifecycle_converges_against_postgres(
    hardkill_pg_factory: async_sessionmaker[AsyncSession],
) -> None:
    """engage durable → crash → restart HALTED → release con reconciliación → RUNNING."""
    import uuid

    from bolsa_api.api.v1.routes.risk import (
        DurableKillReleaseBody,
        post_durable_kill_release,
    )

    account_id = f"acc-hardkill-{uuid.uuid4().hex[:10]}"
    try:
        # T1/T2 — un worker activa y PERSISTE la parada dura (productor real tipificado).
        async with hardkill_pg_factory() as session:
            w1 = _worker(session, account_id=account_id)  # type: ignore[assignment]
            await w1.engage_kill_switch_durable(  # type: ignore[attr-defined]
                "RECONCILIATION_FAILURE", at="2026-09-15T09:00:00Z"
            )
            assert w1._v2_kill_switch_halted() is True  # type: ignore[attr-defined]

        # T3/T4 — proceso NUEVO (otra sesión): la RAM no comparte nada con el anterior.
        async with hardkill_pg_factory() as session:
            w2 = _worker(session, account_id=account_id)  # type: ignore[assignment]
            assert w2._v2_kill_switch_halted() is False  # type: ignore[attr-defined]
            await w2._v2_load_kill_state()  # type: ignore[attr-defined]
            assert w2._v2_kill_switch_halted() is True  # type: ignore[attr-defined]
            assert w2._v2_kill_switch.reason == "RECONCILIATION_FAILURE"  # type: ignore[attr-defined]

            # La liberación entra por la VÍA DE PRODUCCIÓN (el endpoint real), no por el
            # método del worker: así se mide el camino que usará un operador.
            released = await post_durable_kill_release(
                DurableKillReleaseBody(
                    accountId=account_id,
                    engineId=_ENGINE_ID,
                    reconciliationId="recon-hardkill-77",
                ),
                session,
            )
            assert released.released is True

            # El MISMO worker (sin reiniciarse) adopta la liberación en el siguiente turno.
            await w2._v2_load_kill_state()  # type: ignore[attr-defined]
            assert w2._v2_kill_switch_halted() is False  # type: ignore[attr-defined]

        # Un no-op idempotente: liberar una parada no activa no es un error.
        async with hardkill_pg_factory() as session:
            again = await post_durable_kill_release(
                DurableKillReleaseBody(
                    accountId=account_id,
                    engineId=_ENGINE_ID,
                    reconciliationId="recon-hardkill-77",
                ),
                session,
            )
            assert again.released is False
            assert again.reason == "not_engaged"
    finally:
        await _cleanup(hardkill_pg_factory, account_id=account_id)


@pytest.mark.asyncio
async def test_a_stale_release_does_not_lift_a_newer_halt_against_postgres(
    hardkill_pg_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Una liberación anterior a la re-activación NO levanta el halt vigente."""
    import uuid

    account_id = f"acc-hardkill-{uuid.uuid4().hex[:10]}"
    try:
        async with hardkill_pg_factory() as session:
            w = _worker(session, account_id=account_id)  # type: ignore[assignment]
            await w.engage_kill_switch_durable(  # type: ignore[attr-defined]
                "RECONCILIATION_FAILURE", at="2026-09-15T09:00:00Z"
            )
            await w.release_kill_switch_durable(  # type: ignore[attr-defined]
                reconciliation_ok=True, reconciliation_id="recon-old"
            )
            assert w._v2_kill_switch_halted() is False  # type: ignore[attr-defined]
            # Re-activación POSTERIOR al release.
            await w.engage_kill_switch_durable(  # type: ignore[attr-defined]
                "DUPLICATE_EXECUTION", at="2026-09-15T09:20:00Z"
            )
            assert w._v2_kill_switch_halted() is True  # type: ignore[attr-defined]

        # Proceso nuevo: lee la fila durable ENGAGED (la re-activación manda).
        async with hardkill_pg_factory() as session:
            w2 = _worker(session, account_id=account_id)  # type: ignore[assignment]
            await w2._v2_load_kill_state()  # type: ignore[attr-defined]
            assert w2._v2_kill_switch_halted() is True  # type: ignore[attr-defined]
            assert w2._v2_kill_switch.reason == "DUPLICATE_EXECUTION"  # type: ignore[attr-defined]
    finally:
        await _cleanup(hardkill_pg_factory, account_id=account_id)
