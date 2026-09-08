"""V2.13 — Multi-worker recovery concurrency: PG claim/lease under 2 sessions.

Cierra el hueco de la auditoría (H2): hasta ahora la exclusión mutua de
``claim_unknown_batch`` (SKIP LOCKED + lease) sólo se ejercitaba en InMemory
(monoproceso) o con ``session.commit`` mockeado. Aquí se valida contra PostgreSQL
real con DOS sesiones/transacciones simultáneas:

* ``test_claim_skips_row_locked_by_other_session`` — determinista: la tx A reclama
  (FOR UPDATE, sin commit) una fila UNKNOWN; la tx B concurrente NO debe obtenerla
  (SKIP LOCKED). Al commit/rollback de A, B ya sí puede.
* ``test_two_workers_claim_disjoint_unknown_batch`` — dos workers corren su
  ``claim_unknown_batch(limit=n)`` en paralelo sobre n filas UNKNOWN: la unión de
  sus claims debe cubrir exactamente las n filas sin duplicar ninguna.

Requiere DATABASE_URL. Fails hard cuando LIVE_PG_REQUIRED=1 (igual patrón que
``test_financial_integrity_pg.py``). Sin DB → skip (CI/integración lo levanta).
"""

from __future__ import annotations

import asyncio
import os
import sys
from collections.abc import AsyncIterator
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def _load_env() -> None:
    from pathlib import Path

    env_path = Path(__file__).resolve().parents[3] / ".env"
    if not env_path.exists():
        return
    try:
        from dotenv import load_dotenv
    except ImportError:  # pragma: no cover — optional dep
        return
    load_dotenv(env_path, override=False)


def _require_or_skip(exc: Exception) -> None:
    if os.environ.get("LIVE_PG_REQUIRED") == "1":
        raise AssertionError(
            f"live-pg concurrency required but PostgreSQL/Alembic unavailable: {exc}"
        ) from exc
    pytest.skip(f"PostgreSQL/Alembic no disponible: {exc}")


