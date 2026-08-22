from datetime import UTC, datetime
from typing import Any

from bolsa_domain.entities.platform_event import PlatformEventRecord
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_infrastructure.database.models import PlatformEventRow
from bolsa_infrastructure.ids import new_id


def _owner_visibility_clause(owner_user_id: str) -> Any:
    """F7c: filtra solo ``user_id == owner`` (legacy NULL excluido)."""
    return PlatformEventRow.user_id == owner_user_id


class SqlAlchemyPlatformEventRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _map(self, row: PlatformEventRow) -> PlatformEventRecord:
        return PlatformEventRecord(
            id=row.id,
            type=row.type,
            payload=dict(row.payload),
            correlation_id=row.correlation_id,
            user_id=row.user_id,
            created_at=row.created_at.isoformat(),
        )

    async def append(
        self,
        *,
        event_type: str,
        payload: dict[str, Any],
        correlation_id: str | None = None,
        user_id: str | None = None,
    ) -> PlatformEventRecord:
        now = datetime.now(UTC)
        row = PlatformEventRow(
            id=new_id(),
            type=event_type,
            payload=payload,
            correlation_id=correlation_id,
            user_id=user_id,
            created_at=now,
        )
        self._session.add(row)
        await self._session.flush()
        return self._map(row)

    async def list_events(
        self,
        *,
        limit: int = 50,
        event_type: str | None = None,
        correlation_id: str | None = None,
        owner_user_id: str | None = None,
    ) -> list[PlatformEventRecord]:
        stmt = select(PlatformEventRow).order_by(PlatformEventRow.created_at.desc()).limit(limit)
        if owner_user_id is not None:
            stmt = stmt.where(_owner_visibility_clause(owner_user_id))
        if event_type:
            stmt = stmt.where(PlatformEventRow.type == event_type)
        if correlation_id:
            stmt = stmt.where(PlatformEventRow.correlation_id == correlation_id)
        result = await self._session.execute(stmt)
        return [self._map(row) for row in result.scalars().all()]
