from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_infrastructure.database.models import ScanJobRow
from bolsa_infrastructure.ids import new_id

ScanJobStatus = Literal["pending", "processing", "completed", "failed"]

#: DS-1 — contador de resurrecciones de un job ``processing`` huérfano. Viaja DENTRO del
#: ``payload`` JSONB a propósito: el reaper no necesita migración para recordar cuántas veces
#: ya se reintentó el mismo job.
REAP_COUNT_KEY = "_reapCount"


@dataclass(frozen=True, slots=True)
class ScanJobRecord:
    id: str
    status: ScanJobStatus
    payload: dict[str, Any]
    result: dict[str, Any] | None
    error: str | None
    cache_hits: int | None
    cache_misses: int | None
    tracker_definition_id: str | None
    created_at: str
    updated_at: str
    completed_at: str | None


class SqlAlchemyScanJobRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        payload: dict[str, Any],
        *,
        status: ScanJobStatus = "pending",
        tracker_definition_id: str | None = None,
    ) -> ScanJobRecord:
        now = datetime.now(UTC)
        row = ScanJobRow(
            id=new_id(),
            status=status,
            payload=payload,
            result=None,
            error=None,
            cache_hits=None,
            cache_misses=None,
            tracker_definition_id=tracker_definition_id,
            created_at=now,
            updated_at=now,
            completed_at=None,
        )
        self._session.add(row)
        await self._session.flush()
        return self._to_record(row)

    async def update_payload(self, job_id: str, payload: dict[str, Any]) -> ScanJobRecord | None:
        now = datetime.now(UTC)
        stmt = (
            update(ScanJobRow)
            .where(ScanJobRow.id == job_id)
            .values(payload=payload, updated_at=now)
            .returning(ScanJobRow)
        )
        updated = await self._session.execute(stmt)
        row = updated.scalar_one_or_none()
        return self._to_record(row) if row else None

    async def get_by_id(self, job_id: str) -> ScanJobRecord | None:
        stmt = select(ScanJobRow).where(ScanJobRow.id == job_id)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return self._to_record(row)

    async def get_many(self, job_ids: list[str]) -> list[ScanJobRecord]:
        if not job_ids:
            return []
        stmt = select(ScanJobRow).where(ScanJobRow.id.in_(job_ids))
        result = await self._session.execute(stmt)
        by_id = {row.id: self._to_record(row) for row in result.scalars().all()}
        return [by_id[job_id] for job_id in job_ids if job_id in by_id]

    async def list_recent(self, *, limit: int = 20) -> list[ScanJobRecord]:
        stmt = select(ScanJobRow).order_by(ScanJobRow.created_at.desc()).limit(limit)
        result = await self._session.execute(stmt)
        return [self._to_record(row) for row in result.scalars().all()]

    async def list_since(
        self,
        *,
        since: datetime,
        payload_key: str,
        statuses: Sequence[str] | None = None,
        limit: int = 500,
    ) -> list[ScanJobRecord]:
        """Filas (con ``id``) de jobs con el marcador, creados desde ``since``.

        D-3 (auditoría 2) — variante con IDENTIDAD de ``list_payloads_since``: el aviso de
        discovery fallido necesita el ``jobId`` para ser accionable, no solo el payload.
        """
        stmt = (
            select(ScanJobRow)
            .where(
                ScanJobRow.created_at >= since,
                ScanJobRow.payload[payload_key].astext == "true",
            )
            .order_by(ScanJobRow.created_at.desc())
            .limit(limit)
        )
        if statuses is not None:
            stmt = stmt.where(ScanJobRow.status.in_(tuple(statuses)))
        result = await self._session.execute(stmt)
        return [self._to_record(row) for row in result.scalars().all()]

    async def list_payloads_since(
        self,
        *,
        since: datetime,
        payload_key: str,
        statuses: Sequence[str] | None = None,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        """Payloads de jobs con ``payload[payload_key]`` verdadero creados desde ``since``.

        Sirve al dedupe *durable* del scan diario (T-2): un reinicio del proceso no debe
        volver a encolar el mismo universo el mismo día. Filtra en SQL (JSONB) para no
        depender de cuántos scans manuales haya habido.

        ``statuses`` (D-3, auditoría 2) acota el dedupe a los estados que de verdad
        representan trabajo VIVO O HECHO. Sin filtro, un job ``failed`` contaba como "ya
        encolado hoy" y el día entero quedaba sin descubrimiento y sin aviso; el llamante
        pasa la lista de INCLUSIÓN (``pending``/``processing``/``completed``) y consulta
        aparte los fallidos para declararlos. ``None`` conserva el contrato histórico
        (cualquier estado).
        """
        records = await self.list_since(
            since=since,
            payload_key=payload_key,
            statuses=statuses,
            limit=limit,
        )
        return [record.payload for record in records]

    async def claim_next(self) -> ScanJobRecord | None:
        stmt = (
            select(ScanJobRow)
            .where(ScanJobRow.status == "pending")
            .order_by(ScanJobRow.created_at.asc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None

        now = datetime.now(UTC)
        update_stmt = (
            update(ScanJobRow)
            .where(ScanJobRow.id == row.id, ScanJobRow.status == "pending")
            .values(status="processing", updated_at=now)
            .returning(ScanJobRow)
        )
        updated = await self._session.execute(update_stmt)
        claimed = updated.scalar_one_or_none()
        if claimed is None:
            return None
        return self._to_record(claimed)

    async def claim_by_id(self, job_id: str) -> ScanJobRecord | None:
        now = datetime.now(UTC)
        stmt = (
            update(ScanJobRow)
            .where(ScanJobRow.id == job_id, ScanJobRow.status == "pending")
            .values(status="processing", updated_at=now)
            .returning(ScanJobRow)
        )
        updated = await self._session.execute(stmt)
        claimed = updated.scalar_one_or_none()
        if claimed is None:
            return None
        return self._to_record(claimed)

    async def mark_completed(
        self,
        job_id: str,
        *,
        result: dict[str, Any],
        cache_hits: int,
        cache_misses: int,
    ) -> ScanJobRecord | None:
        now = datetime.now(UTC)
        stmt = (
            update(ScanJobRow)
            .where(ScanJobRow.id == job_id, ScanJobRow.status == "processing")
            .values(
                status="completed",
                result=result,
                error=None,
                cache_hits=cache_hits,
                cache_misses=cache_misses,
                updated_at=now,
                completed_at=now,
            )
            .returning(ScanJobRow)
        )
        updated = await self._session.execute(stmt)
        row = updated.scalar_one_or_none()
        return self._to_record(row) if row else None

    async def mark_failed(self, job_id: str, *, error: str) -> ScanJobRecord | None:
        now = datetime.now(UTC)
        stmt = (
            update(ScanJobRow)
            .where(ScanJobRow.id == job_id, ScanJobRow.status == "processing")
            .values(status="failed", error=error, updated_at=now, completed_at=now)
            .returning(ScanJobRow)
        )
        updated = await self._session.execute(stmt)
        row = updated.scalar_one_or_none()
        return self._to_record(row) if row else None

    async def renew_processing_lease(
        self,
        job_id: str,
        *,
        now: datetime | None = None,
    ) -> ScanJobRecord | None:
        """Renueva el LEASE de un job que se está procesando (DS-1, auditoría 2.88.179).

        ``updated_at`` es la referencia temporal del lease: el reaper declara huérfano un
        ``processing`` cuyo ``updated_at`` superó ``SCAN_JOB_PROCESSING_STALE_SECONDS``. Sin
        este latido, un scan legítimo más largo que ese umbral se reencolaba mientras seguía
        vivo (y podía ejecutarse dos veces).

        Devuelve ``None`` si el job ya no está ``processing`` (terminó, falló o el reaper lo
        reencoló): el llamante debe dejar de latir. El ``UPDATE`` repite el estado para no
        reabrir un job cerrado entre la lectura y la escritura.
        """
        moment = now or datetime.now(UTC)
        stmt = (
            update(ScanJobRow)
            .where(ScanJobRow.id == job_id, ScanJobRow.status == "processing")
            .values(updated_at=moment)
            .returning(ScanJobRow)
        )
        updated = await self._session.execute(stmt)
        row = updated.scalar_one_or_none()
        return self._to_record(row) if row else None

    async def reap_stale_processing(
        self,
        *,
        stale_before: datetime,
        requeue: bool,
        max_reaps: int = 3,
        now: datetime | None = None,
        limit: int = 100,
    ) -> list[ScanJobRecord]:
        """Recupera jobs ``processing`` HUÉRFANOS (DS-1, auditoría 2.88.179).

        ``claim_next`` pasa ``pending → processing`` y no hay latido: si el proceso cae tras
        reclamar (SIGKILL, reinicio del ``queue_poll_worker``) la fila se quedaba en
        ``processing`` **para siempre**, y como ese estado cuenta en el dedupe del scan diario,
        contenía el reintento del día y era invisible para ``_failed_discoveries_today``.

        Un job es huérfano cuando su ``updated_at`` (la marca del claim) es anterior a
        ``stale_before``. ``updated_at`` y no ``created_at``: lo que caduca es el LEASE, no la
        antigüedad del trabajo encolado.

        * ``requeue=True`` (autoridad ``queue_poll_worker``): vuelve a ``pending`` para que el
          poller inline lo reclame otra vez. El contador de resurrecciones viaja en el propio
          ``payload`` (``_reapCount``, sin migración); superado ``max_reaps`` se marca
          ``failed`` para no ciclar indefinidamente.
        * ``requeue=False`` (autoridad ``arq_worker``): se marca ``failed``. Devolver la fila
          a ``pending`` no republica el job en Redis y dejaría un ``pending`` que nadie drena.

        Devuelve las filas YA tocadas (el ``commit`` lo hace el llamante). El ``UPDATE`` repite
        ``status == "processing"`` **y** ``updated_at < stale_before``: así un job que renovó su
        lease (``renew_processing_lease``) entre la lectura y la escritura, o que otro
        reconciliador ya reencoló, deja de ser candidato en vez de pisarse. Sin la segunda
        condición la renovación concurrente no impedía el reencolado.
        """
        moment = now or datetime.now(UTC)
        candidates = (
            await self._session.execute(
                select(ScanJobRow)
                .where(
                    ScanJobRow.status == "processing",
                    ScanJobRow.updated_at < stale_before,
                )
                .order_by(ScanJobRow.updated_at.asc())
                .limit(max(1, int(limit)))
            )
        ).scalars().all()

        reaped: list[ScanJobRecord] = []
        for candidate in candidates:
            payload = dict(candidate.payload or {})
            reaps = int(payload.get(REAP_COUNT_KEY) or 0) + 1
            payload[REAP_COUNT_KEY] = reaps
            exhausted = reaps > max(0, int(max_reaps))
            if requeue and not exhausted:
                values: dict[str, Any] = {
                    "status": "pending",
                    "payload": payload,
                    "error": None,
                    "updated_at": moment,
                    "completed_at": None,
                }
            else:
                values = {
                    "status": "failed",
                    "payload": payload,
                    "error": (
                        "processing_stale: reap cap reached"
                        if exhausted
                        else "processing_stale: requeue disabled for this backend"
                    ),
                    "updated_at": moment,
                    "completed_at": moment,
                }
            updated = await self._session.execute(
                update(ScanJobRow)
                .where(
                    ScanJobRow.id == candidate.id,
                    ScanJobRow.status == "processing",
                    ScanJobRow.updated_at < stale_before,
                )
                .values(**values)
                .returning(ScanJobRow)
            )
            row = updated.scalar_one_or_none()
            if row is not None:
                reaped.append(self._to_record(row))
        return reaped

    def _to_record(self, row: ScanJobRow) -> ScanJobRecord:
        return ScanJobRecord(
            id=row.id,
            status=row.status,  # type: ignore[arg-type]
            payload=dict(row.payload),
            result=dict(row.result) if row.result is not None else None,
            error=row.error,
            cache_hits=row.cache_hits,
            cache_misses=row.cache_misses,
            tracker_definition_id=row.tracker_definition_id,
            created_at=row.created_at.isoformat(),
            updated_at=row.updated_at.isoformat(),
            completed_at=row.completed_at.isoformat() if row.completed_at else None,
        )
