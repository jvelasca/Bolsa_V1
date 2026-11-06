"""DS-1 contra PostgreSQL real: concurrencia, lease y autoridad de reencolado.

El dictamen de la auditoría 2.88.179 exige certificar DS-1 en integración, no solo offline.
Lo que un stub NO puede probar y aquí sí se mide:

* **Concurrencia** (condición 2): dos reconciliadores simultáneos sobre el mismo ``processing``
  obsoleto reencolan EXACTAMENTE una vez.
* **Carrera con el latido** (condición 3): un job que renueva su lease mientras el reaper
  trabaja NO se declara huérfano. El ``UPDATE`` del reaper revalida ``updated_at``, así que
  una renovación entre su ``SELECT`` y su ``UPDATE`` anula el reencolado.
* **Autoridad de reencolado** (condición 4): el job reencolado conserva identidad y datos, y
  el tope de reaps queda ``failed`` de forma persistente sin bloquear el dedupe diario.

Gate ``SCAN_QUEUE_PG_REQUIRED=1`` (fail-if-skipped) en ``lifecycle-pg``.
"""

from __future__ import annotations

import asyncio
import sys
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy import delete, select, text, update

from bolsa_api.background.scan_queue_health import reconcile_scan_queue
from bolsa_infrastructure.database.models import ScanJobRow
from bolsa_infrastructure.database.repositories.scan_job_repository import (
    REAP_COUNT_KEY,
    SqlAlchemyScanJobRepository,
)
from tests._estudio_pg_helpers import make_pg_session_factory, require_or_skip

if sys.platform == "win32":  # psycopg async no soporta ProactorEventLoop.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

#: Gate propio (fail-if-skipped) del job ``lifecycle-pg``.
_REQUIRED_ENV = "SCAN_QUEUE_PG_REQUIRED"

_DISCOVERY_KEY = "opportunityDiscovery"

#: Espera máxima a que el reaper quede BLOQUEADO en el lock de la fila.
_LOCK_WAIT_TIMEOUT_SECONDS = 10.0

#: Cota de sondeo del estado del lock (evita sleeps largos en el camino feliz).
_LOCK_POLL_SECONDS = 0.05


@pytest_asyncio.fixture
async def pg_factory() -> AsyncIterator[Any]:
    try:
        factory, engine = await make_pg_session_factory()
    except Exception as exc:  # noqa: BLE001 — skip/fail gate honesto por env.
        require_or_skip(exc, required_env=_REQUIRED_ENV, what="lease de la cola de scan")
        return
    try:
        yield factory
    finally:
        await engine.dispose()


def _payload(*, list_id: str = "estudio") -> dict[str, Any]:
    """Payload de discovery con la identidad que el reencolado debe conservar."""
    return {
        "universe": {"listId": list_id, "instrumentIds": ["AAA", "BBB"]},
        "timeframe": "1d",
        "presetKey": "opportunity_daily",
        _DISCOVERY_KEY: True,
        "opportunityProposeCap": 3,
    }


async def _insert(
    factory: Any,
    *,
    status: str = "processing",
    age_seconds: float = 7200.0,
    payload: dict[str, Any] | None = None,
) -> str:
    job_id = f"test-scanq-lease-{uuid.uuid4().hex[:12]}"
    now = datetime.now(UTC)
    async with factory() as session:
        session.add(
            ScanJobRow(
                id=job_id,
                status=status,
                payload=payload if payload is not None else _payload(),
                result=None,
                error=None,
                cache_hits=None,
                cache_misses=None,
                tracker_definition_id=None,
                created_at=now - timedelta(seconds=age_seconds + 3600.0),
                updated_at=now - timedelta(seconds=age_seconds),
                completed_at=None,
            )
        )
        await session.commit()
    return job_id


async def _delete(factory: Any, *job_ids: str) -> None:
    async with factory() as session:
        await session.execute(delete(ScanJobRow).where(ScanJobRow.id.in_(job_ids)))
        await session.commit()


async def _read(factory: Any, job_id: str) -> ScanJobRow | None:
    async with factory() as session:
        return await session.get(ScanJobRow, job_id)


