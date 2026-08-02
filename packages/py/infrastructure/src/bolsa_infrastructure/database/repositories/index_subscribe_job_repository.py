"""Jobs de suscripción de índices (L2 job+poll)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_infrastructure.database.models import IndexSubscribeJobRow
from bolsa_infrastructure.ids import new_id


@dataclass(frozen=True, slots=True)

class IndexSubscribeJobRecord:

    id: str

    status: str

    payload: dict[str, Any]

    result: dict[str, Any] | None

    error: str | None

    created_at: str

    updated_at: str

    completed_at: str | None

class SqlAlchemyIndexSubscribeJobRepository:

    def __init__(self, session: AsyncSession) -> None:

        self._session = session

    def _to_record(self, row: IndexSubscribeJobRow) -> IndexSubscribeJobRecord:

        return IndexSubscribeJobRecord(

            id=row.id,

            status=row.status,

            payload=dict(row.payload or {}),

            result=dict(row.result) if row.result else None,

            error=row.error,

            created_at=row.created_at.isoformat(),

            updated_at=row.updated_at.isoformat(),

            completed_at=row.completed_at.isoformat() if row.completed_at else None,

        )

    async def create(self, *, payload: dict[str, Any]) -> IndexSubscribeJobRecord:

        now = datetime.now(UTC)

        row = IndexSubscribeJobRow(

            id=new_id(),

            status="pending",

            payload=payload,

            result={

                "phase": "queued",

                "checked": 0,

                "total": 0,

                "alreadyPresent": 0,

                "imported": 0,

                "failed": [],

            },

            error=None,

            created_at=now,

            updated_at=now,

            completed_at=None,

        )

        self._session.add(row)

        await self._session.flush()

        return self._to_record(row)

    async def get(self, job_id: str) -> IndexSubscribeJobRecord | None:

        row = await self._session.get(IndexSubscribeJobRow, job_id)

        return self._to_record(row) if row else None

    async def claim_next(self) -> IndexSubscribeJobRecord | None:

        stmt = (

            select(IndexSubscribeJobRow)

            .where(IndexSubscribeJobRow.status == "pending")

            .order_by(IndexSubscribeJobRow.created_at.asc())

            .limit(1)

            .with_for_update(skip_locked=True)

        )

        result = await self._session.execute(stmt)

        row = result.scalar_one_or_none()

        if row is None:

            return None

        return await self._mark_processing(row)

    async def claim_by_id(self, job_id: str) -> IndexSubscribeJobRecord | None:

        stmt = (

            select(IndexSubscribeJobRow)

            .where(

                IndexSubscribeJobRow.id == job_id,

                IndexSubscribeJobRow.status.in_(("pending", "processing")),

            )

            .with_for_update(skip_locked=True)

        )

        result = await self._session.execute(stmt)

        row = result.scalar_one_or_none()

        if row is None:

            return None

        if row.status == "pending":

            return await self._mark_processing(row)

        return self._to_record(row)

    async def _mark_processing(self, row: IndexSubscribeJobRow) -> IndexSubscribeJobRecord:

        now = datetime.now(UTC)

        row.status = "processing"

        row.updated_at = now

        result_payload = dict(row.result or {})

        result_payload["phase"] = "processing"

        row.result = result_payload

        await self._session.flush()

        return self._to_record(row)

    async def update_progress(self, job_id: str, progress: dict[str, Any]) -> None:

        row = await self._session.get(IndexSubscribeJobRow, job_id)

        if row is None:

            return

        row.result = {**(row.result or {}), **progress, "phase": "processing"}

        row.updated_at = datetime.now(UTC)

        await self._session.flush()

    async def mark_completed(self, job_id: str, result: dict[str, Any]) -> IndexSubscribeJobRecord | None:

        row = await self._session.get(IndexSubscribeJobRow, job_id)

        if row is None:

            return None

        now = datetime.now(UTC)

        row.status = "completed"

        row.result = {**result, "phase": "done"}

        row.error = None

        row.updated_at = now

        row.completed_at = now

        await self._session.flush()

        return self._to_record(row)

    async def mark_failed(self, job_id: str, error: str) -> IndexSubscribeJobRecord | None:

        row = await self._session.get(IndexSubscribeJobRow, job_id)

        if row is None:

            return None

        now = datetime.now(UTC)

        row.status = "failed"

        row.error = error

        row.result = {**(row.result or {}), "phase": "failed"}

        row.updated_at = now

        row.completed_at = now

        await self._session.flush()

        return self._to_record(row)