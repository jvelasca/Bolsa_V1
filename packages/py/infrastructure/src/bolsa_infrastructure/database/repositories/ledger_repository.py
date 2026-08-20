from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bolsa_domain.entities.account import LedgerEntry
from bolsa_infrastructure.database.models import LedgerEntryRow
from bolsa_infrastructure.ids import new_id


def _entry_from_row(row: LedgerEntryRow, symbol: str | None = None) -> LedgerEntry:
    return LedgerEntry(
        id=row.id,
        account_id=row.account_id,
        portfolio_id=row.portfolio_id,
        type=row.type,
        amount=float(row.amount),
        currency=row.currency,
        balance_after=float(row.balance_after),
        instrument_id=row.instrument_id,
        symbol=symbol,
        quantity=float(row.quantity) if row.quantity is not None else None,
        price=float(row.price) if row.price is not None else None,
        reference_type=row.reference_type,
        reference_id=row.reference_id,
        description=row.description,
        executed_at=row.executed_at.isoformat(),
    )


class SqlAlchemyLedgerRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def append_trade(
        self,
        *,
        account_id: str,
        portfolio_id: str,
        entry_type: str,
        amount: float,
        currency: str,
        balance_after: float,
        instrument_id: str,
        quantity: float,
        price: float,
        reference_id: str,
        executed_at: datetime | None = None,
    ) -> LedgerEntry:
        now = datetime.now(UTC)
        executed = executed_at or now
        row = LedgerEntryRow(
            id=new_id(),
            account_id=account_id,
            portfolio_id=portfolio_id,
            type=entry_type,
            amount=Decimal(str(amount)),
            currency=currency,
            balance_after=Decimal(str(balance_after)),
            instrument_id=instrument_id,
            quantity=Decimal(str(quantity)),
            price=Decimal(str(price)),
            reference_type="transaction",
            reference_id=reference_id,
            description=None,
            executed_at=executed,
            created_at=now,
        )
        self._session.add(row)
        await self._session.flush()
        return _entry_from_row(row)

    async def append_fee(
        self,
        *,
        account_id: str,
        portfolio_id: str,
        amount: float,
        currency: str,
        balance_after: float,
        reference_id: str,
        description: str | None = None,
        executed_at: datetime | None = None,
    ) -> LedgerEntry:
        now = datetime.now(UTC)
        executed = executed_at or now
        row = LedgerEntryRow(
            id=new_id(),
            account_id=account_id,
            portfolio_id=portfolio_id,
            type="fee",
            amount=Decimal(str(-abs(amount))),
            currency=currency,
            balance_after=Decimal(str(balance_after)),
            instrument_id=None,
            quantity=None,
            price=None,
            reference_type="transaction",
            reference_id=reference_id,
            description=description or "Comisiones e impuestos de operación",
            executed_at=executed,
            created_at=now,
        )
        self._session.add(row)
        await self._session.flush()
        return _entry_from_row(row)

    async def list_for_account(
        self,
        account_id: str,
        *,
        limit: int = 50,
        offset: int = 0,
        portfolio_id: str | None = None,
        executed_from: datetime | None = None,
        executed_to: datetime | None = None,
    ) -> list[LedgerEntry]:
        stmt = (
            select(LedgerEntryRow)
            .where(LedgerEntryRow.account_id == account_id)
            .options(selectinload(LedgerEntryRow.instrument))
            .order_by(LedgerEntryRow.executed_at.desc())
            .offset(offset)
            .limit(limit)
        )
        if portfolio_id is not None:
            stmt = stmt.where(LedgerEntryRow.portfolio_id == portfolio_id)
        if executed_from is not None:
            # F-FIN-2: acotar el ledger al ejercicio fiscal (fees del año).
            stmt = stmt.where(LedgerEntryRow.executed_at >= executed_from)
        if executed_to is not None:
            stmt = stmt.where(LedgerEntryRow.executed_at < executed_to)
        rows = (await self._session.execute(stmt)).scalars().all()
        return [
            _entry_from_row(row, row.instrument.symbol if row.instrument else None)
            for row in rows
        ]

    async def has_reference(self, reference_type: str, reference_id: str) -> bool:
        stmt = select(LedgerEntryRow.id).where(
            LedgerEntryRow.reference_type == reference_type,
            LedgerEntryRow.reference_id == reference_id,
        )
        return (await self._session.execute(stmt)).scalar_one_or_none() is not None

    async def find_cash_movement_by_reference(
        self,
        reference_type: str,
        reference_id: str,
    ) -> LedgerEntry | None:
        """Localiza el movimiento de caja original por su reference (idempotencia A-2).

        Devuelve la entrada más antigua (ejecución original) para poder replicala en
        un reintento con la misma idempotency_key sin volver a mover efectivo.
        """
        stmt = (
            select(LedgerEntryRow)
            .where(
                LedgerEntryRow.reference_type == reference_type,
                LedgerEntryRow.reference_id == reference_id,
            )
            .order_by(LedgerEntryRow.executed_at.asc())
            .limit(1)
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return _entry_from_row(row) if row is not None else None

    async def last_custody_charge_at(self, account_id: str) -> datetime | None:
        stmt = (
            select(LedgerEntryRow.executed_at)
            .where(
                LedgerEntryRow.account_id == account_id,
                LedgerEntryRow.reference_type == "custody",
            )
            .order_by(LedgerEntryRow.executed_at.desc())
            .limit(1)
        )
        result = (await self._session.execute(stmt)).scalar_one_or_none()
        return result

    async def append_custody_fee(
        self,
        *,
        account_id: str,
        portfolio_id: str,
        amount: float,
        currency: str,
        balance_after: float,
        reference_id: str,
        description: str,
    ) -> LedgerEntry:
        now = datetime.now(UTC)
        row = LedgerEntryRow(
            id=new_id(),
            account_id=account_id,
            portfolio_id=portfolio_id,
            type="fee",
            amount=Decimal(str(-abs(amount))),
            currency=currency,
            balance_after=Decimal(str(balance_after)),
            instrument_id=None,
            quantity=None,
            price=None,
            reference_type="custody",
            reference_id=reference_id,
            description=description,
            executed_at=now,
            created_at=now,
        )
        self._session.add(row)
        await self._session.flush()
        return _entry_from_row(row)

    async def total_fees_for_account(
        self,
        account_id: str,
        *,
        executed_from: datetime | None = None,
        executed_to: datetime | None = None,
    ) -> float:
        stmt = select(LedgerEntryRow.amount).where(
            LedgerEntryRow.account_id == account_id,
            LedgerEntryRow.type == "fee",
        )
        if executed_from is not None:
            stmt = stmt.where(LedgerEntryRow.executed_at >= executed_from)
        if executed_to is not None:
            stmt = stmt.where(LedgerEntryRow.executed_at < executed_to)
        amounts = (await self._session.execute(stmt)).scalars().all()
        return sum(abs(float(amount)) for amount in amounts)

    async def append_cash_movement(
        self,
        *,
        account_id: str,
        portfolio_id: str,
        entry_type: str,
        amount: float,
        currency: str,
        balance_after: float,
        reference_id: str,
        reference_type: str = "transfer",
        description: str | None = None,
    ) -> LedgerEntry:
        now = datetime.now(UTC)
        row = LedgerEntryRow(
            id=new_id(),
            account_id=account_id,
            portfolio_id=portfolio_id,
            type=entry_type,
            amount=Decimal(str(amount)),
            currency=currency,
            balance_after=Decimal(str(balance_after)),
            instrument_id=None,
            quantity=None,
            price=None,
            reference_type=reference_type,
            reference_id=reference_id,
            description=description,
            executed_at=now,
            created_at=now,
        )
        self._session.add(row)
        await self._session.flush()
        return _entry_from_row(row)