@pytest_asyncio.fixture
async def pg_engine() -> AsyncIterator[AsyncEngine]:
    _load_env()
    from bolsa_infrastructure.config import get_settings
    from bolsa_infrastructure.database.session import create_engine

    get_settings.cache_clear()
    settings = get_settings()
    engine = create_engine(settings)
    try:
        async with engine.connect() as conn:
            await conn.execute(select(1))
            version = await conn.execute(text("SELECT version_num FROM alembic_version"))
            versions = {row[0] for row in version}
            if "022_live_orders_exec" not in versions:
                raise RuntimeError(
                    f"alembic_version is {versions!r}; "
                    "expected 022_live_orders_exec (V2.14 live_orders head)"
                )
    except Exception as exc:  # noqa: BLE001
        await engine.dispose()
        _require_or_skip(exc)
        raise

    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def session_factory(
    pg_engine: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(pg_engine, expire_on_commit=False)


async def _seed_unknown(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    count: int,
    account_id: str,
) -> list[str]:
    from bolsa_analytics.cognitive.live_order import (
        build_live_order,
        transition_live_order,
    )
    from bolsa_application.live_order_store import PostgresLiveOrderStore

    ids: list[str] = []
    async with session_factory() as session:
        store = PostgresLiveOrderStore(session)
        for _ in range(count):
            order_id = f"lo-conc-{uuid4().hex[:10]}"
            built = build_live_order(
                order_id=order_id,
                instrument_id="inst-conc-1",
                side="buy",
                quantity=100,
                account_id=account_id,
            )
            unknown = transition_live_order(
                transition_live_order(built, "SUBMITTING"),
                "UNKNOWN",
            )
            await store.put(unknown, account_id=account_id)
            ids.append(order_id)
        await session.commit()
    return ids


async def _claim_ids(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    worker_id: str,
    limit: int,
    stale_after_seconds: int = 120,
) -> list[str]:
    from bolsa_application.live_order_store import PostgresLiveOrderStore

    async with session_factory() as session:
        store = PostgresLiveOrderStore(session)
        rows = await store.claim_unknown_batch(
            limit=limit,
            worker_id=worker_id,
            stale_after_seconds=stale_after_seconds,
        )
        # No se commitea aquí: el lease queda en la tx del llamador (put) o se
        # libera al cerrar. Para el test usamos rollback al final (no estado).
        await session.rollback()
        return [r.order_id for r in rows]


@pytest.mark.asyncio
async def test_claim_skips_row_locked_by_other_session(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Determinista: una fila UNKNOWN lockeada por A (sin commit) la skipea B."""
    from bolsa_application.live_order_store import PostgresLiveOrderStore

    account_id = f"acc-conc-lock-{uuid4().hex[:8]}"
    issue_id = await _seed_unknown(session_factory, count=1, account_id=account_id)

    # A: reclama y mantiene la tx abierta (FOR UPDATE, sin commit) → lock vivo.
    async with session_factory() as session_a:
        store_a = PostgresLiveOrderStore(session_a)
        rows_a = await store_a.claim_unknown_batch(
            limit=10, worker_id="worker-a", stale_after_seconds=120
        )
        claimed_a = {r.order_id for r in rows_a}
        assert issue_id[0] in claimed_a  # A tiene la fila
        # NO commit: el lock FOR UPDATE persiste en la tx de A.

        # B: en una tx independiente SKIP LOCKED no debe ver la fila de A.
        async with session_factory() as session_b:
            store_b = PostgresLiveOrderStore(session_b)
            rows_b = await store_b.claim_unknown_batch(
                limit=10, worker_id="worker-b", stale_after_seconds=120
            )
            claimed_b = {r.order_id for r in rows_b}
            assert not (claimed_b & claimed_a)  # ninguna fila duplicada

        # Cierra tx de A (rollback) → su claim se anula y B ya podría reapropiar.
        await session_a.rollback()

    # Tras rollback de A la fila vuelve a UNKNOWN y un nuevo claim la toma.
    from bolsa_application.live_order_store import PostgresLiveOrderStore

    async with session_factory() as session:
        store = PostgresLiveOrderStore(session)
        rows = await store.claim_unknown_batch(
            limit=10, worker_id="worker-re", stale_after_seconds=120
        )
        assert issue_id[0] in {r.order_id for r in rows}
        await session.rollback()


@pytest.mark.asyncio
async def test_two_workers_claim_disjoint_unknown_batch(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Dos workers dividen el lote UNKNOWN sin duplicar (unión == seed exacta)."""
    from bolsa_application.live_order_store import PostgresLiveOrderStore

    n = 4
    account_id = f"acc-conc-par-{uuid4().hex[:8]}"
    seeded = set(await _seed_unknown(session_factory, count=n, account_id=account_id))

    async def _run(worker_id: str) -> set[str]:
        async with session_factory() as s:
            store = PostgresLiveOrderStore(s)
            rows = await store.claim_unknown_batch(
                limit=n, worker_id=worker_id, stale_after_seconds=120
            )
            got = {r.order_id for r in rows}
            await s.rollback()  # no materializar lease (aislamiento de test)
        return got

    # Lanzar dos claims en paralelo sobre el mismo conjunto n.
    a_task = asyncio.create_task(_run("worker-x"))
    b_task = asyncio.create_task(_run("worker-y"))
    (claimed_a, claimed_b) = await asyncio.gather(a_task, b_task)

    union = claimed_a | claimed_b
    overlap = claimed_a & claimed_b
    # Ninguna fila asignada a dos workers al mismo tiempo.
    assert not overlap, f"doble-claim en la misma ventana: {overlap}"
    # Entre los dos cubren TODO el lote (no pierden filas bajo contención).
    assert union == seeded, f"lote no cubierto: missing {seeded - union}, extra {union - seeded}"
