"""Use-case de listado de entradas de ledger."""

from bolsa_domain.entities.account import LedgerEntry
from bolsa_infrastructure.database.repositories.ledger_repository import SqlAlchemyLedgerRepository


class ListLedgerEntries:
    """Lista Ledger Entries."""
    def __init__(self, ledger_repo: SqlAlchemyLedgerRepository) -> None:
        self._ledger_repo = ledger_repo

    async def execute(
        self,
        account_id: str,
        *,
        limit: int = 50,
        offset: int = 0,
        portfolio_id: str | None = None,
    ) -> list[LedgerEntry]:
        return await self._ledger_repo.list_for_account(
            account_id,
            limit=limit,
            offset=offset,
            portfolio_id=portfolio_id,
        )
