from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import delete, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_domain.entities.tracker_definition import TrackerDefinitionRecord
from bolsa_infrastructure.database.models import TrackerDefinitionRow
from bolsa_infrastructure.ids import new_id


class SqlAlchemyTrackerDefinitionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _map(self, row: TrackerDefinitionRow) -> TrackerDefinitionRecord:
        return TrackerDefinitionRecord(
            id=row.id,
            name=row.name,
            definition=dict(row.definition),
            strategy_definition_id=row.strategy_definition_id,
            strategy_version=row.strategy_version,
            timeframe=row.timeframe,
            evaluation_mode=row.evaluation_mode,
            origin=row.origin,
            enabled=row.enabled,
            user_id=row.user_id,
            created_at=row.created_at.isoformat(),
            updated_at=row.updated_at.isoformat(),
        )

    async def list_trackers(
        self,
        *,
        limit: int = 50,
        enabled_only: bool = False,
    ) -> list[TrackerDefinitionRecord]:
        stmt = select(TrackerDefinitionRow).order_by(TrackerDefinitionRow.updated_at.desc()).limit(limit)
        if enabled_only:
            stmt = stmt.where(TrackerDefinitionRow.enabled.is_(True))
        result = await self._session.execute(stmt)
        return [self._map(row) for row in result.scalars().all()]

    async def list_trackers_for_list(
        self,
        list_id: str,
        *,
        limit: int = 50,
    ) -> list[TrackerDefinitionRecord]:
        stmt = (
            select(TrackerDefinitionRow)
            .where(TrackerDefinitionRow.definition["universe"]["listId"].astext == list_id)
            .order_by(TrackerDefinitionRow.updated_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return [self._map(row) for row in result.scalars().all()]

    async def get_tracker(self, tracker_id: str) -> TrackerDefinitionRecord | None:
        row = await self._session.get(TrackerDefinitionRow, tracker_id)
        if row is None:
            return None
        return self._map(row)

    async def create_tracker(
        self,
        *,
        name: str,
        definition: dict[str, Any],
        strategy_definition_id: str,
        strategy_version: int | None,
        timeframe: str,
        evaluation_mode: str,
        origin: str,
        enabled: bool,
        user_id: str | None = None,
    ) -> TrackerDefinitionRecord:
        now = datetime.now(UTC)
        row = TrackerDefinitionRow(
            id=new_id(),
            name=name,
            definition=definition,
            strategy_definition_id=strategy_definition_id,
            strategy_version=strategy_version,
            timeframe=timeframe,
            evaluation_mode=evaluation_mode,
            origin=origin,
            enabled=enabled,
            user_id=user_id,
            created_at=now,
            updated_at=now,
        )
        self._session.add(row)
        await self._session.flush()
        return self._map(row)

    async def update_tracker(
        self,
        tracker_id: str,
        *,
        name: str | None = None,
        definition: dict[str, Any] | None = None,
        strategy_definition_id: str | None = None,
        strategy_version: int | None = None,
        timeframe: str | None = None,
        evaluation_mode: str | None = None,
        origin: str | None = None,
        enabled: bool | None = None,
    ) -> TrackerDefinitionRecord | None:
        values: dict[str, Any] = {"updated_at": datetime.now(UTC)}
        if name is not None:
            values["name"] = name
        if definition is not None:
            values["definition"] = definition
        if strategy_definition_id is not None:
            values["strategy_definition_id"] = strategy_definition_id
        if strategy_version is not None:
            values["strategy_version"] = strategy_version
        if timeframe is not None:
            values["timeframe"] = timeframe
        if evaluation_mode is not None:
            values["evaluation_mode"] = evaluation_mode
        if origin is not None:
            values["origin"] = origin
        if enabled is not None:
            values["enabled"] = enabled
        stmt = (
            update(TrackerDefinitionRow)
            .where(TrackerDefinitionRow.id == tracker_id)
            .values(**values)
            .returning(TrackerDefinitionRow)
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return self._map(row)

    async def delete_tracker(self, tracker_id: str) -> bool:
        stmt = delete(TrackerDefinitionRow).where(TrackerDefinitionRow.id == tracker_id)
        result = await self._session.execute(stmt)
        return cast(CursorResult[Any], result).rowcount > 0
