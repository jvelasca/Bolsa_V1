from bolsa_infrastructure.database.repositories.account_repository import SqlAlchemyAccountRepository
from bolsa_infrastructure.database.repositories.pending_order_repository import (
    SqlAlchemyPendingOrderRepository,
)


class ListPendingOrders:
    def __init__(
        self,
        repo: SqlAlchemyPendingOrderRepository,
        account_repo: SqlAlchemyAccountRepository,
    ) -> None:
        self._repo = repo
        self._account_repo = account_repo

    async def execute(self, account_id: str | None = None):
        scope = await self._account_repo.resolve_scope(account_id)
        return await self._repo.list_for_account(scope.account.id)


class CreatePendingOrder:
    def __init__(
        self,
        repo: SqlAlchemyPendingOrderRepository,
        account_repo: SqlAlchemyAccountRepository,
    ) -> None:
        self._repo = repo
        self._account_repo = account_repo

    async def execute(
        self,
        *,
        instrument_id: str,
        symbol: str,
        side: str,
        order_type: str,
        quantity: float,
        limit_price: float,
        expiry_at,
        account_id: str | None = None,
    ):
        scope = await self._account_repo.resolve_scope(account_id)
        return await self._repo.create(
            account_id=scope.account.id,
            instrument_id=instrument_id,
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            limit_price=limit_price,
            expiry_at=expiry_at,
        )


class DeletePendingOrder:
    def __init__(
        self,
        repo: SqlAlchemyPendingOrderRepository,
        account_repo: SqlAlchemyAccountRepository,
    ) -> None:
        self._repo = repo
        self._account_repo = account_repo

    async def execute(self, order_id: str, account_id: str | None = None) -> None:
        scope = await self._account_repo.resolve_scope(account_id)
        deleted = await self._repo.delete(order_id, account_id=scope.account.id)
        if not deleted:
            raise ValueError("Order not found")
