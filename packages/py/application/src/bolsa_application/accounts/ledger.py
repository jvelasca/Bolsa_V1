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

    async def total_trade_fees(self, account_id: str) -> float:
        """Σ de comisiones de operaciones de la cuenta (todo el histórico).

        P1-03 — la página de `execute()` NO permite calcular el acumulado: sumar
        las filas `fee` devueltas subestima el coste en cuanto la cuenta supera
        `limit` movimientos. El agregado se delega en el repositorio, que ya
        excluye la custodia (M-4/T-M5).
        """
        return float(await self._ledger_repo.total_fees_for_account(account_id))
