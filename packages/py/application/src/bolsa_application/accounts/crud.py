"""Use-cases CRUD de cuentas DEMO/trading."""

from bolsa_domain.account_settings import AccountSettings
from bolsa_domain.entities.account import InvestmentAccount
from bolsa_infrastructure.database.repositories.account_repository import (
    SqlAlchemyAccountRepository,
)


class ListAccounts:
    """Lista Accounts."""
    def __init__(self, account_repo: SqlAlchemyAccountRepository) -> None:
        self._account_repo = account_repo

    async def execute(self, account_type: str | None = None) -> list[InvestmentAccount]:
        return await self._account_repo.list_accounts(account_type=account_type)


class CreateSimulatedAccount:
    """Crea Simulated Account."""
    def __init__(self, account_repo: SqlAlchemyAccountRepository) -> None:
        self._account_repo = account_repo

    async def execute(
        self,
        *,
        name: str,
        description: str | None = None,
        currency: str = "EUR",
        base_currency: str | None = None,
        initial_deposit: float = 100_000.0,
        leverage: float = 1.0,
        margin_call_level_pct: float | None = 100.0,
        portfolio_name: str | None = None,
        portfolio_description: str | None = None,
        strategy_tag: str | None = "core",
        settings: AccountSettings | None = None,
        commission_preset_id: str | None = None,
    ) -> InvestmentAccount:
        scope = await self._account_repo.create_simulated_account(
            name=name,
            description=description,
            currency=currency,
            base_currency=base_currency,
            initial_deposit=initial_deposit,
            leverage=leverage,
            margin_call_level_pct=margin_call_level_pct,
            portfolio_name=portfolio_name,
            portfolio_description=portfolio_description,
            strategy_tag=strategy_tag,
            settings=settings,
            commission_preset_id=commission_preset_id,
        )
        return scope.account


class UpdateAccountSettings:
    """Actualiza Account Settings."""
    def __init__(self, account_repo: SqlAlchemyAccountRepository) -> None:
        self._account_repo = account_repo

    async def execute(self, account_id: str, settings: AccountSettings) -> InvestmentAccount:
        return await self._account_repo.update_settings(account_id, settings)


class GetAccount:
    """Obtiene Account."""
    def __init__(self, account_repo: SqlAlchemyAccountRepository) -> None:
        self._account_repo = account_repo

    async def execute(self, account_id: str) -> InvestmentAccount:
        return await self._account_repo.get_account(account_id)


class UpdateAccount:
    """Actualiza Account."""
    def __init__(self, account_repo: SqlAlchemyAccountRepository) -> None:
        self._account_repo = account_repo

    async def execute(
        self,
        account_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
    ) -> InvestmentAccount:
        return await self._account_repo.update_account(
            account_id,
            name=name,
            description=description,
        )


class SetDefaultAccount:
    """Establece Default Account."""
    def __init__(self, account_repo: SqlAlchemyAccountRepository) -> None:
        self._account_repo = account_repo

    async def execute(self, account_id: str) -> InvestmentAccount:
        return await self._account_repo.set_default_account(account_id)


class CloseAccount:
    """Cierra Account."""
    def __init__(self, account_repo: SqlAlchemyAccountRepository) -> None:
        self._account_repo = account_repo

    async def execute(self, account_id: str) -> InvestmentAccount:
        return await self._account_repo.close_account(account_id)


class DeleteAccount:
    """Elimina Account."""
    def __init__(self, account_repo: SqlAlchemyAccountRepository) -> None:
        self._account_repo = account_repo

    async def execute(self, account_id: str) -> None:
        await self._account_repo.delete_simulated_account(account_id)
