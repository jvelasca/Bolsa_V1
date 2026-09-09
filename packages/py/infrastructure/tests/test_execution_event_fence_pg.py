"""V2.21 / A8 (M1 · fencing P1-01b) — lease_generation proof on REAL PostgreSQL.

La migración 026 añade ``execution_events.lease_generation`` (token monótono). Un
terminal (``mark_applied``/``mark_failed``/``mark_retry``) con fencing exige
coincidencia ``lease_owner`` + ``lease_generation`` con la fila. Si worker-B roba
la lease stale de worker-A (reclaim → bump de generación), el ``mark_applied``
tardío de worker-A debe fallar (rowcount 0) y NO puede finalizar una fila ajena.

* Real PG (DATABASE_URL). Requiere esquema a head 026 (columna ``lease_generation``).
  Si no hay PG o falta la columna → skip salvo ``EXECUTION_FENCE_PG_REQUIRED=1``.
* Escribe SOLO filas desechables (execution_id único) y las borra al final.
* Offline: el mismo invariante se cubre con la tienda en memoria en
  ``packages/py/application/tests/test_execution_event.py`` (estilo dual).
"""

from __future__ import annotations

import asyncio
import os
import sys
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

pytestmark = pytest.mark.asyncio
_PG_REQUIRED = "EXECUTION_FENCE_PG_REQUIRED"


def _load_env() -> None:
    from pathlib import Path

    env_path = Path(__file__).resolve().parents[4] / ".env"
    if not env_path.exists():
        return
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(env_path, override=False)


def _require_or_skip(exc: Exception) -> None:
    if os.environ.get(_PG_REQUIRED) == "1":
        raise AssertionError(
            f"execution_event fence PG required but unavailable: {exc}"
        ) from exc
    pytest.skip(f"PostgreSQL/026 no disponible: {exc}")


@pytest_asyncio.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    _load_env()
    from bolsa_infrastructure.config import get_settings
    from bolsa_infrastructure.database.session import create_engine, create_session_factory

    get_settings.cache_clear()
    settings = get_settings()
    engine = create_engine(settings)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
            col = await conn.execute(
                text(
                    "SELECT 1 FROM information_schema.columns "
                    "WHERE table_schema = 'public' AND table_name = 'execution_events' "
                    "AND column_name = 'lease_generation'"
                )
            )
            if col.scalar() is None:
                raise RuntimeError(
                    "execution_events.lease_generation missing — Alembic 026 required"
                )
    except Exception as exc:  # noqa: BLE001
        await engine.dispose()
        _require_or_skip(exc)
        raise  # unreachable

    factory = create_session_factory(engine)
    async with factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
    await engine.dispose()


async def _cleanup(session: AsyncSession, execution_id: str) -> None:
    await session.execute(
        text("DELETE FROM execution_events WHERE execution_id = :p"),
        {"p": execution_id},
    )
    await session.commit()


def _sample(execution_id: str) -> object:
    from bolsa_application.execution_event import ExecutionEvent

    return ExecutionEvent(
        execution_id=execution_id,
        order_id=f"ord-{execution_id}",
        venue="PAPER",
        qty=Decimal("1.0"),
        account_id="acc-fence",
        fill_seq=1,
    )


@pytest.mark.asyncio
async def test_lease_generation_bumps_on_acquire_and_reclaim(db_session: AsyncSession) -> None:
    """Dos procesos: A adquiere APPLYING (gen1); B roba por stale (gen2). Un
    mark_applied tardío de A con su token viejo (gen1) NO puede finalizar."""
    from bolsa_application.execution_event import PostgresExecutionEventStore

    execution_id = f"fence-{uuid4().hex}"
    store = PostgresExecutionEventStore(db_session)
    try:
        ev = _sample(execution_id)
        assert await store.capture(ev) == "inserted"

        # A adquiere (gen 1).
        assert await store.start_apply(execution_id, owner="worker-a") is True
        a_row = await store.get(execution_id)
        assert a_row is not None
        gen_a = a_row.lease_generation
        assert gen_a >= 1
        assert a_row.status == "APPLYING"

        # Simula que A cayó hace tiempo: envejecemos su lease (updated_at al pasado)
        # para que el reclaim pueda considerarla stale (dueño muerto).
        past = datetime.now(UTC) - timedelta(seconds=120)
        await db_session.execute(
            text(
                "UPDATE execution_events SET updated_at = :p "
                "WHERE execution_id = :e"
            ),
            {"p": past, "e": execution_id},
        )
        await db_session.commit()

        # B reclama como stale (lease caducada) → roba, gen bump.
        stale_before = datetime.now(UTC) - timedelta(seconds=5)
        assert await store.reclaim_stale_apply(
            execution_id, owner="worker-b", stale_before=stale_before
        ) is True
        b_row = await store.get(execution_id)
        assert b_row is not None
        assert b_row.status == "APPLYING"
        assert b_row.lease_owner == "worker-b"
        assert b_row.lease_generation > gen_a

        # A NI TERMINA: su mark_applied con el token viejo queda en 0 filas.
        late = await store.mark_applied(
            execution_id,
            lease_owner="worker-a",
            lease_generation=gen_a,
        )
        assert late is False
        still = await store.get(execution_id)
        assert still is not None
        assert still.status == "APPLYING"  # A no pudo finalizar la fila ajena.

        # Ni un mark_failed/mark_retry con fence viejo.
        assert (
            await store.mark_failed(
                execution_id, error="late", lease_owner="worker-a",
                lease_generation=gen_a,
            )
            is False
        )
        assert (
            await store.mark_retry(
                execution_id, error="late", lease_owner="worker-a",
                lease_generation=gen_a,
            )
            is False
        )

        # B (dueno legítimo con gen nueva) sí terminaliza → APPLIED, lease limpia.
        assert await store.mark_applied(
            execution_id,
            lease_owner="worker-b",
            lease_generation=b_row.lease_generation,
        ) is True
        final = await store.get(execution_id)
        assert final is not None
        assert final.status == "APPLIED"
        assert final.lease_owner is None
    finally:
        await _cleanup(db_session, execution_id)