async def _wait_for_row_lock_waiters(
    factory: Any,
    job_id: str,
    *,
    minimum: int = 1,
) -> bool:
    """Espera a que al menos ``minimum`` backends queden esperando el lock de la fila.

    Se consulta ``pg_stat_activity`` en vez de dormir un tiempo fijo: el test es determinista
    (espera el estado real) y rápido (sale en el primer tick que lo cumple). ``wait_event_type
    = 'Lock'`` con un ``pid`` ajeno confirma que el reaper está BLOQUEADO en la fila, no que
    haya fallado; ``job_id`` se usa solo para el mensaje de diagnóstico.
    """
    deadline = asyncio.get_running_loop().time() + _LOCK_WAIT_TIMEOUT_SECONDS
    stmt = text(
        """
        SELECT count(*)
          FROM pg_stat_activity
         WHERE datname = current_database()
           AND pid <> pg_backend_pid()
           AND wait_event_type = 'Lock'
        """
    )
    while asyncio.get_running_loop().time() < deadline:
        async with factory() as session:
            waiting = (await session.execute(stmt)).scalar_one()
        if waiting >= minimum:
            return True
        await asyncio.sleep(_LOCK_POLL_SECONDS)
    return False


# ── Condición 2: reconciliación concurrente ─────────────────────────────────────


@pytest.mark.asyncio
async def test_two_reconcilers_requeue_the_same_job_exactly_once(pg_factory: Any) -> None:
    """DS-1 — concurrencia: dos reconciliadores simultáneos no duplican el reencolado."""
    job_id = await _insert(pg_factory, age_seconds=7200.0)
    try:
        first, second = await asyncio.gather(
            reconcile_scan_queue(pg_factory, requeue=True, max_reaps=3),
            reconcile_scan_queue(pg_factory, requeue=True, max_reaps=3),
        )
        # Ambos ciclos se completaron (ninguno falló) y el estado durable es el de UN solo
        # intento. No se afirman contadores globales de salud: la BD de desarrollo es
        # compartida y puede tener otros jobs ajenos al test.
        assert first is not None and second is not None

        row = await _read(pg_factory, job_id)
        assert row is not None
        assert row.status == "pending"
        # Exactamente UN intento: el segundo UPDATE revalidó updated_at y no tocó la fila.
        assert row.payload[REAP_COUNT_KEY] == 1
    finally:
        await _delete(pg_factory, job_id)


@pytest.mark.asyncio
async def test_reconcilers_on_two_sessions_do_not_double_requeue(pg_factory: Any) -> None:
    """DS-1 — concurrencia real por sesiones: el segundo reconciler ve 0 filas tocadas."""
    job_id = await _insert(pg_factory, age_seconds=7200.0)
    stale_before = datetime.now(UTC) - timedelta(hours=1)
    try:
        async def reap() -> list[str]:
            async with pg_factory() as session:
                reaped = await SqlAlchemyScanJobRepository(session).reap_stale_processing(
                    stale_before=stale_before,
                    requeue=True,
                    max_reaps=3,
                )
                await session.commit()
            return [job.id for job in reaped]

        results = await asyncio.gather(reap(), reap())
        touched = [ids for ids in results if ids]
        assert touched == [[job_id]], "solo un reconciler debe tocar la fila"

        row = await _read(pg_factory, job_id)
        assert row is not None
        assert row.payload[REAP_COUNT_KEY] == 1
    finally:
        await _delete(pg_factory, job_id)


# ── Condición 3: carrera entre la renovación del lease y el reaper ──────────────


