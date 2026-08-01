from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_domain.entities.execution_policy import ExecutionPolicyRecord
from bolsa_infrastructure.database.models import ExecutionPolicyRow
from bolsa_infrastructure.ids import new_id


class SqlAlchemyExecutionPolicyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _map(self, row: ExecutionPolicyRow) -> ExecutionPolicyRecord:
        return ExecutionPolicyRecord(
            id=row.id,
            name=row.name,
            definition=dict(row.definition),
            mode=row.mode,
            account_id=row.account_id,
            strategy_definition_id=row.strategy_definition_id,
            origin=row.origin,
            enabled=row.enabled,
            user_id=row.user_id,
            created_at=row.created_at.isoformat(),
            updated_at=row.updated_at.isoformat(),
        )

    async def list_policies(
        self,
        *,
        limit: int = 50,
        enabled_only: bool = False,
    ) -> list[ExecutionPolicyRecord]:
        stmt = select(ExecutionPolicyRow).order_by(ExecutionPolicyRow.updated_at.desc()).limit(limit)
        if enabled_only:
            stmt = stmt.where(ExecutionPolicyRow.enabled.is_(True))
        result = await self._session.execute(stmt)
        return [self._map(row) for row in result.scalars().all()]

    async def get_policy(self, policy_id: str) -> ExecutionPolicyRecord | None:
        row = await self._session.get(ExecutionPolicyRow, policy_id)
        if row is None:
            return None
        return self._map(row)

    async def create_policy(
        self,
        *,
        name: str,
        definition: dict[str, Any],
        mode: str,
        account_id: str | None,
        strategy_definition_id: str | None,
        origin: str,
        enabled: bool,
        user_id: str | None = None,
    ) -> ExecutionPolicyRecord:
        now = datetime.now(UTC)
        row = ExecutionPolicyRow(
            id=new_id(),
            name=name,
            definition=definition,
            mode=mode,
            account_id=account_id,
            strategy_definition_id=strategy_definition_id,
            origin=origin,
            enabled=enabled,
            user_id=user_id,
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
        name: str | None = None,
        definition: dict[str, Any] | None = None,
        mode: str | None = None,
        account_id: str | None = None,
        strategy_definition_id: str | None = None,
        origin: str | None = None,
        enabled: bool | None = None,
    ) -> ExecutionPolicyRecord | None:
        values: dict[str, Any] = {"updated_at": datetime.now(UTC)}
        if name is not None:
            values["name"] = name
        if definition is not None:
            values["definition"] = definition
        if mode is not None:
            values["mode"] = mode
        if account_id is not None:
            values["account_id"] = account_id
        if strategy_definition_id is not None:
            values["strategy_definition_id"] = strategy_definition_id
        if origin is not None:
            values["origin"] = origin
        if enabled is not None:
            values["enabled"] = enabled
        stmt = (
            update(ExecutionPolicyRow)
            .where(ExecutionPolicyRow.id == policy_id)
            .values(**values)
            .returning(ExecutionPolicyRow)
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return self._map(row)

    async def delete_policy(self, policy_id: str) -> bool:
        stmt = delete(ExecutionPolicyRow).where(ExecutionPolicyRow.id == policy_id)
        result = await self._session.execute(stmt)
        return result.rowcount > 0
