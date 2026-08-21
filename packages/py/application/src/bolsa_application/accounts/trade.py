"""Use-case de ejecución de trades."""

from bolsa_domain.account_settings import calculate_trade_fees, settings_from_dict
from bolsa_domain.entities.portfolio import TradeResult
from bolsa_domain.errors import IdempotencyKeyExists
from bolsa_infrastructure.database.repositories.account_repository import (
    SqlAlchemyAccountRepository,
)
from bolsa_infrastructure.database.repositories.ledger_repository import SqlAlchemyLedgerRepository
from bolsa_infrastructure.database.repositories.portfolio_repository import (
    SqlAlchemyPortfolioRepository,
)

from .idempotency import _assert_trade_payload_matches


class ExecuteTrade:
    """Ejecuta Trade."""
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
        *,
        instrument_id: str,
        trade_type: str,
        quantity: float,
        price: float,
        account_id: str | None = None,
        portfolio_id: str | None = None,
        idempotency_key: str,
    ) -> TradeResult:
        """Ejecuta un trade sobre la cuenta/cartera resuelta por el scope.

        R-11 C2/C3: ``idempotency_key`` obligatoria (str 16-128, sin whitespace) y
        precisión `Decimal` íntegra hasta el borde del wire; el float solo aparece al
        invocar repo/ledger.
        """
        scope = await self._account_repo.resolve_scope(account_id, portfolio_id)
        # M4: doble POST con la misma idempotency_key → una sola transacción.
        # Devuelve la transacción original (misma shape) con un summary fresco, sin duplicar.
        if idempotency_key:
            existing = await self._portfolio_repo.find_transaction_by_idempotency(
                scope.legacy_portfolio_id,
                idempotency_key,
            )
            if existing is not None:
                _assert_trade_payload_matches(
                    existing,
                    instrument_id=instrument_id,
                    trade_type=trade_type,
                    quantity=quantity,
                    price=price,
                    idempotency_key=idempotency_key,
                )
                summary = await self._portfolio_repo.get_summary(scope.legacy_portfolio_id)
                return TradeResult(transaction=existing, summary=summary)
        settings = scope.account.settings or settings_from_dict(None)
        from decimal import Decimal

        # R-11 C3 (R-10.8): notional se calcula en Decimal. calculate_trade_fees y
        # execute_trade ya operan internamente en Decimal; aquí se evita el salto
        # Decimal→float→Decimal en la aritmética del use-case. La conversión a float
        # queda solo en el borde al invocar repo/ledger (que re-hacen Decimal).
        notional = Decimal(str(quantity)) * Decimal(str(price))
        fees = calculate_trade_fees(
            float(notional),
            trade_type,  # type: ignore[arg-type]
            settings,
            currency=scope.account.currency,
        )
        # EXEC-B-CONC / R-10 F3: NO leer cash PRE-lock. execute_trade ya serializa con
        # with_for_update y el summary devuelto es cash POST notional+fee (misma sesión).
        # Derivar balance_after desde ese cash post-lock evita la cadena B rota bajo
        # ExecuteTrade concurrente (cash_before desfasado) sin cambiar TradeResult.
        try:
            result = await self._portfolio_repo.execute_trade(
                instrument_id=instrument_id,
                trade_type=trade_type,  # type: ignore[arg-type]
                quantity=quantity,
                price=price,
                legacy_portfolio_id=scope.legacy_portfolio_id,
                fee_amount=fees.total,
                idempotency_key=idempotency_key,
            )
        except IdempotencyKeyExists:
            # R-8A/P0-B: otro request con LA MISMA idempotency_key ganó la carrera y ya
            # grabó la transacción (el repo revertió este intento con un savepoint).
            # Rejugamos el trade original con un summary fresco, sin append_trade/fee.
            existing = await self._portfolio_repo.find_transaction_by_idempotency(
                scope.legacy_portfolio_id,
                idempotency_key,
            )
            if existing is None:
                raise
            _assert_trade_payload_matches(
                existing,
                instrument_id=instrument_id,
                trade_type=trade_type,
                quantity=quantity,
                price=price,
                idempotency_key=idempotency_key,
            )
            summary = await self._portfolio_repo.get_summary(scope.legacy_portfolio_id)
            return TradeResult(transaction=existing, summary=summary)
        amount = (
            -Decimal(str(result.transaction.total))
            if trade_type == "buy"
            else Decimal(str(result.transaction.total))
        )
        # R-10 F3: balance_after SECUENCIAL por fila, en Decimal (R-11 C3).
        #   fee:   cash final post notional+fee (= summary.portfolio.cash post-lock).
        #   trade: cash tras SOLO el notional = fee_balance + abs(fees)
        #          (fees.total==0 → trade_balance == fee_balance; skip append_fee abajo).
        # Semántica invariante: balance_after[n] == balance_after[n-1] + amount[n].
        fee_balance = Decimal(str(result.summary.portfolio.cash))
        trade_balance = fee_balance + Decimal(str(abs(fees.total)))
        await self._ledger_repo.append_trade(
            account_id=scope.account.id,
            portfolio_id=scope.portfolio.id,
            entry_type=trade_type,
            amount=float(amount),
            currency=scope.account.currency,
            balance_after=float(trade_balance),
            instrument_id=instrument_id,
            quantity=quantity,
            price=price,
            reference_id=result.transaction.id,
        )
        if fees.total > 0:
            fee_parts = []
            if fees.commission > 0:
                fee_parts.append(f"comisión {fees.commission:.2f}")
            if fees.vat_on_commission > 0:
                fee_parts.append(f"IVA {fees.vat_on_commission:.2f}")
            if fees.stamp_duty > 0:
                fee_parts.append(f"transmisiones {fees.stamp_duty:.2f}")
            description = " · ".join(fee_parts) if fee_parts else "Comisiones de operación"
            await self._ledger_repo.append_fee(
                account_id=scope.account.id,
                portfolio_id=scope.portfolio.id,
                amount=fees.total,
                currency=scope.account.currency,
                balance_after=float(fee_balance),
                reference_id=result.transaction.id,
                description=description,
            )
        await self._account_repo.touch_activity(scope.account.id)
        return result