@pytest.mark.asyncio
async def test_renewal_between_select_and_update_cancels_the_reap(pg_factory: Any) -> None:
    """DS-1 — carrera: renovar el lease con el reaper ya bloqueado impide el reencolado.

    Secuencia forzada (determinista):

    1. La sesión A bloquea la fila con ``SELECT ... FOR UPDATE``: el reaper puede LEERLA
       (su ``SELECT`` no bloquea) pero su ``UPDATE`` queda esperando el lock.
    2. Se comprueba en ``pg_locks`` que el reaper está realmente esperando.
    3. La sesión A renueva el lease y hace ``commit``, liberando el lock.
    4. El reaper reanuda: su ``UPDATE`` revalida ``updated_at < stale_before`` y afecta 0
       filas. El job sigue ``processing``.

    Sin la condición de ``updated_at`` en el ``UPDATE``, este test falla: el job se
    reencolaba mientras el worker seguía vivo (doble ejecución).
    """
    job_id = await _insert(pg_factory, age_seconds=7200.0)
    stale_before = datetime.now(UTC) - timedelta(hours=1)
    try:
        async with pg_factory() as blocker:
            await blocker.execute(
                select(ScanJobRow.id).where(ScanJobRow.id == job_id).with_for_update()
            )

            async def reap() -> list[str]:
                async with pg_factory() as session:
                    reaped = await SqlAlchemyScanJobRepository(session).reap_stale_processing(
                        stale_before=stale_before,
                        requeue=True,
                        max_reaps=3,
                    )
                    await session.commit()
                return [job.id for job in reaped]

            reaper_task = asyncio.create_task(reap())
            try:
                blocked = await _wait_for_row_lock_waiters(pg_factory, job_id)
                assert blocked, (
                    "el reaper no quedó bloqueado en la fila: el test no está ejercitando "
                    "la carrera real"
                )
                # El worker sigue vivo y renueva su lease ANTES de que el reaper escriba.
                renewed = await SqlAlchemyScanJobRepository(blocker).renew_processing_lease(
                    job_id
                )
                assert renewed is not None
                assert renewed.status == "processing"
                await blocker.commit()

                reaped = await asyncio.wait_for(reaper_task, timeout=30.0)
            finally:
                if not reaper_task.done():
                    reaper_task.cancel()
                    await asyncio.gather(reaper_task, return_exceptions=True)

        assert reaped == [], "un lease renovado NO debe reencolarse"
        row = await _read(pg_factory, job_id)
        assert row is not None
        assert row.status == "processing"
        assert REAP_COUNT_KEY not in (row.payload or {})
    finally:
        await _delete(pg_factory, job_id)


@pytest.mark.asyncio
async def test_heartbeat_keeps_a_long_job_alive_across_reconcile_cycles(
    pg_factory: Any,
) -> None:
    """DS-1 — un job que late deja de ser huérfano en CADA ciclo del reaper."""
    job_id = await _insert(pg_factory, age_seconds=7200.0)
    try:
        for _ in range(3):
            async with pg_factory() as session:
                renewed = await SqlAlchemyScanJobRepository(
                    session
                ).renew_processing_lease(job_id)
                await session.commit()
            assert renewed is not None

            health = await reconcile_scan_queue(pg_factory, requeue=True, max_reaps=3)
            assert health is not None

            row = await _read(pg_factory, job_id)
            assert row is not None, "el reaper no debe tocar un job con lease renovado"
            assert row.status == "processing"
            assert REAP_COUNT_KEY not in (row.payload or {})
    finally:
        await _delete(pg_factory, job_id)


@pytest.mark.asyncio
async def test_renewal_of_a_job_that_is_no_longer_processing_returns_none(
    pg_factory: Any,
) -> None:
    """DS-1 — el latido no reabre ni refresca un job ya cerrado o reencolado."""
    job_id = await _insert(pg_factory, status="pending", age_seconds=10.0)
    try:
        async with pg_factory() as session:
            renewed = await SqlAlchemyScanJobRepository(session).renew_processing_lease(
                job_id
            )
            await session.commit()
        assert renewed is None

        row = await _read(pg_factory, job_id)
        assert row is not None
        assert row.status == "pending"
    finally:
        await _delete(pg_factory, job_id)


# ── Condición 4: autoridad de reencolado y tope persistente ────────────────────


@pytest.mark.asyncio
async def test_requeued_job_preserves_identity_and_is_claimable_again(pg_factory: Any) -> None:
    """DS-1 — el reencolado conserva id y datos, se puede reclamar y no duplica filas."""
    original = _payload(list_id="estudio")
    job_id = await _insert(pg_factory, payload=original, age_seconds=7200.0)
    try:
        async with pg_factory() as session:
            reaped = await SqlAlchemyScanJobRepository(session).reap_stale_processing(
                stale_before=datetime.now(UTC) - timedelta(hours=1),
                requeue=True,
                max_reaps=3,
            )
            await session.commit()

        assert [job.id for job in reaped] == [job_id]
        reaped_job = reaped[0]
        # Identidad y datos del trabajo original intactos; solo se añade el contador.
        assert reaped_job.id == job_id
        for key, value in original.items():
            assert reaped_job.payload[key] == value
        assert reaped_job.payload[REAP_COUNT_KEY] == 1
        assert reaped_job.error is None

        # No hay duplicado: una sola fila con ese payload de identidad.
        async with pg_factory() as session:
            rows = (
                await session.execute(
                    select(ScanJobRow).where(
                        ScanJobRow.payload["universe"]["listId"].astext == "estudio",
                        ScanJobRow.id.like("test-scanq-lease-%"),
                    )
                )
            ).scalars().all()
        assert [row.id for row in rows] == [job_id]

        # El poller lo reclama otra vez y puede terminarlo: trazabilidad completa.
        async with pg_factory() as session:
            repo = SqlAlchemyScanJobRepository(session)
            claimed = await repo.claim_by_id(job_id)
            assert claimed is not None
            assert claimed.status == "processing"
            assert claimed.payload[REAP_COUNT_KEY] == 1
            completed = await repo.mark_completed(
                job_id, result={"ok": True}, cache_hits=0, cache_misses=0
            )
            await session.commit()
        assert completed is not None
        assert completed.status == "completed"
    finally:
        await _delete(pg_factory, job_id)


