from datetime import UTC, datetime
from typing import Any

from bolsa_domain.entities.research_tree import MklSyncEvent
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_infrastructure.database.models import MklSyncEventRow
from bolsa_infrastructure.ids import new_id


class SqlAlchemyMklSyncRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _map(self, row: MklSyncEventRow) -> MklSyncEvent:
        notes = row.notes if isinstance(row.notes, list) else []
        return MklSyncEvent(
            id=row.id,
            knowledge_node_id=row.knowledge_node_id,
            status=row.status,
            fact_payload=row.fact_payload if isinstance(row.fact_payload, dict) else {},
            math_version=row.math_version,
            created_at=row.created_at.isoformat(),
            notes=[str(n) for n in notes],
        )

    async def append(
        self,
        *,
        knowledge_node_id: str,
        status: str,
        fact_payload: dict[str, Any],
        math_version: str,
        notes: list[str] | None = None,
        event_id: str | None = None,
    ) -> MklSyncEvent:
        row = MklSyncEventRow(
            id=event_id or new_id(),
            knowledge_node_id=knowledge_node_id,
            status=status,
            fact_payload=fact_payload,
            math_version=math_version,
            notes=list(notes or []),
            created_at=datetime.now(UTC),
        )
        self._session.add(row)
        await self._session.flush()
        return self._map(row)

    async def list_for_knowledge(
        self,
        knowledge_node_id: str,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[MklSyncEvent], int]:
        filters = [MklSyncEventRow.knowledge_node_id == knowledge_node_id]
        count_stmt = select(func.count()).select_from(MklSyncEventRow).where(*filters)
        total = int((await self._session.execute(count_stmt)).scalar_one())
        list_stmt = (
            select(MklSyncEventRow)
            .where(*filters)
            .order_by(desc(MklSyncEventRow.created_at))
            .limit(limit)
            .offset(offset)
        )
        rows = (await self._session.execute(list_stmt)).scalars().all()
        return [self._map(r) for r in rows], total
