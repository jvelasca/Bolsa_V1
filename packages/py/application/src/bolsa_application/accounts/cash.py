"""Use-cases de depósito y retiro de efectivo."""

from bolsa_domain.entities.account import CashMovementResult
from bolsa_domain.errors import IdempotencyKeyExists
from bolsa_infrastructure.database.repositories.account_repository import (
    SqlAlchemyAccountRepository,
)
from bolsa_infrastructure.database.repositories.ledger_repository import SqlAlchemyLedgerRepository
from bolsa_infrastructure.database.repositories.portfolio_repository import (
    SqlAlchemyPortfolioRepository,
)

from .idempotency import (
    _assert_cash_payload_matches,
    _cash_movement_result_from_entry,
    _idempotent_savepoint,
)


class DepositCashToAccount:
    """Ingresa efectivo en cuenta."""
    def __init__(
        self,
        account_repo: SqlAlchemyAccountRepository,
        portfolio_repo: SqlAlchemyPortfolioRepository,
        ledger_repo: SqlAlchemyLedgerRepository,
    ) -> None:
        self._account_repo = account_repo
        self._portfolio_repo = portfolio_repo
        self._ledger_repo = ledger_repo

    async def execute(
        self,
        account_id: str,
        *,
        amount: float,
        note: str | None = None,
        idempotency_key: str,
    ) -> CashMovementResult:
        if amount <= 0:
            raise ValueError("El importe debe ser mayor que cero")
        scope = await self._account_repo.resolve_scope(account_id)
        # A-2: idempotencia — un retry con la misma idempotency_key no re-mueve
        # efectivo; rejuega el movimiento original desde el ledger. Aislado por
        # cuenta y por type (deposit) para coincidir con el UNIQUE por-cuenta+type.
        if idempotency_key:
            existing = await self._ledger_repo.find_cash_movement_by_reference(
                "external",
                idempotency_key,
                account_id=scope.account.id,
                type="deposit",
            )
            if existing is not None:
                _assert_cash_payload_matches(
                    existing,
                    amount=amount,
                    note=note,
                    storage_sign=1,
                    idempotency_key=idempotency_key,
                )
                return _cash_movement_result_from_entry(existing, "external_deposit")
        movement_id = idempotency_key
        session = getattr(self._ledger_repo, "session", None)
        try:
            async with _idempotent_savepoint(session):
                balance_after = await self._portfolio_repo.add_cash(
                    scope.legacy_portfolio_id, amount
                )
                description = note or "Depósito externo (simulado)"
                entry = await self._ledger_repo.append_cash_movement(
                    account_id=account_id,
                    portfolio_id=scope.portfolio.id,
                    entry_type="deposit",
                    amount=amount,
                    currency=scope.account.currency,
                    balance_after=balance_after,
                    reference_id=movement_id,
                    reference_type="external",
                    description=description,
                )
                await self._account_repo.touch_activity(account_id)
        except IdempotencyKeyExists:
            # R-8A/P0-B: otro request con la misma idempotency_key ganó la carrera y ya
            # grabó el depósito; el savepoint revirtió este intento (incl. add_cash).
            # Rejugamos el movimiento original para devolver la misma shape.
            existing = await self._ledger_repo.find_cash_movement_by_reference(
                "external",
                idempotency_key,
                account_id=scope.account.id,
                type="deposit",
            )
            if existing is None:
                raise
            _assert_cash_payload_matches(
                existing,
                amount=amount,
                note=note,
                storage_sign=1,
                idempotency_key=idempotency_key,
            )
            return _cash_movement_result_from_entry(existing, "external_deposit")
        return CashMovementResult(
            id=movement_id,
            account_id=account_id,
            portfolio_id=scope.portfolio.id,
            kind="external_deposit",
            amount=amount,
            currency=scope.account.currency,
            balance_after=balance_after,
            executed_at=entry.executed_at,
            description=description,
        )


class WithdrawCashFromAccount:
    """Retira efectivo de cuenta."""
    def __init__(
        self,
        account_repo: SqlAlchemyAccountRepository,
        portfolio_repo: SqlAlchemyPortfolioRepository,
        ledger_repo: SqlAlchemyLedgerRepository,
    ) -> None:
        self._account_repo = account_repo
        self._portfolio_repo = portfolio_repo
        self._ledger_repo = ledger_repo

    async def execute(
        self,
        account_id: str,
        *,
        amount: float,
        note: str | None = None,
        idempotency_key: str,
    ) -> CashMovementResult:
        if amount <= 0:
            raise ValueError("El importe debe ser mayor que cero")
        scope = await self._account_repo.resolve_scope(account_id)
        # A-2: idempotencia — un retry con la misma idempotency_key no re-mueve
        # efectivo; rejuega el movimiento original desde el ledger (antes de validar
        # saldo actual, que ya se consumió en la ejecución original). Aislado por
        # cuenta y por type (withdrawal) para coincidir con el UNIQUE por-cuenta+type.
        if idempotency_key:
            existing = await self._ledger_repo.find_cash_movement_by_reference(
                "external",
                idempotency_key,
                account_id=scope.account.id,
                type="withdrawal",
            )
            if existing is not None:
                _assert_cash_payload_matches(
                    existing,
                    amount=amount,
                    note=note,
                    storage_sign=-1,
                    idempotency_key=idempotency_key,
                )
                return _cash_movement_result_from_entry(existing, "external_withdrawal")
        summary = await self._portfolio_repo.get_summary(scope.legacy_portfolio_id)
        if summary.portfolio.cash < amount:
            raise ValueError(
                f"Efectivo insuficiente. Disponible: {summary.portfolio.cash:.2f} {scope.account.currency}",
            )
        movement_id = idempotency_key
        session = getattr(self._ledger_repo, "session", None)
        try:
            async with _idempotent_savepoint(session):
                balance_after = await self._portfolio_repo.deduct_cash(
                    scope.legacy_portfolio_id, amount
                )
                description = note or "Retirada externa (simulada)"
                entry = await self._ledger_repo.append_cash_movement(
                    account_id=account_id,
                    portfolio_id=scope.portfolio.id,
                    entry_type="withdrawal",
                    amount=-amount,
                    currency=scope.account.currency,
                    balance_after=balance_after,
                    reference_id=movement_id,
                    reference_type="external",
                    description=description,
                )
                await self._account_repo.touch_activity(account_id)
        except IdempotencyKeyExists:
            # R-8A/P0-B: carrera de idempotencia perdida → el savepoint revirtió este
            # intento (incl. deduct_cash); rejugamos la retirada original.
            existing = await self._ledger_repo.find_cash_movement_by_reference(
                "external",
                idempotency_key,
                account_id=scope.account.id,
                type="withdrawal",
            )
            if existing is None:
                raise
            _assert_cash_payload_matches(
                existing,
                amount=amount,
                note=note,
                storage_sign=-1,
                idempotency_key=idempotency_key,
            )
            return _cash_movement_result_from_entry(existing, "external_withdrawal")
        return CashMovementResult(
            id=movement_id,
            account_id=account_id,
            portfolio_id=scope.portfolio.id,
            kind="external_withdrawal",
            amount=-amount,
            currency=scope.account.currency,
            balance_after=balance_after,
            executed_at=entry.executed_at,
            description=description,
        )
