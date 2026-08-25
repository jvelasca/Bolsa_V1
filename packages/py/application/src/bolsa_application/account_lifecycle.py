"""Ciclo de vida de cuentas demo: listar cerradas y purga en lote (Configuración → BD)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_infrastructure.database.models import (
    InvestmentAccountRow,
    InvestmentPortfolioRow,
    LedgerEntryRow,
    PendingOrderRow,
    PositionRow,
    TransactionRow,
)
from bolsa_infrastructure.database.repositories.account_repository import (
    SqlAlchemyAccountRepository,
)


@dataclass(frozen=True, slots=True)
class ClosedSimulatedAccountRow:
    """Cierra Simulated Account Row."""
    id: str
    name: str
    currency: str
    updated_at: datetime
    ledger_entry_count: int
    portfolio_count: int
    position_count: int
    transaction_count: int
    pending_order_count: int


@dataclass(frozen=True, slots=True)
class ListClosedSimulatedAccountsResult:
    """Lista Closed Simulated Accounts Result."""
    accounts: tuple[ClosedSimulatedAccountRow, ...]
    total_ledger_entries: int


@dataclass(frozen=True, slots=True)
class PurgeClosedAccountSkip:
    """Purga Closed Account Skip."""
    account_id: str
    name: str
    reasons: tuple[str, ...]


class ListClosedSimulatedAccounts:
    """Lista Closed Simulated Accounts."""
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(self, *, limit: int = 100) -> ListClosedSimulatedAccountsResult:
        stmt = (
            select(InvestmentAccountRow)
            .where(
                InvestmentAccountRow.type == "simulated",
                InvestmentAccountRow.status == "closed",
            )
            .order_by(InvestmentAccountRow.updated_at.desc())
            .limit(limit)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        accounts: list[ClosedSimulatedAccountRow] = []
        total_ledger = 0
        for row in rows:
            preview = await self._preview_counts(row.id)
            accounts.append(
                ClosedSimulatedAccountRow(
                    id=row.id,
                    name=row.name,
                    currency=row.currency,
                    updated_at=row.updated_at,
                    ledger_entry_count=preview["ledger"],
                    portfolio_count=preview["portfolios"],
                    position_count=preview["positions"],
                    transaction_count=preview["transactions"],
                    pending_order_count=preview["orders"],
                )
            )
            total_ledger += preview["ledger"]
        return ListClosedSimulatedAccountsResult(
            accounts=tuple(accounts),
            total_ledger_entries=total_ledger,
        )

    async def _preview_counts(self, account_id: str) -> dict[str, int]:
        ledger = int(
            (
                await self._session.execute(
                    select(func.count()).select_from(LedgerEntryRow).where(
                        LedgerEntryRow.account_id == account_id
                    )
                )
            ).scalar_one()
        )
        portfolios = int(
            (
                await self._session.execute(
                    select(func.count()).select_from(InvestmentPortfolioRow).where(
                        InvestmentPortfolioRow.account_id == account_id
                    )
                )
            ).scalar_one()
        )
        orders = int(
            (
                await self._session.execute(
                    select(func.count()).select_from(PendingOrderRow).where(
                        PendingOrderRow.account_id == account_id
                    )
                )
            ).scalar_one()
        )

        legacy_ids = (
            await self._session.execute(
                select(InvestmentPortfolioRow.legacy_portfolio_id).where(
                    InvestmentPortfolioRow.account_id == account_id,
                    InvestmentPortfolioRow.legacy_portfolio_id.is_not(None),
                )
            )
        ).scalars().all()
        positions = 0
        transactions = 0
        for legacy_id in legacy_ids:
            if not legacy_id:
                continue
            positions += int(
                (
                    await self._session.execute(
                        select(func.count()).select_from(PositionRow).where(
                            PositionRow.portfolio_id == legacy_id
                        )
                    )
                ).scalar_one()
            )
            transactions += int(
                (
                    await self._session.execute(
                        select(func.count()).select_from(TransactionRow).where(
                            TransactionRow.portfolio_id == legacy_id
                        )
                    )
                ).scalar_one()
            )

        return {
            "ledger": ledger,
            "portfolios": portfolios,
            "orders": orders,
            "positions": positions,
            "transactions": transactions,
        }


class PurgeClosedSimulatedAccounts:
    """Elimina demos ya cerradas (misma regla que DELETE /accounts/{id})."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._accounts = SqlAlchemyAccountRepository(session)

    async def execute(self, *, limit: int = 50) -> dict[str, object]:
        listed = await ListClosedSimulatedAccounts(self._session).execute(limit=limit)
        purged: list[str] = []
        skipped: list[dict[str, object]] = []
        for account in listed.accounts:
            try:
                await self._accounts.delete_simulated_account(account.id)
                purged.append(account.id)
            except ValueError as exc:
                skipped.append(
                    {
                        "accountId": account.id,
                        "name": account.name,
                        "reasons": [str(exc)],
                    }
                )
        return {
            "purgedIds": purged,
            "skipped": skipped,
            "scanned": len(listed.accounts),
        }
