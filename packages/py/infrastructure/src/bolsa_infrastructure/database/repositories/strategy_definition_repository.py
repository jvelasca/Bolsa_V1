from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_analytics.signals.preset_catalog import is_valid_preset_key
from bolsa_domain.entities.strategy_definition import StrategyDefinitionRecord
from bolsa_infrastructure.database.models import (
    BacktestRunRow,
    ExecutionPolicyRow,
    InvestmentAccountRow,
    PositionPolicyRow,
    ScanManifestRow,
    SignalAlertSubscriptionRow,
    StrategyDefinitionRow,
    TrackerDefinitionRow,
)
from bolsa_infrastructure.ids import new_id


class SqlAlchemyStrategyDefinitionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _map(self, row: StrategyDefinitionRow) -> StrategyDefinitionRecord:
        preset = row.preset_key
        # Full catalog (21+). Old whitelist sma/rsi only → Finalistas re-run ERROR.
        preset_key = preset if is_valid_preset_key(preset) else None
        if preset_key is None and isinstance(row.definition, dict):
            nested = row.definition.get("presetKey")
            if isinstance(nested, str) and is_valid_preset_key(nested):
                preset_key = nested
        return StrategyDefinitionRecord(
            id=row.id,
            name=row.name,
            definition=row.definition,
            preset_key=preset_key,
            origin=row.origin,
            timeframe=row.timeframe,
            created_at=row.created_at.isoformat(),
            updated_at=row.updated_at.isoformat(),
        )

    async def list_definitions(self, limit: int = 50) -> list[StrategyDefinitionRecord]:
        stmt = (
            select(StrategyDefinitionRow)
            .order_by(StrategyDefinitionRow.updated_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return [self._map(row) for row in result.scalars().all()]

    async def get_definition(self, definition_id: str) -> StrategyDefinitionRecord | None:
        row = await self._session.get(StrategyDefinitionRow, definition_id)
        if row is None:
            return None
        return self._map(row)

    async def create_definition(
        self,
        *,
        name: str,
        definition: dict[str, Any],
        preset_key: str | None,
        origin: str,
        timeframe: str,
    ) -> StrategyDefinitionRecord:
        now = datetime.now(UTC)
        row = StrategyDefinitionRow(
            id=new_id(),
            name=name,
            definition=definition,
            preset_key=preset_key,
            origin=origin,
            timeframe=timeframe,
            created_at=now,
            updated_at=now,
        )
        self._session.add(row)
        await self._session.flush()
        return self._map(row)

    async def update_definition(
        self,
        definition_id: str,
        *,
        name: str | None = None,
        definition: dict[str, Any] | None = None,
        preset_key: str | None = None,
        origin: str | None = None,
        timeframe: str | None = None,
    ) -> StrategyDefinitionRecord | None:
        values: dict[str, Any] = {"updated_at": datetime.now(UTC)}
        if name is not None:
            values["name"] = name
        if definition is not None:
            values["definition"] = definition
        if preset_key is not None:
            values["preset_key"] = preset_key
        if origin is not None:
            values["origin"] = origin
        if timeframe is not None:
            values["timeframe"] = timeframe
        stmt = (
            update(StrategyDefinitionRow)
            .where(StrategyDefinitionRow.id == definition_id)
            .values(**values)
            .returning(StrategyDefinitionRow)
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return self._map(row)

    async def delete_definition(self, definition_id: str) -> bool:
        existing = await self._session.get(StrategyDefinitionRow, definition_id)
        if existing is None:
            return False

        await self._session.execute(
            update(BacktestRunRow)
            .where(BacktestRunRow.strategy_definition_id == definition_id)
            .values(strategy_definition_id=None)
        )
        await self._session.execute(
            update(SignalAlertSubscriptionRow)
            .where(SignalAlertSubscriptionRow.strategy_definition_id == definition_id)
            .values(strategy_definition_id=None)
        )
        await self._session.execute(
            update(ScanManifestRow)
            .where(ScanManifestRow.strategy_definition_id == definition_id)
            .values(strategy_definition_id=None)
        )
        await self._session.execute(
            update(ExecutionPolicyRow)
            .where(ExecutionPolicyRow.strategy_definition_id == definition_id)
            .values(strategy_definition_id=None)
        )
        await self._session.execute(
            update(PositionPolicyRow)
            .where(PositionPolicyRow.exit_strategy_definition_id == definition_id)
            .values(exit_strategy_definition_id=None)
        )
        await self._session.execute(
            update(InvestmentAccountRow)
            .where(InvestmentAccountRow.strategy_definition_id == definition_id)
            .values(strategy_definition_id=None)
        )
        await self._session.execute(
            delete(TrackerDefinitionRow).where(
                TrackerDefinitionRow.strategy_definition_id == definition_id,
            )
        )

        result = await self._session.execute(
            delete(StrategyDefinitionRow).where(StrategyDefinitionRow.id == definition_id),
        )
        return result.rowcount > 0
