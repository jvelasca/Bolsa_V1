from datetime import UTC, datetime
from typing import Any, cast

from bolsa_domain.entities.position_policy import PositionPolicyRecord
from sqlalchemy import delete, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_infrastructure.database.models import PositionPolicyRow
from bolsa_infrastructure.ids import new_id


class SqlAlchemyPositionPolicyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _map(self, row: PositionPolicyRow) -> PositionPolicyRecord:
        return PositionPolicyRecord(
            id=row.id,
            account_id=row.account_id,
            instrument_id=row.instrument_id,
            definition=dict(row.definition),
            mode=row.mode,
            exit_strategy_definition_id=row.exit_strategy_definition_id,
            execution_policy_id=row.execution_policy_id,
            created_at=row.created_at.isoformat(),
            updated_at=row.updated_at.isoformat(),
        )

    async def list_policies(
        self,
        *,
        account_id: str | None = None,
        limit: int = 100,
    ) -> list[PositionPolicyRecord]:
        stmt = select(PositionPolicyRow).order_by(PositionPolicyRow.updated_at.desc()).limit(limit)
        if account_id is not None:
            stmt = stmt.where(PositionPolicyRow.account_id == account_id)
        result = await self._session.execute(stmt)
        return [self._map(row) for row in result.scalars().all()]

    async def get_policy(self, policy_id: str) -> PositionPolicyRecord | None:
        row = await self._session.get(PositionPolicyRow, policy_id)
        if row is None:
            return None
        return self._map(row)

    async def get_by_account_instrument(
        self,
        account_id: str,
        instrument_id: str,
    ) -> PositionPolicyRecord | None:
        stmt = select(PositionPolicyRow).where(
            PositionPolicyRow.account_id == account_id,
            PositionPolicyRow.instrument_id == instrument_id,
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return self._map(row) if row else None

    async def create_policy(
        self,
        *,
        account_id: str,
        instrument_id: str,
        definition: dict[str, Any],
        mode: str,
        exit_strategy_definition_id: str | None,
        execution_policy_id: str | None,
    ) -> PositionPolicyRecord:
        now = datetime.now(UTC)
        row = PositionPolicyRow(
            id=new_id(),
            account_id=account_id,
            instrument_id=instrument_id,
            definition=definition,
            mode=mode,
            exit_strategy_definition_id=exit_strategy_definition_id,
            execution_policy_id=execution_policy_id,
            created_at=now,
            updated_at=now,
        )
        self._session.add(row)
        await self._session.flush()
        return self._map(row)

    async def update_policy(
        self,
        policy_id: str,
        *,
        definition: dict[str, Any] | None = None,
        mode: str | None = None,
        exit_strategy_definition_id: str | None = None,
        execution_policy_id: str | None = None,
    ) -> PositionPolicyRecord | None:
        values: dict[str, Any] = {"updated_at": datetime.now(UTC)}
        if definition is not None:
            values["definition"] = definition
        if mode is not None:
            values["mode"] = mode
        if exit_strategy_definition_id is not None:
            values["exit_strategy_definition_id"] = exit_strategy_definition_id
        if execution_policy_id is not None:
            values["execution_policy_id"] = execution_policy_id
        stmt = (
            update(PositionPolicyRow)
            .where(PositionPolicyRow.id == policy_id)
            .values(**values)
            .returning(PositionPolicyRow)
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return self._map(row)

    async def delete_policy(self, policy_id: str) -> bool:
        stmt = delete(PositionPolicyRow).where(PositionPolicyRow.id == policy_id)
        result = await self._session.execute(stmt)
        return cast(CursorResult[Any], result).rowcount > 0
