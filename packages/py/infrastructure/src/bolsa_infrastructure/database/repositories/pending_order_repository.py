from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_infrastructure.database.models import PendingOrderRow
from bolsa_infrastructure.ids import new_id


@dataclass(frozen=True, slots=True)
class PendingOrderRecord:
    id: str
    instrument_id: str
    symbol: str
    side: str
    order_type: str
    quantity: float
    limit_price: float
    expiry_at: str | None
    created_at: str


def _to_record(row: PendingOrderRow) -> PendingOrderRecord:
    return PendingOrderRecord(
        id=row.id,
        instrument_id=row.instrument_id,
        symbol=row.symbol,
        side=row.side,
        order_type=row.order_type,
        quantity=float(row.quantity),
        limit_price=float(row.limit_price),
        expiry_at=row.expiry_at.isoformat() if row.expiry_at else None,
        created_at=row.created_at.isoformat(),
    )


class SqlAlchemyPendingOrderRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_account(self, account_id: str) -> list[PendingOrderRecord]:
        stmt = (
            select(PendingOrderRow)
            .where(PendingOrderRow.account_id == account_id)
            .order_by(PendingOrderRow.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return [_to_record(row) for row in result.scalars().all()]

    async def list_all(self) -> list[PendingOrderRecord]:
        stmt = select(PendingOrderRow).order_by(PendingOrderRow.created_at.desc())
        result = await self._session.execute(stmt)
        return [_to_record(row) for row in result.scalars().all()]

    async def create(
        self,
        *,
        account_id: str,
        instrument_id: str,
        symbol: str,
        side: str,
        order_type: str,
        quantity: float,
        limit_price: float,
        expiry_at: datetime | None,
    ) -> PendingOrderRecord:
        now = datetime.now(timezone.utc)
        row = PendingOrderRow(
            id=new_id(),
            account_id=account_id,
            instrument_id=instrument_id,
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=Decimal(str(quantity)),
            limit_price=Decimal(str(limit_price)),
            expiry_at=expiry_at,
            created_at=now,
        )
        self._session.add(row)
        await self._session.flush()
        return _to_record(row)

    async def delete(self, order_id: str, account_id: str | None = None) -> bool:
        stmt = select(PendingOrderRow).where(PendingOrderRow.id == order_id)
        if account_id is not None:
            stmt = stmt.where(PendingOrderRow.account_id == account_id)
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return False
        await self._session.delete(row)
        await self._session.flush()
        return True
