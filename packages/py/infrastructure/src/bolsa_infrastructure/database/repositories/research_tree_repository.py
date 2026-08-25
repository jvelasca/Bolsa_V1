from datetime import UTC, datetime
from typing import Any

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.expression import ColumnElement

from bolsa_domain.entities.research_tree import ResearchTreeEdge
from bolsa_infrastructure.database.models import ResearchTreeEdgeRow
from bolsa_infrastructure.ids import new_id


class SqlAlchemyResearchTreeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _map(self, row: ResearchTreeEdgeRow) -> ResearchTreeEdge:
        return ResearchTreeEdge(
            id=row.id,
            from_ref_type=row.from_ref_type,
            from_ref_id=row.from_ref_id,
            to_ref_type=row.to_ref_type,
            to_ref_id=row.to_ref_id,
            edge_type=row.edge_type,
            created_at=row.created_at.isoformat(),
            notes=row.notes,
            payload=row.payload if isinstance(row.payload, dict) else None,
            deleted_at=None if row.deleted_at is None else row.deleted_at.isoformat(),
        )

    async def insert(
        self,
        *,
        from_ref_type: str,
        from_ref_id: str,
        to_ref_type: str,
        to_ref_id: str,
        edge_type: str,
        notes: str | None = None,
        payload: dict[str, Any] | None = None,
        edge_id: str | None = None,
    ) -> ResearchTreeEdge:
        row = ResearchTreeEdgeRow(
            id=edge_id or new_id(),
            from_ref_type=from_ref_type,
            from_ref_id=from_ref_id,
            to_ref_type=to_ref_type,
            to_ref_id=to_ref_id,
            edge_type=edge_type,
            notes=notes,
            payload=payload,
            deleted_at=None,
            created_at=datetime.now(UTC),
        )
        self._session.add(row)
        await self._session.flush()
        return self._map(row)

    async def get_by_id(self, edge_id: str) -> ResearchTreeEdge | None:
        stmt = select(ResearchTreeEdgeRow).where(ResearchTreeEdgeRow.id == edge_id)
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return None if row is None else self._map(row)

    async def soft_delete(self, edge_id: str) -> ResearchTreeEdge | None:
        stmt = select(ResearchTreeEdgeRow).where(ResearchTreeEdgeRow.id == edge_id)
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return None
        if row.deleted_at is None:
            row.deleted_at = datetime.now(UTC)
            await self._session.flush()
        return self._map(row)

    async def list_edges(
        self,
        *,
        from_ref_type: str | None = None,
        from_ref_id: str | None = None,
        to_ref_type: str | None = None,
        to_ref_id: str | None = None,
        edge_type: str | None = None,
        include_deleted: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[ResearchTreeEdge], int]:
        filters: list[ColumnElement[bool]] = []
        if not include_deleted:
            filters.append(ResearchTreeEdgeRow.deleted_at.is_(None))
        if from_ref_type:
            filters.append(ResearchTreeEdgeRow.from_ref_type == from_ref_type)
        if from_ref_id:
            filters.append(ResearchTreeEdgeRow.from_ref_id == from_ref_id)
        if to_ref_type:
            filters.append(ResearchTreeEdgeRow.to_ref_type == to_ref_type)
        if to_ref_id:
            filters.append(ResearchTreeEdgeRow.to_ref_id == to_ref_id)
        if edge_type:
            filters.append(ResearchTreeEdgeRow.edge_type == edge_type)

        count_stmt = select(func.count()).select_from(ResearchTreeEdgeRow)
        list_stmt = select(ResearchTreeEdgeRow)
        if filters:
            count_stmt = count_stmt.where(*filters)
            list_stmt = list_stmt.where(*filters)
        total = int((await self._session.execute(count_stmt)).scalar_one())
        list_stmt = (
            list_stmt.order_by(desc(ResearchTreeEdgeRow.created_at))
            .limit(limit)
            .offset(offset)
        )
        rows = (await self._session.execute(list_stmt)).scalars().all()
        return [self._map(r) for r in rows], total
