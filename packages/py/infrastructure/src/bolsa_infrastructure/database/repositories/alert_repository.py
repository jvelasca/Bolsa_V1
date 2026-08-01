from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_infrastructure.database.models import InstrumentRow, PriceAlertRow
from bolsa_infrastructure.ids import new_id

AlertCondition = Literal["above", "below"]
AlertPriceSource = Literal["daily_close", "xtb_last"]


@dataclass(frozen=True, slots=True)
class PriceAlertRecord:
    id: str
    instrument_id: str
    symbol: str
    condition: AlertCondition
    price_source: AlertPriceSource
    target_price: float
    is_active: bool
    triggered_at: str | None
    triggered_price: float | None
    note: str | None
    created_at: str


class SqlAlchemyAlertRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_all(self, *, active_only: bool = False) -> list[PriceAlertRecord]:
        stmt = select(PriceAlertRow).order_by(PriceAlertRow.created_at.desc())
        if active_only:
            stmt = stmt.where(PriceAlertRow.is_active.is_(True))
        result = await self._session.execute(stmt)
        return [self._to_record(row) for row in result.scalars().all()]

    async def get_by_id(self, alert_id: str) -> PriceAlertRecord | None:
        stmt = select(PriceAlertRow).where(PriceAlertRow.id == alert_id)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return self._to_record(row)

    async def create(
        self,
        *,
        instrument_id: str,
        condition: AlertCondition,
        target_price: float,
        price_source: AlertPriceSource = "daily_close",
        note: str | None = None,
    ) -> PriceAlertRecord:
        stmt = select(InstrumentRow).where(InstrumentRow.id == instrument_id)
        result = await self._session.execute(stmt)
        instrument = result.scalar_one_or_none()
        if instrument is None:
            raise ValueError("Instrumento no encontrado")

        now = datetime.now(UTC)
        row = PriceAlertRow(
            id=new_id(),
            instrument_id=instrument_id,
            symbol=instrument.symbol,
            condition=condition,
            price_source=price_source,
            target_price=target_price,
            is_active=True,
            triggered_at=None,
            triggered_price=None,
            note=note,
            created_at=now,
        )
        self._session.add(row)
        await self._session.flush()
        return self._to_record(row)

    async def delete(self, alert_id: str) -> bool:
        stmt = delete(PriceAlertRow).where(PriceAlertRow.id == alert_id)
        result = await self._session.execute(stmt)
        return result.rowcount > 0

    async def mark_triggered(self, alert_id: str, *, price: float) -> PriceAlertRecord | None:
        now = datetime.now(UTC)
        stmt = (
            update(PriceAlertRow)
            .where(PriceAlertRow.id == alert_id, PriceAlertRow.is_active.is_(True))
            .values(
                is_active=False,
                triggered_at=now,
                triggered_price=price,
            )
            .returning(PriceAlertRow)
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return self._to_record(row)

    async def reactivate(self, alert_id: str) -> PriceAlertRecord | None:
        stmt = (
            update(PriceAlertRow)
            .where(PriceAlertRow.id == alert_id, PriceAlertRow.is_active.is_(False))
            .values(
                is_active=True,
                triggered_at=None,
                triggered_price=None,
            )
            .returning(PriceAlertRow)
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return self._to_record(row)

    def _to_record(self, row: PriceAlertRow) -> PriceAlertRecord:
        return PriceAlertRecord(
            id=row.id,
            instrument_id=row.instrument_id,
            symbol=row.symbol,
            condition=row.condition,
            price_source=row.price_source,
            target_price=float(row.target_price),
            is_active=row.is_active,
            triggered_at=row.triggered_at.isoformat() if row.triggered_at else None,
            triggered_price=float(row.triggered_price) if row.triggered_price is not None else None,
            note=row.note,
            created_at=row.created_at.isoformat(),
        )
