"""Repositorio P1 — PositionState persistida (ADR-033). JP-1 dual-write hot columns."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
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


def _numeric_from_blob(raw: object) -> Decimal | None:
    if raw is None or isinstance(raw, bool):
        return None
    if isinstance(raw, Decimal):
        return raw
    if isinstance(raw, (int, float)):
        try:
            return Decimal(str(raw))
        except (InvalidOperation, ValueError):
            return None
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return None
        try:
            return Decimal(text)
        except (InvalidOperation, ValueError):
            return None
    return None


def hot_scalars_from_position_state(position_state: dict[str, Any]) -> dict[str, Any]:
    """JP-1 — extract dual-write columns from PositionState.to_dict() camelCase blob."""
    direction_raw = position_state.get("direction")
    direction: str | None
    if direction_raw is None:
        direction = None
    elif isinstance(direction_raw, str):
        direction = direction_raw.strip() or None
    else:
        direction = str(direction_raw)

    return {
        "direction": direction,
        "current_stop": _numeric_from_blob(position_state.get("currentStop")),
        "remaining_quantity": _numeric_from_blob(position_state.get("remainingQuantity")),
        "quantity": _numeric_from_blob(position_state.get("quantity")),
        "initial_stop": _numeric_from_blob(position_state.get("initialStop")),
        "actual_entry": _numeric_from_blob(position_state.get("actualEntry")),
    }


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

    async def list_for_account(self, account_id: str) -> list[PositionStateRecord]:
        """V1.93 — all PositionState rows for account (open + closed) for lifecycle recon."""
        stmt = (
            select(PositionStateRow)
            .where(PositionStateRow.account_id == account_id)
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
        hot = hot_scalars_from_position_state(position_state)
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
            **hot,
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
        """P3 — persiste reduce/cierre. No inserta natalicio. JP-1 dual-write hot cols."""
        pid = position_id.strip() if position_id else ""
        if not pid:
            return None
        stmt = select(PositionStateRow).where(PositionStateRow.id == pid)
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return None
        hot = hot_scalars_from_position_state(position_state)
        row.status = status
        row.position_state = position_state
        row.direction = hot["direction"]
        row.current_stop = hot["current_stop"]
        row.remaining_quantity = hot["remaining_quantity"]
        row.quantity = hot["quantity"]
        row.initial_stop = hot["initial_stop"]
        row.actual_entry = hot["actual_entry"]
        row.updated_at = datetime.now(UTC)
        await self._session.flush()
        return _to_record(row)

    async def compare_and_swap_stop(
        self,
        *,
        position_id: str,
        expected_stop: float,
        status: str,
        position_state: dict[str, Any],
    ) -> PositionStateRecord | None:
        """V1.48 — UPDATE iff hot current_stop matches expected (row lock)."""
        pid = position_id.strip() if position_id else ""
        if not pid:
            return None
        stmt = (
            select(PositionStateRow)
            .where(PositionStateRow.id == pid)
            .with_for_update()
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return None
        current = row.current_stop
        if current is None:
            current = _numeric_from_blob((row.position_state or {}).get("currentStop"))
        try:
            expected = Decimal(str(expected_stop))
        except (InvalidOperation, ValueError):
            return None
        if current is None or abs(current - expected) > Decimal("0.000000001"):
            return None
        hot = hot_scalars_from_position_state(position_state)
        row.status = status
        row.position_state = position_state
        row.direction = hot["direction"]
        row.current_stop = hot["current_stop"]
        row.remaining_quantity = hot["remaining_quantity"]
        row.quantity = hot["quantity"]
        row.initial_stop = hot["initial_stop"]
        row.actual_entry = hot["actual_entry"]
        row.updated_at = datetime.now(UTC)
        await self._session.flush()
        return _to_record(row)
