"""V2.46.x (AUTO-6 hardening) — inyección de crash sobre PostgreSQL REAL.

Gemelo PG de la Capa 1 de ``test_auto_v46_crash_injection_matrix.py``. Certifica, contra
PostgreSQL y con SESIONES DISTINTAS (cero RAM compartida entre "procesos"), lo que el
Crash Day determinista no podía cubrir porque el broker SIM liquidaba todas las tranchas en
el mismo tick: una muerte EN MEDIO de la materialización.

Transiciones críticas medidas:

* ``CRASH_AFTER_APPLYING`` — la fila queda ``APPLYING`` con el lease del dueño caído. El
  reinicio (otra sesión) RECLAMA el lease vencido y materializa UNA vez.
* ``CRASH_AFTER_PARTIAL_FILL`` — la trancha #1 queda ``APPLIED``; muere con la #2 en
  ``APPLYING``. El reinicio materializa SOLO la #2: el total es la suma, nunca el doble.

GOBIERNO DE HONESTIDAD (patrón del repo): sin PostgreSQL real hace ``pytest.skip``; con
``AUTO_CRASH_INJECT_PG_REQUIRED=1`` un skip silencioso es un FALLO duro. NUNCA abre LIVE.
"""

from __future__ import annotations

import asyncio
import os
import sys
import uuid
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

if sys.platform == "win32":  # psycopg async no soporta ProactorEventLoop.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

_DOTENV = Path(__file__).resolve().parents[3] / ".env"
_REQUIRED_ENV = "AUTO_CRASH_INJECT_PG_REQUIRED"
_ACCOUNT = "acc-crash-inject"


def _require_or_skip(exc: Exception) -> None:
    if os.environ.get(_REQUIRED_ENV) == "1":
        raise AssertionError(
            f"PostgreSQL requerido para la inyección de crash AUTO-6 pero no disponible: {exc}"
        ) from exc
    pytest.skip(f"PostgreSQL/Alembic (inyección de crash AUTO-6) no disponible: {exc}")


@pytest_asyncio.fixture
async def crash_pg_factory() -> async_sessionmaker[AsyncSession]:
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
    factory: async_sessionmaker[AsyncSession], *, execution_ids: tuple[str, ...]
) -> None:
    from bolsa_infrastructure.database.models.tables import (
        ExecutionEventRow,
        SimFillFinanceContextRow,
    )

    async with factory() as session:
        await session.execute(
            delete(SimFillFinanceContextRow).where(
                SimFillFinanceContextRow.execution_id.in_(execution_ids)
            )
        )
        await session.execute(
            delete(ExecutionEventRow).where(
                ExecutionEventRow.execution_id.in_(execution_ids)
            )
        )
        await session.commit()


class _LedgerEffect:
    """El efecto financiero: idempotente por ``execution_id`` (como el kernel real)."""

    def __init__(self) -> None:
        self.applied: list[str] = []

    async def apply(self, execution: object) -> bool:
        execution_id = str(getattr(execution, "execution_id", ""))
        if execution_id in self.applied:
            return False
        self.applied.append(execution_id)
        return True


def _event(execution_id: str, qty: float = 100.0) -> object:
    from bolsa_application.execution_event import ExecutionEvent

    return ExecutionEvent(
        execution_id=execution_id,
        order_id=f"o-{execution_id}",
        venue="paper",
        qty=qty,
        account_id=_ACCOUNT,
    )


@pytest.mark.asyncio
async def test_crash_while_applying_is_reclaimed_and_applied_once_pg(
    crash_pg_factory: async_sessionmaker[AsyncSession],
) -> None:
    """APPLYING con dueño caído: el reinicio (otra sesión) reclama y aplica UNA vez."""
    from bolsa_application.execution_event import (
        PostgresExecutionEventStore,
        apply_execution_financial_once,
    )

    execution_id = f"ev-applying-{uuid.uuid4().hex[:10]}"
    event = _event(execution_id)
    ledger = _LedgerEffect()
    try:
        # PROCESO 1: captura y gana el APPLYING; muere sin terminal (kill -9 implícito).
        async with crash_pg_factory() as session:
            store = PostgresExecutionEventStore(session)
            await store.capture(event)
            assert await store.start_apply(execution_id, owner="w1") is True
            row = await store.get(execution_id)
            assert row is not None and row.status == "APPLYING"
            await session.commit()

        # PROCESO 2 (reinicio, otra sesión): reclama el lease vencido y materializa.
        async with crash_pg_factory() as session:
            store = PostgresExecutionEventStore(session)
            outcome = await apply_execution_financial_once(
                store,
                execution=event,
                apply_finance=ledger.apply,
                owner="w2",
                lease_window_seconds=0,
            )
            assert outcome == "applied"
            await session.commit()
        assert ledger.applied == [execution_id]

        # PROCESO 3: el terminal APPLIED es durable → no hay segundo efecto.
        async with crash_pg_factory() as session:
            store = PostgresExecutionEventStore(session)
            again = await apply_execution_financial_once(
                store,
                execution=event,
                apply_finance=ledger.apply,
                owner="w3",
                lease_window_seconds=0,
            )
            assert again == "already_applied"
        assert ledger.applied == [execution_id]
    finally:
        await _cleanup(crash_pg_factory, execution_ids=(execution_id,))


@pytest.mark.asyncio
async def test_crash_between_two_partial_fills_never_doubles_pg(
    crash_pg_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Trancha #1 APPLIED; crash con la #2 en APPLYING: el reinicio aplica SOLO la #2."""
    from bolsa_application.execution_event import (
        PostgresExecutionEventStore,
        apply_execution_financial_once,
    )

    first_id = f"fill-1a-{uuid.uuid4().hex[:10]}"
    second_id = f"fill-1b-{uuid.uuid4().hex[:10]}"
    first = _event(first_id, qty=60.0)
    second = _event(second_id, qty=40.0)
    ledger = _LedgerEffect()
    try:
        async with crash_pg_factory() as session:
            store = PostgresExecutionEventStore(session)
            assert (
                await apply_execution_financial_once(
                    store,
                    execution=first,
                    apply_finance=ledger.apply,
                    owner="w1",
                    lease_window_seconds=0,
                )
                == "applied"
            )
            # La trancha #2 queda en vuelo; CRASH en medio del fill.
            await store.capture(second)
            assert await store.start_apply(second_id, owner="w1") is True
            await session.commit()
        assert ledger.applied == [first_id]

        async with crash_pg_factory() as session:
            store = PostgresExecutionEventStore(session)
            assert (
                await apply_execution_financial_once(
                    store,
                    execution=second,
                    apply_finance=ledger.apply,
                    owner="w2",
                    lease_window_seconds=0,
                )
                == "applied"
            )
            await session.commit()

        assert ledger.applied == [first_id, second_id], (
            "el total es la suma de las tranchas, nunca el doble"
        )
    finally:
        await _cleanup(crash_pg_factory, execution_ids=(first_id, second_id))
