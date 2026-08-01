from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_infrastructure.database.models import ScanJobRow
from bolsa_infrastructure.ids import new_id

ScanJobStatus = Literal["pending", "processing", "completed", "failed"]


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
