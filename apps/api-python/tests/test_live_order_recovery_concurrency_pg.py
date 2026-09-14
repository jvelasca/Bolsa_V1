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
    from bolsa_infrastructure.database.migrations import alembic_head
    from bolsa_infrastructure.database.session import create_engine

    get_settings.cache_clear()
    settings = get_settings()
    engine = create_engine(settings)
    try:
        async with engine.connect() as conn:
            await conn.execute(select(1))
            version = await conn.execute(text("SELECT version_num FROM alembic_version"))
            versions = {row[0] for row in version}
            head = alembic_head()
            if head not in versions:
                raise RuntimeError(
                    f"alembic_version is {versions!r}; expected {head} (head aplicada)"
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


async def _purge_account(
    session_factory: async_sessionmaker[AsyncSession],
    account_id: str,
) -> None:
    """Borra las filas sembradas por ``account_id`` (hermeticidad del test).

    ``_seed_unknown`` hace ``commit`` y las filas UNKNOWN persisten en la BD
    compartida del job. Sin esta purga, el test de concurrencia ve filas de
    ejecuciones previas (``union != seeded``) y la suite se envenena a sí misma
    entre pasadas. Se borra por cuenta (no ``TRUNCATE``) para respetar el
    aislamiento multi-cuenta.
    """
    from sqlalchemy import delete

    from bolsa_infrastructure.database.models.tables import LiveOrderRow

    async with session_factory() as session:
        await session.execute(delete(LiveOrderRow).where(LiveOrderRow.account_id == account_id))
        await session.commit()


async def _purge_all_unknown(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Borra TODA fila UNKNOWN de la tabla (hermeticidad ante el claim global).

    ``claim_unknown_batch`` NO acepta ``account_id``: es una barrida global de
    ``status='UNKNOWN'`` (semántica correcta en producción — un worker de recuperación
    atiende cualquier cuenta). Por eso un test que siembra n filas y afirma
    ``union == seeded`` NO es hermético aunque purgue su propia cuenta: si otra pasada
    (o otro test) dejó filas UNKNOWN vivas, el claim también las reclamará y la unión
    excederá el lote sembrado.

    Se limpia por ``status`` (no ``TRUNCATE`` ni ``DELETE`` total) para no tocar filas
    que otros estados del ciclo de vida sí pueden necesitar.
    """
    from sqlalchemy import delete

    from bolsa_infrastructure.database.models.tables import LiveOrderRow

    async with session_factory() as session:
        await session.execute(delete(LiveOrderRow).where(LiveOrderRow.status == "UNKNOWN"))
        await session.commit()


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
    # El claim es global: sin purgar las UNKNOWN previas, A/B podrían reclamar filas
    # ajenas y las aserciones ``issue_id[0] in claimed_*`` seguirían pasando por azar.
    await _purge_all_unknown(session_factory)
    issue_id = await _seed_unknown(session_factory, count=1, account_id=account_id)
    try:
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
    finally:
        await _purge_account(session_factory, account_id)


@pytest.mark.asyncio
async def test_two_workers_claim_disjoint_unknown_batch(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Dos workers con leases VIVOS y solapados se reparten el lote sin duplicar.

    Nota de honestidad (bug real de este test, no flakiness): antes se hacía
    ``asyncio.gather`` de dos ``claim_unknown_batch`` y **cada uno hacía rollback
    inmediato**. Eso NO certifica la exclusión mutua de producción, la refuta: en
    PostgreSQL real el ``SELECT ... FOR UPDATE SKIP LOCKED`` de Y puede ejecutarse
    *después* de que X haya hecho rollback, viendo las filas ya liberadas y
    reclamándolas otra vez. El resultado dependía del entrelazado del event loop
    (a veces solapaban, a veces no) → verde/rojo aleatorio con la semilla del
    scheduler.

    La propiedad REAL que ``claim_unknown_batch`` garantiza (y que sí es
    determinista) es: **mientras el lease de un worker está vivo y no expirado,
    otro worker no puede reclamar la misma fila** (FOR UPDATE + lease + SKIP
    LOCKED). Eso es lo que se certifica aquí, con las dos sesiones/leases ABIERTOS
    a la vez: X reclama n y se retiene su tx; Y reclama n concurrentemente y debe
    obtener vacío (todas lockeadas); al liberar X, Y sí puede reclamarlas. La
    cobertura total (unión == seed) se comprueba sobre el resultado de Y tras la
    liberación, que es la secuencia real de un relevo de worker.
    """
    from bolsa_application.live_order_store import PostgresLiveOrderStore

    n = 4
    account_id = f"acc-conc-par-{uuid4().hex[:8]}"
    # Hermeticidad obligatoria: ``claim_unknown_batch`` barre la tabla entera, así que
    # cualquier UNKNOWN residual de otra pasada/tests haría que ``union`` excediera
    # ``seeded``. Se limpia ANTES de sembrar (el try/finally solo purga lo propio).
    await _purge_all_unknown(session_factory)
    seeded = set(await _seed_unknown(session_factory, count=n, account_id=account_id))
    try:
        async with session_factory() as session_x:
            store_x = PostgresLiveOrderStore(session_x)
            rows_x = await store_x.claim_unknown_batch(
                limit=n, worker_id="worker-x", stale_after_seconds=120
            )
            claimed_x = {r.order_id for r in rows_x}
            assert claimed_x == seeded, f"X debe reclamar todo el lote: {claimed_x}"

            # Y reclama en una tx INDEPENDIENTE mientras X mantiene su lease vivo.
            # SKIP LOCKED: todas las filas de X están lockeadas → Y no ve ninguna.
            async with session_factory() as session_y:
                store_y = PostgresLiveOrderStore(session_y)
                rows_y = await store_y.claim_unknown_batch(
                    limit=n, worker_id="worker-y", stale_after_seconds=120
                )
                claimed_y_live = {r.order_id for r in rows_y}
                overlap = claimed_x & claimed_y_live
                assert not overlap, f"doble-claim con leases vivos: {overlap}"
                assert claimed_y_live == set(), (
                    f"Y no debe reclamar nada mientras X retiene el lease: {claimed_y_live}"
                )
                await session_y.rollback()

            # X suelta el lease (rollback del claim: el lock se libera).
            await session_x.rollback()

        # Relevo real: Y vuelve a reclamar ahora que las filas están libres y cubre
        # el lote completo (no se pierden filas con el relevo).
        async with session_factory() as session_y2:
            store_y2 = PostgresLiveOrderStore(session_y2)
            rows_y2 = await store_y2.claim_unknown_batch(
                limit=n, worker_id="worker-y", stale_after_seconds=120
            )
            claimed_y_after = {r.order_id for r in rows_y2}
            await session_y2.rollback()
        assert claimed_y_after == seeded, (
            f"lote no cubierto tras el relevo: missing {seeded - claimed_y_after}, "
            f"extra {claimed_y_after - seeded}"
        )
    finally:
        await _purge_account(session_factory, account_id)