@pytest.mark.asyncio
async def test_reap_cap_is_persistent_and_unblocks_the_daily_dedupe(pg_factory: Any) -> None:
    """DS-1 — tras el tope queda ``failed`` para siempre y deja de bloquear el día."""
    now = datetime.now(UTC)
    job_id = await _insert(
        pg_factory,
        payload={**_payload(), REAP_COUNT_KEY: 3},
        age_seconds=7200.0,
    )
    try:
        async with pg_factory() as session:
            reaped = await SqlAlchemyScanJobRepository(session).reap_stale_processing(
                stale_before=now - timedelta(hours=1),
                requeue=True,
                max_reaps=3,
                now=now,
            )
            await session.commit()

        assert [job.id for job in reaped] == [job_id]
        assert reaped[0].status == "failed"
        assert reaped[0].error == "processing_stale: reap cap reached"
        assert reaped[0].payload[REAP_COUNT_KEY] == 4

        # Persistente: otro ciclo de reconciliación ya no lo ve como candidato.
        async with pg_factory() as session:
            again = await SqlAlchemyScanJobRepository(session).reap_stale_processing(
                stale_before=now,
                requeue=True,
                max_reaps=3,
            )
            await session.commit()
        assert again == []

        # Y el dedupe diario con estados VIVOS ya no lo cuenta: el día no queda bloqueado.
        async with pg_factory() as session:
            repo = SqlAlchemyScanJobRepository(session)
            live_records = await repo.list_since(
                since=now - timedelta(hours=4),
                payload_key=_DISCOVERY_KEY,
                statuses=("pending", "processing", "completed"),
            )
            failed_records = await repo.list_since(
                since=now - timedelta(hours=4),
                payload_key=_DISCOVERY_KEY,
                statuses=("failed",),
            )
        assert job_id not in {record.id for record in live_records}
        assert job_id in {record.id for record in failed_records}
    finally:
        await _delete(pg_factory, job_id)


@pytest.mark.asyncio
async def test_reap_is_bounded_and_skips_rows_outside_the_lease(pg_factory: Any) -> None:
    """DS-1 — el reaper no escanea la tabla entera ni toca jobs con lease vivo."""
    stale_ids = [await _insert(pg_factory, age_seconds=7200.0) for _ in range(3)]
    fresh_id = await _insert(pg_factory, age_seconds=5.0)
    try:
        async with pg_factory() as session:
            reaped = await SqlAlchemyScanJobRepository(session).reap_stale_processing(
                stale_before=datetime.now(UTC) - timedelta(hours=1),
                requeue=True,
                max_reaps=3,
                limit=2,
            )
            await session.commit()
        assert len(reaped) == 2
        assert fresh_id not in {job.id for job in reaped}

        row = await _read(pg_factory, fresh_id)
        assert row is not None and row.status == "processing"
    finally:
        await _delete(pg_factory, *stale_ids, fresh_id)


@pytest.mark.asyncio
async def test_update_of_the_reaper_never_reopens_a_finished_job(pg_factory: Any) -> None:
    """DS-1 — un job terminado por otro proceso entre lectura y escritura no se reabre."""
    job_id = await _insert(pg_factory, age_seconds=7200.0)
    try:
        async with pg_factory() as session:
            # Simula al worker terminando el job DESPUÉS de que el reaper lo leyera.
            await session.execute(
                update(ScanJobRow)
                .where(ScanJobRow.id == job_id)
                .values(status="completed", updated_at=datetime.now(UTC))
            )
            await session.commit()

            reaped = await SqlAlchemyScanJobRepository(session).reap_stale_processing(
                stale_before=datetime.now(UTC) - timedelta(hours=1),
                requeue=True,
                max_reaps=3,
            )
            await session.commit()
        assert reaped == []

        row = await _read(pg_factory, job_id)
        assert row is not None
        assert row.status == "completed"
    finally:
        await _delete(pg_factory, job_id)
