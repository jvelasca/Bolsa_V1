"""T-1/T-2 contra PostgreSQL real: lo que el stub no puede probar (SQL + JSONB).

El offline de CI corre sin PostgreSQL, así que estas dos consultas se miden en
``lifecycle-pg`` con ``SCAN_QUEUE_PG_REQUIRED=1`` (un skip es un fallo duro):

* ``inspect_scan_queue`` cuenta ``pending`` y la antigüedad del más viejo.
* ``SqlAlchemyScanJobRepository.list_payloads_since`` filtra el marcador de discovery en
  JSONB, que es el dedupe durable del primer tick inmediato del scan diario.
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
from sqlalchemy import delete

from bolsa_api.background.scan_queue_health import inspect_scan_queue
from bolsa_infrastructure.database.models import ScanJobRow
from bolsa_infrastructure.database.repositories.scan_job_repository import (
    SqlAlchemyScanJobRepository,
)
from tests._estudio_pg_helpers import make_pg_session_factory, require_or_skip

if sys.platform == "win32":  # psycopg async no soporta ProactorEventLoop.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

#: Gate propio (fail-if-skipped) del job ``lifecycle-pg``.
_REQUIRED_ENV = "SCAN_QUEUE_PG_REQUIRED"

_DISCOVERY_KEY = "opportunityDiscovery"


@pytest_asyncio.fixture
async def pg_factory() -> AsyncIterator[Any]:
    try:
        factory, engine = await make_pg_session_factory()
    except Exception as exc:  # noqa: BLE001 — skip/fail gate honesto por env.
        require_or_skip(exc, required_env=_REQUIRED_ENV, what="salud de la cola de scan")
        return
    try:
        yield factory
    finally:
        await engine.dispose()


def _payload(*, discovery: bool, list_id: str = "estudio") -> dict[str, Any]:
    payload: dict[str, Any] = {
        "universe": {"listId": list_id},
        "timeframe": "1d",
        "presetKey": "opportunity_daily",
    }
    if discovery:
        payload[_DISCOVERY_KEY] = True
        payload["opportunityProposeCap"] = 3
    return payload


async def _insert(
    factory: Any,
    *,
    status: str,
    created_at: datetime,
    payload: dict[str, Any],
    updated_at: datetime | None = None,
) -> str:
    job_id = f"test-scanq-{uuid.uuid4().hex[:12]}"
    async with factory() as session:
        session.add(
            ScanJobRow(
                id=job_id,
                status=status,
                payload=payload,
                result=None,
                error=None,
                cache_hits=None,
                cache_misses=None,
                tracker_definition_id=None,
                created_at=created_at,
                updated_at=updated_at or created_at,
                completed_at=None,
            )
        )
        await session.commit()
    return job_id


async def _delete(factory: Any, *job_ids: str) -> None:
    async with factory() as session:
        await session.execute(delete(ScanJobRow).where(ScanJobRow.id.in_(job_ids)))
        await session.commit()


@pytest.mark.asyncio
async def test_pending_scan_older_than_stale_after_is_stalled(pg_factory: Any) -> None:
    """T-1: un ``pending`` de hace una hora es atasco, y el motivo es el declarado."""
    now = datetime.now(UTC)
    old = await _insert(
        pg_factory, status="pending", created_at=now - timedelta(minutes=60), payload=_payload(discovery=False)
    )
    fresh = await _insert(
        pg_factory, status="completed", created_at=now, payload=_payload(discovery=False)
    )
    try:
        async with pg_factory() as session:
            health = await inspect_scan_queue(session, backend="inline", now=now)
        assert health.pending >= 1
        assert health.oldest_pending_seconds is not None
        assert health.oldest_pending_seconds >= 3600
        assert health.stalled is True
        assert health.reason == "scan_queue_stalled"
        assert health.authority == "queue_poll_worker"
    finally:
        await _delete(pg_factory, old, fresh)


@pytest.mark.asyncio
async def test_completed_jobs_do_not_count_as_pending(pg_factory: Any) -> None:
    """T-1: ``pending`` cuenta estado, no antigüedad: un job cerrado no es atasco."""
    now = datetime.now(UTC)
    old_done = await _insert(
        pg_factory, status="completed", created_at=now - timedelta(hours=3), payload=_payload(discovery=False)
    )
    try:
        async with pg_factory() as session:
            health = await inspect_scan_queue(
                session, backend="arq", now=now, stale_after_seconds=60.0
            )
        assert health.authority == "arq_worker"
        # El job cerrado no aparece; si hay otros pending, su antigüedad manda.
        assert health.oldest_pending_seconds is None or health.oldest_pending_seconds < 10800
    finally:
        await _delete(pg_factory, old_done)


@pytest.mark.asyncio
async def test_list_payloads_since_filters_the_discovery_marker(pg_factory: Any) -> None:
    """T-2: el dedupe durable sólo ve jobs de discovery creados desde el corte."""
    now = datetime.now(UTC)
    discovery_id = await _insert(
        pg_factory, status="pending", created_at=now, payload=_payload(discovery=True)
    )
    manual_id = await _insert(
        pg_factory, status="pending", created_at=now, payload=_payload(discovery=False)
    )
    yesterday_id = await _insert(
        pg_factory,
        status="completed",
        created_at=now - timedelta(days=2),
        payload=_payload(discovery=True),
    )
    try:
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        async with pg_factory() as session:
            payloads = await SqlAlchemyScanJobRepository(session).list_payloads_since(
                since=day_start, payload_key=_DISCOVERY_KEY
            )
        ids = {payload.get("universe", {}).get("listId") for payload in payloads}
        assert ids == {"estudio"}
        assert all(payload.get(_DISCOVERY_KEY) for payload in payloads)
        # El manual de hoy no entra por el marcador; el de ayer no entra por el corte.
        assert len(payloads) >= 1
        assert discovery_id
        assert manual_id
        assert yesterday_id
    finally:
        await _delete(pg_factory, discovery_id, manual_id, yesterday_id)


@pytest.mark.asyncio
async def test_list_payloads_since_filters_by_status_for_the_daily_dedupe(
    pg_factory: Any,
) -> None:
    """D-3 — un discovery ``failed`` de hoy NO cuenta como «ya encolado hoy».

    Sin el filtro de estado, el job fallido bloqueaba el reintento del día entero. La
    consulta con la lista de INCLUSIÓN lo deja fuera y la consulta de fallidos lo declara.
    """
    now = datetime.now(UTC)
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    live_id = await _insert(
        pg_factory,
        status="pending",
        created_at=now,
        payload=_payload(discovery=True, list_id="estudio"),
    )
    failed_id = await _insert(
        pg_factory,
        status="failed",
        created_at=now,
        payload=_payload(discovery=True, list_id="otro"),
    )
    try:
        async with pg_factory() as session:
            repo = SqlAlchemyScanJobRepository(session)
            live = await repo.list_payloads_since(
                since=day_start,
                payload_key=_DISCOVERY_KEY,
                statuses=("pending", "processing", "completed"),
            )
            failed = await repo.list_payloads_since(
                since=day_start,
                payload_key=_DISCOVERY_KEY,
                statuses=("failed",),
            )
            failed_records = await repo.list_since(
                since=day_start,
                payload_key=_DISCOVERY_KEY,
                statuses=("failed",),
            )
            every = await repo.list_payloads_since(
                since=day_start, payload_key=_DISCOVERY_KEY
            )
        assert {payload["universe"]["listId"] for payload in live} == {"estudio"}
        assert {payload["universe"]["listId"] for payload in failed} == {"otro"}
        # La variante con IDENTIDAD es la que permite declarar el ``jobId`` del fallo.
        assert [record.id for record in failed_records] == [failed_id]
        # ``None`` conserva el contrato histórico (cualquier estado).
        assert {payload["universe"]["listId"] for payload in every} == {"estudio", "otro"}
    finally:
        await _delete(pg_factory, live_id, failed_id)


# ── DS-1 (auditoría 2.88.179): el ``processing`` huérfano se mide y se recupera ──


@pytest.mark.asyncio
async def test_stale_processing_is_measured_by_its_lease(pg_factory: Any) -> None:
    """DS-1: ``processing`` se mide por ``updated_at`` (el lease), no por ``created_at``."""
    now = datetime.now(UTC)
    stale = await _insert(
        pg_factory,
        status="processing",
        created_at=now - timedelta(hours=3),
        updated_at=now - timedelta(hours=2),
        payload=_payload(discovery=True),
    )
    fresh = await _insert(
        pg_factory,
        status="processing",
        created_at=now - timedelta(hours=3),
        updated_at=now - timedelta(seconds=30),
        payload=_payload(discovery=True),
    )
    try:
        async with pg_factory() as session:
            health = await inspect_scan_queue(
                session,
                backend="inline",
                now=now,
                stale_processing_after_seconds=3600.0,
            )
        assert health.processing == 2
        assert health.stale_processing == 1
        assert health.stalled is True
        assert health.reason == "scan_queue_processing_stale"
        assert health.oldest_processing_seconds is not None
        assert health.oldest_processing_seconds >= 7200
    finally:
        await _delete(pg_factory, stale, fresh)


@pytest.mark.asyncio
async def test_reaper_requeues_a_stale_processing_job(pg_factory: Any) -> None:
    """DS-1: con autoridad inline el huérfano vuelve a ``pending`` y se cuenta el intento."""
    now = datetime.now(UTC)
    job_id = await _insert(
        pg_factory,
        status="processing",
        created_at=now - timedelta(hours=3),
        updated_at=now - timedelta(hours=2),
        payload=_payload(discovery=True),
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
        assert reaped[0].status == "pending"
        assert reaped[0].payload["_reapCount"] == 1
        assert reaped[0].error is None

        async with pg_factory() as session:
            again = await SqlAlchemyScanJobRepository(session).get_by_id(job_id)
        assert again is not None
        assert again.status == "pending"
    finally:
        await _delete(pg_factory, job_id)


@pytest.mark.asyncio
async def test_reaper_leaves_a_fresh_processing_job_untouched(pg_factory: Any) -> None:
    """DS-1: un scan en curso NO se toca (solo caduca el lease vencido)."""
    now = datetime.now(UTC)
    job_id = await _insert(
        pg_factory,
        status="processing",
        created_at=now - timedelta(hours=3),
        updated_at=now - timedelta(seconds=30),
        payload=_payload(discovery=True),
    )
    try:
        async with pg_factory() as session:
            reaped = await SqlAlchemyScanJobRepository(session).reap_stale_processing(
                stale_before=now - timedelta(hours=1),
                requeue=True,
                now=now,
            )
            await session.commit()
        assert reaped == []

        async with pg_factory() as session:
            still = await SqlAlchemyScanJobRepository(session).get_by_id(job_id)
        assert still is not None
        assert still.status == "processing"
    finally:
        await _delete(pg_factory, job_id)


@pytest.mark.asyncio
async def test_reaper_declares_failed_when_the_arq_authority_cannot_replay_it(
    pg_factory: Any,
) -> None:
    """DS-1: con ``arq`` no se devuelve a ``pending`` (Redis no republica): se declara failed."""
    now = datetime.now(UTC)
    job_id = await _insert(
        pg_factory,
        status="processing",
        created_at=now - timedelta(hours=3),
        updated_at=now - timedelta(hours=2),
        payload=_payload(discovery=True),
    )
    try:
        async with pg_factory() as session:
            reaped = await SqlAlchemyScanJobRepository(session).reap_stale_processing(
                stale_before=now - timedelta(hours=1),
                requeue=False,
                now=now,
            )
            await session.commit()

        assert [job.id for job in reaped] == [job_id]
        assert reaped[0].status == "failed"
        assert reaped[0].error is not None
        assert "processing_stale" in reaped[0].error
        assert reaped[0].completed_at is not None
    finally:
        await _delete(pg_factory, job_id)


@pytest.mark.asyncio
async def test_reaper_stops_cycling_after_the_reap_cap(pg_factory: Any) -> None:
    """DS-1: un job veneno (cae siempre al reclamar) se declara failed tras el tope."""
    now = datetime.now(UTC)
    job_id = await _insert(
        pg_factory,
        status="processing",
        created_at=now - timedelta(hours=3),
        updated_at=now - timedelta(hours=2),
        payload={**_payload(discovery=True), "_reapCount": 3},
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
        assert reaped[0].payload["_reapCount"] == 4
        assert reaped[0].error == "processing_stale: reap cap reached"
    finally:
        await _delete(pg_factory, job_id)
