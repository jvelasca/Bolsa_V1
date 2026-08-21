"""Use-cases de resumen de cartera y listado de transacciones."""

from bolsa_domain.entities.portfolio import PortfolioSummary, Transaction
from bolsa_infrastructure.database.repositories.account_repository import (
    SqlAlchemyAccountRepository,
)
from bolsa_infrastructure.database.repositories.portfolio_repository import (
    SqlAlchemyPortfolioRepository,
)


class GetPortfolioSummary:
    """Obtiene Portfolio Summary."""
    def __init__(
        self,
        account_repo: SqlAlchemyAccountRepository,
        portfolio_repo: SqlAlchemyPortfolioRepository,
    ) -> None:
        self._account_repo = account_repo
        self._portfolio_repo = portfolio_repo

    async def execute(
        self,
        account_id: str | None = None,
        portfolio_id: str | None = None,
    ) -> PortfolioSummary:
        scope = await self._account_repo.resolve_scope(account_id, portfolio_id)
        return await self._portfolio_repo.get_summary(scope.legacy_portfolio_id)


class ListTransactions:
    """Lista Transactions."""
    def __init__(
        self,
        account_repo: SqlAlchemyAccountRepository,
        portfolio_repo: SqlAlchemyPortfolioRepository,
    ) -> None:
        self._account_repo = account_repo
        self._portfolio_repo = portfolio_repo

    async def execute(
        self,
        limit: int = 50,
        account_id: str | None = None,
        portfolio_id: str | None = None,
    ) -> list[Transaction]:
        scope = await self._account_repo.resolve_scope(account_id, portfolio_id)
        return await self._portfolio_repo.list_transactions(
            limit=limit,
            legacy_portfolio_id=scope.legacy_portfolio_id,
        )
