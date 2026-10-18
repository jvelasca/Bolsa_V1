"""Repositorio SQLAlchemy — cola durable de trabajos operativos AUTO.

Un job pertenece a un ``kind`` (``estudio_daily`` | ``dia_d_replay``), un ``day``
(``YYYY-MM-DD``) y, opcionalmente, una cuenta. El **hueco de idempotencia** es
``(kind, cuenta, día)`` mientras el job está ACTIVO (``queued``/``running``), y lo
garantiza un índice único parcial en la base de datos (migración ``056``): dos
peticiones concurrentes convergen en una sola fila activa.

El ``claim`` es atómico (``SELECT … FOR UPDATE SKIP LOCKED``) y también recupera jobs
``running`` cuyo latido quedó obsoleto (proceso caído), de modo que el trabajo no se
pierde silenciosamente.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import and_, desc, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_domain.entities.auto_ops_job import (
    JOB_ACTIVE_STATUSES,
    JOB_KIND_DIA_D_REPLAY,
    JOB_KIND_ESTUDIO_DAILY,
    JOB_KINDS,
    JOB_STATUS_COMPLETED,
    JOB_STATUS_FAILED,
    JOB_STATUS_QUEUED,
    JOB_STATUS_RUNNING,
    AutoOpsJob,
)
from bolsa_infrastructure.database.models import AutoOpsJobRow
from bolsa_infrastructure.ids import new_id

__all__ = [
    "SqlAlchemyAutoOpsJobRepository",
    "normalize_job_kind",
    "normalize_job_day",
]


def normalize_job_kind(kind: str) -> str:
    """Valida el tipo de job (fail-closed: un tipo desconocido no se encola)."""
    value = str(kind or "").strip()
    if value not in JOB_KINDS:
        raise ValueError(f"kind inválido: {value or '(vacío)'}")
    return value


def normalize_job_day(day: str | None) -> str:
    """Normaliza el día del job a ``YYYY-MM-DD`` (UTC si no se declara)."""
    raw = str(day or "").strip()
    if not raw:
        return datetime.now(UTC).date().isoformat()
    return raw[:10]


def _iso(value: datetime | None) -> str | None:
    return None if value is None else value.isoformat()


class SqlAlchemyAutoOpsJobRepository:
    """Acceso durable a ``auto_ops_jobs``."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ── mapeo ────────────────────────────────────────────────────────────────

    def _map(self, row: AutoOpsJobRow) -> AutoOpsJob:
        return AutoOpsJob(
            id=row.id,
            kind=row.kind,
            status=row.status,
            day=row.day,
            account_id=row.account_id,
            payload=dict(row.payload or {}),
            progress=dict(row.progress or {}),
            result=dict(row.result or {}),
            error=row.error,
            attempt=int(row.attempt or 0),
            created_at=_iso(row.created_at),
            started_at=_iso(row.started_at),
            finished_at=_iso(row.finished_at),
            heartbeat_at=_iso(row.heartbeat_at),
        )

    # ── lectura ──────────────────────────────────────────────────────────────

    async def get(self, job_id: str) -> AutoOpsJob | None:
        stmt = select(AutoOpsJobRow).where(AutoOpsJobRow.id == job_id)
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return None if row is None else self._map(row)

    async def find_active(
        self,
        *,
        kind: str,
        day: str,
        account_id: str | None,
    ) -> AutoOpsJob | None:
        """Job ACTIVO del mismo hueco ``(kind, cuenta, día)``, si existe."""
        stmt = select(AutoOpsJobRow).where(
            AutoOpsJobRow.kind == kind,
            AutoOpsJobRow.day == day,
            AutoOpsJobRow.status.in_(JOB_ACTIVE_STATUSES),
        )
        stmt = self._scope_account(stmt, account_id)
        row = (await self._session.execute(stmt.limit(1))).scalar_one_or_none()
        return None if row is None else self._map(row)

    async def list_for_account(
        self,
        *,
        account_id: str | None,
        kind: str | None = None,
        limit: int = 20,
    ) -> list[AutoOpsJob]:
        stmt = select(AutoOpsJobRow)
        stmt = self._scope_account(stmt, account_id)
        if kind is not None:
            stmt = stmt.where(AutoOpsJobRow.kind == kind)
        stmt = stmt.order_by(desc(AutoOpsJobRow.created_at)).limit(max(1, min(limit, 200)))
        rows = (await self._session.execute(stmt)).scalars().all()
        return [self._map(r) for r in rows]

    async def list_for_day(
        self,
        *,
        kind: str,
        day: str,
        account_id: str | None,
        limit: int = 10,
    ) -> list[AutoOpsJob]:
        """Jobs del mismo ``(kind, cuenta, día)``, más recientes primero (cualquier estado)."""
        stmt = select(AutoOpsJobRow).where(
            AutoOpsJobRow.kind == kind,
            AutoOpsJobRow.day == day,
        )
        stmt = self._scope_account(stmt, account_id)
        stmt = stmt.order_by(desc(AutoOpsJobRow.created_at)).limit(max(1, min(limit, 50)))
        rows = (await self._session.execute(stmt)).scalars().all()
        return [self._map(r) for r in rows]

    # ── escritura ────────────────────────────────────────────────────────────

    async def enqueue(
        self,
        *,
        kind: str,
        day: str,
        account_id: str | None,
        payload: dict[str, Any] | None = None,
    ) -> AutoOpsJob:
        """Encola un job o devuelve el ACTIVO del mismo hueco (idempotente).

        La carrera real la resuelve el índice único parcial: si el ``INSERT`` choca,
        se relee el job activo y se devuelve (nunca se duplica el trabajo).
        """
        job_kind = normalize_job_kind(kind)
        job_day = normalize_job_day(day)
        existing = await self.find_active(
            kind=job_kind, day=job_day, account_id=account_id
        )
        if existing is not None:
            return existing

        now = datetime.now(UTC)
        row = AutoOpsJobRow(
            id=new_id(),
            kind=job_kind,
            status=JOB_STATUS_QUEUED,
            day=job_day,
            account_id=account_id,
            payload=dict(payload or {}),
            progress={},
            result={},
            error=None,
            attempt=0,
            created_at=now,
        )
        try:
            # SAVEPOINT: un choque del índice único no invalida la transacción del llamante.
            async with self._session.begin_nested():
                self._session.add(row)
                await self._session.flush()
        except IntegrityError:
            raced = await self.find_active(
                kind=job_kind, day=job_day, account_id=account_id
            )
            if raced is None:  # pragma: no cover — el conflicto garantiza una fila activa
                raise
            return raced
        return self._map(row)

    async def claim_next(
        self,
        *,
        stale_after_seconds: int = 1800,
        now: datetime | None = None,
    ) -> AutoOpsJob | None:
        """Reclama el siguiente job pendiente (o uno ``running`` con latido obsoleto).

        ``FOR UPDATE SKIP LOCKED`` hace que dos workers no reclamen la misma fila.
        """
        moment = now or datetime.now(UTC)
        stale_before = moment - timedelta(seconds=max(60, int(stale_after_seconds)))
        stmt = (
            select(AutoOpsJobRow)
            .where(
                or_(
                    AutoOpsJobRow.status == JOB_STATUS_QUEUED,
                    and_(
                        AutoOpsJobRow.status == JOB_STATUS_RUNNING,
                        or_(
                            AutoOpsJobRow.heartbeat_at.is_(None),
                            AutoOpsJobRow.heartbeat_at < stale_before,
                        ),
                    ),
                )
            )
            .order_by(AutoOpsJobRow.created_at)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return None
        row.status = JOB_STATUS_RUNNING
        row.attempt = int(row.attempt or 0) + 1
        row.started_at = row.started_at or moment
        row.heartbeat_at = moment
        row.finished_at = None
        row.error = None
        await self._session.flush()
        return self._map(row)

    async def set_progress(
        self,
        job_id: str,
        progress: dict[str, Any],
        *,
        now: datetime | None = None,
    ) -> None:
        """Publica progreso y renueva el latido del job."""
        row = await self._row(job_id)
        if row is None:
            return
        row.progress = dict(progress or {})
        row.heartbeat_at = now or datetime.now(UTC)
        await self._session.flush()

    async def touch(self, job_id: str, *, now: datetime | None = None) -> None:
        """Renueva el latido sin cambiar el progreso."""
        row = await self._row(job_id)
        if row is None:
            return
        row.heartbeat_at = now or datetime.now(UTC)
        await self._session.flush()

    async def complete(
        self,
        job_id: str,
        result: dict[str, Any] | None = None,
        *,
        now: datetime | None = None,
    ) -> None:
        moment = now or datetime.now(UTC)
        row = await self._row(job_id)
        if row is None:
            return
        row.status = JOB_STATUS_COMPLETED
        row.result = dict(result or {})
        row.error = None
        row.finished_at = moment
        row.heartbeat_at = moment
        await self._session.flush()

    async def fail(
        self,
        job_id: str,
        error: str,
        *,
        result: dict[str, Any] | None = None,
        now: datetime | None = None,
    ) -> None:
        moment = now or datetime.now(UTC)
        row = await self._row(job_id)
        if row is None:
            return
        row.status = JOB_STATUS_FAILED
        row.error = str(error)[:2000]
        if result is not None:
            row.result = dict(result)
        row.finished_at = moment
        row.heartbeat_at = moment
        await self._session.flush()

    # ── helpers ──────────────────────────────────────────────────────────────

    async def _row(self, job_id: str) -> AutoOpsJobRow | None:
        stmt = select(AutoOpsJobRow).where(AutoOpsJobRow.id == job_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    @staticmethod
    def _scope_account(stmt: Any, account_id: str | None) -> Any:
        if account_id is None:
            return stmt.where(AutoOpsJobRow.account_id.is_(None))
        return stmt.where(AutoOpsJobRow.account_id == account_id)


def kind_label(kind: str) -> str:
    """Rótulo humano del tipo de job (para mensajes de error y UI)."""
    if kind == JOB_KIND_ESTUDIO_DAILY:
        return "operativa diaria ESTUDIO"
    if kind == JOB_KIND_DIA_D_REPLAY:
        return "replay DÍA-D AUTO"
    return kind
