"""Use case — R-10 F4b: job periódico de custodia sobre cuentas activas.

Mueve ``ApplyCustodyFees`` del path de lectura (mutaba en GET de summary/tax) a un
job programado del scheduler. El worker ``custody_job_worker`` invoca este use-case
en cada ciclo; aquí se agrega ``{scanned, applied_complete, pending, skipped}``.

Idempotencia: ``ApplyCustodyFees.execute`` ya devuelve ``False`` ante colisión de
UNIQUE/mutex (R-9 F3), si ya se cobró este periodo (guard duradero de ledger) o si
la custodia no aplica (fee 0 / equity<=0); el job tolera ``False`` y lo agrega como
``skipped`` — nunca error fatal. Un ``True`` cobra: la obligación/pendientes
quedan ``APPLIED`` (saldado) o queda algún ``PENDING`` (cash<fee o histórico).
Multi-periodo (R-11 C1 / R-10.6): se consultan las obligaciones PENDING de la
cuenta; si queda alguna → ``pending``, si no → ``applied_complete``.
"""

from __future__ import annotations

from typing import Any

from bolsa_infrastructure.database.repositories.account_repository import (
    SqlAlchemyAccountRepository,
)
from bolsa_infrastructure.database.repositories.custody_obligation_repository import (
    CustodyObligationRepository,
)
from bolsa_infrastructure.database.repositories.ledger_repository import SqlAlchemyLedgerRepository
from bolsa_infrastructure.database.repositories.portfolio_repository import (
    SqlAlchemyPortfolioRepository,
)

from bolsa_application.accounts import ApplyCustodyFees


class RunCustodyJob:
    """Ejecuta el job periódico de custodia sobre todas las cuentas activas."""

    def __init__(
        self,
        account_repo: SqlAlchemyAccountRepository,
        portfolio_repo: SqlAlchemyPortfolioRepository,
        ledger_repo: SqlAlchemyLedgerRepository,
        custody_obligation_repo: CustodyObligationRepository,
    ) -> None:
        self._account_repo = account_repo
        self._portfolio_repo = portfolio_repo
        self._ledger_repo = ledger_repo
        self._obligation_repo = custody_obligation_repo

    async def execute(self) -> dict[str, Any]:
        accounts = await self._account_repo.list_active_accounts(for_custody_job=True)
        applied_complete = 0
        pending = 0
        skipped = 0
        results: list[dict[str, Any]] = []

        for account in accounts:
            scope = await self._account_repo.resolve_scope(account.id, None)
            applied = await ApplyCustodyFees(
                self._account_repo,
                self._portfolio_repo,
                self._ledger_repo,
                custody_obligation_repo=self._obligation_repo,
            ).execute(scope)
            if not applied:
                # Idempotente: no aplica / ya cobrado / perdedor de carrera UNIQUE/mutex.
                skipped += 1
                results.append({"accountId": account.id, "outcome": "skipped"})
                continue
            # True == cobrado/saldado. Distinguir APPLIED vs PENDING por las
            # obligaciones persistidas (multi-periodo): si queda alguna PENDING (ya sea
            # el periodo actual con cash<fee o histórico no saldado) → pending; si no →
            # applied_complete.
            pendings = await self._obligation_repo.get_pending_by_account(account.id)
            if pendings:
                pending += 1
                results.append({"accountId": account.id, "outcome": "pending"})
            else:
                applied_complete += 1
                results.append({"accountId": account.id, "outcome": "applied"})

        return {
            "scanned": len(accounts),
            "applied_complete": applied_complete,
            "pending": pending,
            "skipped": skipped,
            "results": results,
        }
