"""Custody obligation repository (R-11 C1 / R-10.6) — obligación MULTI-periodo.

La deuda de custodia vive en ``custody_obligations`` (PK ``id`` + ``UNIQUE(account_id,
period)``): UNA fila por (cuenta, año). Un PENDING de un periodo anterior se conserva
aunque se genere/cobre el periodo actual. ``status`` solo ``PENDING`` | ``APPLIED``.
La antigua tabla ``custody_obligation`` (005, una fila por cuenta) no se usa ya.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_domain.entities.account import CustodyObligation
from bolsa_infrastructure.database.models import CustodyObligationRow


def _obligation_from_row(row: CustodyObligationRow) -> CustodyObligation:
    return CustodyObligation(
        id=row.id,
        account_id=row.account_id,
        period=row.period,
        status=row.status,
        outstanding=float(row.outstanding),
        total_fee=float(row.total_fee),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class CustodyObligationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @property
    def session(self) -> AsyncSession:
        """Sesión activa — expone la sesión para los savepoints de los use-cases."""
        return self._session

    async def get_by_account(self, account_id: str) -> list[CustodyObligation]:
        """Todas las obligaciones de la cuenta ordenadas por ``period`` ASC."""
        stmt = (
            select(CustodyObligationRow)
            .where(CustodyObligationRow.account_id == account_id)
            .order_by(CustodyObligationRow.period.asc())
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_obligation_from_row(row) for row in rows]

    async def get_pending_by_account(self, account_id: str) -> list[CustodyObligation]:
        """Obligaciones ``status == "PENDING"`` de la cuenta, la más antigua primero."""
        stmt = (
            select(CustodyObligationRow)
            .where(
                CustodyObligationRow.account_id == account_id,
                CustodyObligationRow.status == "PENDING",
            )
            .order_by(CustodyObligationRow.period.asc())
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_obligation_from_row(row) for row in rows]

    async def get_by_account_period(
        self, account_id: str, period: str
    ) -> CustodyObligation | None:
        """Obligación exacta de la cuenta para el ``period`` dado, o ``None``."""
        stmt = select(CustodyObligationRow).where(
            CustodyObligationRow.account_id == account_id,
            CustodyObligationRow.period == period,
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return None if row is None else _obligation_from_row(row)

    async def upsert(
        self,
        *,
        account_id: str,
        period: str,
        status: str,
        outstanding: float,
        total_fee: float,
    ) -> CustodyObligation:
        """Inserta la fila ``(account_id, period)`` o actualiza su estado si existe.

        Con ``UNIQUE(account_id, period)`` cada (cuenta, año) tiene exactamente una
        fila; un PENDING de un año anterior no se sobrescribe al escribir otro periodo.
        """
        stmt = select(CustodyObligationRow).where(
            CustodyObligationRow.account_id == account_id,
            CustodyObligationRow.period == period,
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        now = datetime.now(tz=UTC)
        if row is None:
            row = CustodyObligationRow(
                account_id=account_id,
                period=period,
                status=status,
                outstanding=Decimal(str(outstanding)),
                total_fee=Decimal(str(total_fee)),
                created_at=now,
                updated_at=now,
            )
            self._session.add(row)
        else:
            row.status = status
            row.outstanding = Decimal(str(outstanding))
            row.total_fee = Decimal(str(total_fee))
            row.updated_at = now
        await self._session.flush()
        return _obligation_from_row(row)
