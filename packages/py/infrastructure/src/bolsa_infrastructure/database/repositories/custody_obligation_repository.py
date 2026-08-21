"""Custody obligation repository (ADR 026 / F4a) — obligación pendiente por cuenta.

Una fila por cuenta (PK ``account_id``), un único periodo pendiente en curso. El
``status`` solo puede ser ``PENDING`` | ``APPLIED``. La tabla nace sin backfill
(forward-only, D6): solo se escribe desde ``ApplyCustodyFees``.
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
        account_id=row.account_id,
        period=row.period,
        status=row.status,
        outstanding=float(row.outstanding),
        total_fee=float(row.total_fee),
    )


class CustodyObligationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @property
    def session(self) -> AsyncSession:
        """Sesión activa — expone la sesión para los savepoints de los use-cases."""
        return self._session

    async def get_by_account(self, account_id: str) -> CustodyObligation | None:
        stmt = select(CustodyObligationRow).where(
            CustodyObligationRow.account_id == account_id
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
        stmt = select(CustodyObligationRow).where(
            CustodyObligationRow.account_id == account_id
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
                updated_at=now,
            )
            self._session.add(row)
        else:
            row.period = period
            row.status = status
            row.outstanding = Decimal(str(outstanding))
            row.total_fee = Decimal(str(total_fee))
            row.updated_at = now
        await self._session.flush()
        return _obligation_from_row(row)
