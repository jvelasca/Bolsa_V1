"""Repositorio P1 — PositionState persistida (ADR-033)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_infrastructure.database.models.tables import PositionStateRow
from bolsa_infrastructure.ids import new_id


@dataclass(frozen=True, slots=True)
class PositionStateRecord:
    id: str
    account_id: str
    instrument_id: str
    ledger_position_id: str | None
    open_transaction_id: str
    trade_plan_id: str
    status: str
    trade_plan_snapshot: dict[str, Any]
    position_state: dict[str, Any]
    birth_override_reason: str | None
    created_at: str
    updated_at: str


def _to_record(row: PositionStateRow) -> PositionStateRecord:
    return PositionStateRecord(
        id=row.id,
        account_id=row.account_id,
        instrument_id=row.instrument_id,
        ledger_position_id=row.ledger_position_id,
        open_transaction_id=row.open_transaction_id,
        trade_plan_id=row.trade_plan_id,
        status=row.status,
        trade_plan_snapshot=dict(row.trade_plan_snapshot or {}),
        position_state=dict(row.position_state or {}),
        birth_override_reason=row.birth_override_reason,
        created_at=row.created_at.isoformat(),
        updated_at=row.updated_at.isoformat(),
    )


class SqlAlchemyPositionStateRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_open_transaction_id(
        self,
        open_transaction_id: str,
    ) -> PositionStateRecord | None:
        stmt = select(PositionStateRow).where(
            PositionStateRow.open_transaction_id == open_transaction_id
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return _to_record(row) if row is not None else None

    async def get_open_for_instrument(
        self,
        account_id: str,
        instrument_id: str,
    ) -> PositionStateRecord | None:
        stmt = select(PositionStateRow).where(
            PositionStateRow.account_id == account_id,
            PositionStateRow.instrument_id == instrument_id,
            PositionStateRow.status != "CLOSED",
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return _to_record(row) if row is not None else None

    async def list_open_for_account(self, account_id: str) -> list[PositionStateRecord]:
        stmt = (
            select(PositionStateRow)
            .where(
                PositionStateRow.account_id == account_id,
                PositionStateRow.status != "CLOSED",
            )
            .order_by(PositionStateRow.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return [_to_record(row) for row in result.scalars().all()]

    async def insert(
        self,
        *,
        account_id: str,
        instrument_id: str,
        ledger_position_id: str | None,
        open_transaction_id: str,
        trade_plan_id: str,
        status: str,
        trade_plan_snapshot: dict[str, Any],
        position_state: dict[str, Any],
        birth_override_reason: str | None,
        position_id: str | None = None,
    ) -> PositionStateRecord:
        now = datetime.now(UTC)
        row = PositionStateRow(
            id=position_id.strip() if isinstance(position_id, str) and position_id.strip() else new_id(),
            account_id=account_id,
            instrument_id=instrument_id,
            ledger_position_id=ledger_position_id,
            open_transaction_id=open_transaction_id,
            trade_plan_id=trade_plan_id,
            status=status,
            trade_plan_snapshot=trade_plan_snapshot,
            position_state=position_state,
            birth_override_reason=birth_override_reason,
            created_at=now,
            updated_at=now,
        )
        self._session.add(row)
        await self._session.flush()
        return _to_record(row)

    async def update_state(
        self,
        *,
        position_id: str,
        status: str,
        position_state: dict[str, Any],
    ) -> PositionStateRecord | None:
        """P3 — persiste reduce/cierre. No inserta natalicio."""
        pid = position_id.strip() if position_id else ""
        if not pid:
            return None
        stmt = select(PositionStateRow).where(PositionStateRow.id == pid)
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return None
        row.status = status
        row.position_state = position_state
        row.updated_at = datetime.now(UTC)
        await self._session.flush()
        return _to_record(row)
