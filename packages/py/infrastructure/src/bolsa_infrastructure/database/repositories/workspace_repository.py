from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_infrastructure.database.models import WorkspaceRow
from bolsa_infrastructure.ids import new_id


@dataclass(frozen=True, slots=True)
class WorkspaceSummary:
    id: str
    name: str
    is_default: bool
    updated_at: str


@dataclass(frozen=True, slots=True)
class WorkspaceRecord:
    id: str
    name: str
    is_default: bool
    document: dict
    dock_layout: dict | None
    created_at: str
    updated_at: str


def _to_summary(row: WorkspaceRow) -> WorkspaceSummary:
    return WorkspaceSummary(
        id=row.id,
        name=row.name,
        is_default=row.is_default,
        updated_at=row.updated_at.isoformat(),
    )


def _to_record(row: WorkspaceRow) -> WorkspaceRecord:
    return WorkspaceRecord(
        id=row.id,
        name=row.name,
        is_default=row.is_default,
        document=row.document,
        dock_layout=row.dock_layout,
        created_at=row.created_at.isoformat(),
        updated_at=row.updated_at.isoformat(),
    )


class SqlAlchemyWorkspaceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_all(self) -> list[WorkspaceSummary]:
        stmt = select(WorkspaceRow).order_by(WorkspaceRow.is_default.desc(), WorkspaceRow.name.asc())
        result = await self._session.execute(stmt)
        return [_to_summary(row) for row in result.scalars().all()]

    async def get_by_id(self, workspace_id: str) -> WorkspaceRecord | None:
        stmt = select(WorkspaceRow).where(WorkspaceRow.id == workspace_id)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return _to_record(row) if row else None

    async def get_default(self) -> WorkspaceRecord | None:
        stmt = (
            select(WorkspaceRow)
            .where(WorkspaceRow.is_default.is_(True))
            .order_by(WorkspaceRow.updated_at.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row:
            return _to_record(row)
        stmt_any = select(WorkspaceRow).order_by(WorkspaceRow.updated_at.desc()).limit(1)
        result_any = await self._session.execute(stmt_any)
        fallback = result_any.scalar_one_or_none()
        return _to_record(fallback) if fallback else None

    async def create(
        self,
        *,
        name: str,
        document: dict,
        dock_layout: dict | None = None,
        is_default: bool = False,
    ) -> WorkspaceRecord:
        now = datetime.now(timezone.utc)
        if is_default:
            await self._clear_default_flag()

        row = WorkspaceRow(
            id=new_id(),
            name=name.strip(),
            document=document,
            dock_layout=dock_layout,
            is_default=is_default,
            created_at=now,
            updated_at=now,
        )
        self._session.add(row)
        await self._session.flush()
        return _to_record(row)

    async def update(
        self,
        workspace_id: str,
        *,
        name: str | None = None,
        document: dict | None = None,
        dock_layout: dict | None = None,
        is_default: bool | None = None,
    ) -> WorkspaceRecord | None:
        stmt = select(WorkspaceRow).where(WorkspaceRow.id == workspace_id)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None

        if name is not None:
            row.name = name.strip()
        if document is not None:
            row.document = document
        if dock_layout is not None:
            row.dock_layout = dock_layout
        if is_default is not None:
            if is_default:
                await self._clear_default_flag(exclude_id=workspace_id)
            row.is_default = is_default
        row.updated_at = datetime.now(timezone.utc)
        await self._session.flush()
        return _to_record(row)

    async def delete(self, workspace_id: str) -> bool:
        stmt = select(WorkspaceRow).where(WorkspaceRow.id == workspace_id)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return False

        was_default = row.is_default
        await self._session.delete(row)
        await self._session.flush()

        if was_default:
            stmt_next = select(WorkspaceRow).order_by(WorkspaceRow.updated_at.desc()).limit(1)
            next_result = await self._session.execute(stmt_next)
            next_row = next_result.scalar_one_or_none()
            if next_row:
                next_row.is_default = True
                await self._session.flush()
        return True

    async def count(self) -> int:
        result = await self._session.execute(select(WorkspaceRow.id))
        return len(result.scalars().all())

    async def _clear_default_flag(self, *, exclude_id: str | None = None) -> None:
        stmt = update(WorkspaceRow).values(is_default=False)
        if exclude_id:
            stmt = stmt.where(WorkspaceRow.id != exclude_id)
        await self._session.execute(stmt)
