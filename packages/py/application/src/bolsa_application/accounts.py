"""Use-cases de cuentas DEMO/trading, ledger y trades."""

from dataclasses import replace
from datetime import UTC, datetime

from bolsa_application.risk_runtime import claim_custody_charge, release_custody_charge
from bolsa_domain.account_settings import calculate_trade_fees, settings_from_dict
from bolsa_domain.entities.account import (
    AccountSummary,
    CashMovementResult,
    InvestmentAccount,
    LedgerEntry,
)
from bolsa_domain.entities.portfolio import PortfolioSummary, TradeResult, Transaction
from bolsa_domain.tax_report import (
    TaxReportTransaction,
    build_tax_report,
    fiscal_year_range,
    map_ledger_fees_to_transactions,
    open_positions_with_fee_basis,
)
from bolsa_infrastructure.database.repositories.account_repository import (
    SqlAlchemyAccountRepository,
)
from bolsa_infrastructure.database.repositories.ledger_repository import SqlAlchemyLedgerRepository
from bolsa_infrastructure.database.repositories.portfolio_repository import (
    SqlAlchemyPortfolioRepository,
)
from bolsa_infrastructure.ids import new_id


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
        settings=None,
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

    async def execute(self, account_id: str, settings) -> InvestmentAccount:
        return await self._account_repo.update_settings(account_id, settings)


class GetAccount:
    """Obtiene Account."""
    def __init__(self, account_repo: SqlAlchemyAccountRepository) -> None:
        self._account_repo = account_repo

    async def execute(self, account_id: str) -> InvestmentAccount:
        return await self._account_repo.get_account(account_id)


def _account_summary_from_portfolio(
    *,
    account: InvestmentAccount,
    default_portfolio,
    portfolio_summary: PortfolioSummary,
) -> AccountSummary:
    cash = portfolio_summary.portfolio.cash
    # M-6: margen canónico (inversión bajo apalancamiento). Definición:
    # `margin_level_pct = equity / margin_used * 100` (investment-platform.md:46).
    # `margin_used = Σ market_value / leverage` (decisión de usuario). Solo las
    # posiciones con `market_value` observable aportan inversión bajo margen; las
    # posiciones sin precio (market_value=None) NO cuentan, consistentes con
    # total_market_value/total_equity (M-1). Guard `>0`: si leverage fuera 0
    # (fail-closed), no dividir por cero. Sin posiciones (o todas sin precio)
    # → margin_used=0 y no aplica margen (margin_level_pct=None).
    margin_used = (
        sum(mv for mv in (pos.market_value for pos in portfolio_summary.positions) if mv is not None)
        / account.leverage
        if account.leverage > 0
        else 0.0
    )
    equity = portfolio_summary.total_equity
    free_margin = equity - margin_used
    margin_level_pct = (equity / margin_used * 100) if margin_used > 0 else None
    return AccountSummary(
        account=account,
        default_portfolio=default_portfolio,
        cash=cash,
        total_market_value=portfolio_summary.total_market_value,
        total_cost=portfolio_summary.total_cost,
        total_unrealized_pnl=portfolio_summary.total_unrealized_pnl,
        total_equity=equity,
        margin_used=margin_used,
        free_margin=free_margin,
        margin_level_pct=margin_level_pct,
        positions_count=len(portfolio_summary.positions),
    )


class GetAccountSummary:
    """Obtiene Account Summary."""
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
        account_id: str | None = None,
        portfolio_id: str | None = None,
    ) -> AccountSummary:
        scope = await self._account_repo.resolve_scope(account_id, portfolio_id)
        await ApplyCustodyFees(
            self._account_repo,
            self._portfolio_repo,
            self._ledger_repo,
        ).execute(scope)
        scope = await self._account_repo.resolve_scope(account_id, portfolio_id)
        summary = await self._portfolio_repo.get_summary(scope.legacy_portfolio_id)
        return _account_summary_from_portfolio(
            account=scope.account,
            default_portfolio=scope.portfolio,
            portfolio_summary=summary,
        )


class ListAccountSummaries:
    """Hub listing: one pass, no custody side-effects (use GetAccountSummary for that)."""

    def __init__(
        self,
        account_repo: SqlAlchemyAccountRepository,
        portfolio_repo: SqlAlchemyPortfolioRepository,
    ) -> None:
        self._account_repo = account_repo
        self._portfolio_repo = portfolio_repo

    async def execute(self, account_type: str | None = None) -> list[AccountSummary]:
        accounts = await self._account_repo.list_accounts(account_type=account_type)
        items: list[AccountSummary] = []
        for account in accounts:
            scope = await self._account_repo.resolve_scope(account.id, None)
            summary = await self._portfolio_repo.get_summary(scope.legacy_portfolio_id)
            items.append(
                _account_summary_from_portfolio(
                    account=scope.account,
                    default_portfolio=scope.portfolio,
                    portfolio_summary=summary,
                )
            )
        return items


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


def _cash_movement_result_from_entry(entry: LedgerEntry, kind: str) -> CashMovementResult:
    """Reconstruye un CashMovementResult desde la entrada de ledger original.

    Se usa para rejugar un movimento ya persistido (idempotencia) manteniendo la
    misma shape (id = reference_id de la entrada, que es la idempotency_key).
    """
    return CashMovementResult(
        id=entry.reference_id or entry.id,
        account_id=entry.account_id,
        portfolio_id=entry.portfolio_id or "",
        kind=kind,
        amount=entry.amount,
        currency=entry.currency,
        balance_after=entry.balance_after,
        executed_at=entry.executed_at,
        description=entry.description,
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
        idempotency_key: str | None = None,
    ) -> CashMovementResult:
        if amount <= 0:
            raise ValueError("El importe debe ser mayor que cero")
        scope = await self._account_repo.resolve_scope(account_id)
        # A-2: idempotencia — un retry con la misma idempotency_key no re-mueve
        # efectivo; rejuega el movimiento original desde el ledger.
        if idempotency_key:
            existing = await self._ledger_repo.find_cash_movement_by_reference(
                "external",
                idempotency_key,
            )
            if existing is not None:
                return _cash_movement_result_from_entry(existing, "external_deposit")
        movement_id = idempotency_key or new_id()
        balance_after = await self._portfolio_repo.add_cash(scope.legacy_portfolio_id, amount)
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
        idempotency_key: str | None = None,
    ) -> CashMovementResult:
        if amount <= 0:
            raise ValueError("El importe debe ser mayor que cero")
        scope = await self._account_repo.resolve_scope(account_id)
        # A-2: idempotencia — un retry con la misma idempotency_key no re-mueve
        # efectivo; rejuega el movimiento original desde el ledger (antes de validar
        # saldo actual, que ya se consumió en la ejecución original).
        if idempotency_key:
            existing = await self._ledger_repo.find_cash_movement_by_reference(
                "external",
                idempotency_key,
            )
            if existing is not None:
                return _cash_movement_result_from_entry(existing, "external_withdrawal")
        summary = await self._portfolio_repo.get_summary(scope.legacy_portfolio_id)
        if summary.portfolio.cash < amount:
            raise ValueError(
                f"Efectivo insuficiente. Disponible: {summary.portfolio.cash:.2f} {scope.account.currency}",
            )
        movement_id = idempotency_key or new_id()
        balance_after = await self._portfolio_repo.deduct_cash(scope.legacy_portfolio_id, amount)
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


class ApplyCustodyFees:
    """Aplica Custody Fees."""
    CUSTODY_INTERVAL_DAYS = 365

    def __init__(
        self,
        account_repo: SqlAlchemyAccountRepository,
        portfolio_repo: SqlAlchemyPortfolioRepository,
        ledger_repo: SqlAlchemyLedgerRepository,
    ) -> None:
        self._account_repo = account_repo
        self._portfolio_repo = portfolio_repo
        self._ledger_repo = ledger_repo

    async def execute(self, scope) -> bool:
        settings = scope.account.settings or settings_from_dict(None)
        pct = settings.commission.custody_annual_pct
        if pct is None or pct <= 0:
            return False

        now = datetime.now(UTC)
        period = now.strftime("%Y")

        # Dedup duradero vía ledger: si ya se cobró este periodo, no repetir.
        # (Consulta previa al claim: serializa la ventana concurrente abajo; este
        # guard se apoya en la fila ya persistida y sobrevive a reinicios.)
        last = await self._ledger_repo.last_custody_charge_at(scope.account.id)
        if last is not None:
            last_dt = last if last.tzinfo else last.replace(tzinfo=UTC)
            if (now - last_dt).days < self.CUSTODY_INTERVAL_DAYS:
                return False

        # Mutex atómico (SET NX) por cuenta+periodo: evita el doble cargo cuando
        # dos GET (summary/tax) entran a la vez y ambas superan el guard de arriba.
        claimed = await claim_custody_charge(scope.account.id, period)
        if not claimed:
            return False

        try:
            portfolios = await self._account_repo.list_portfolios(scope.account.id)
            total_equity = 0.0
            for portfolio in portfolios:
                if not portfolio.legacy_portfolio_id:
                    continue
                summary = await self._portfolio_repo.get_summary(portfolio.legacy_portfolio_id)
                total_equity += summary.total_equity
            if total_equity <= 0:
                await release_custody_charge(scope.account.id, period)
                return False

            fee_amount = total_equity * pct / 100
            charge_portfolio_id = scope.portfolio.id
            charge_legacy_id = scope.portfolio.legacy_portfolio_id
            if not charge_legacy_id:
                default = next((p for p in portfolios if p.is_default), portfolios[0])
                charge_portfolio_id = default.id
                charge_legacy_id = default.legacy_portfolio_id
            if not charge_legacy_id:
                await release_custody_charge(scope.account.id, period)
                return False

            # Custodia descuenta del cash de una única cartera el cargo calculado
            # sobre el patrimonio total (por definición el cargo puede superar el
            # cash disponible). allow_partial: True descarta lo que haya, de forma
            # explícita (nunca en silencio) y trazada en el ledger con el importe real.
            pre_summary = await self._portfolio_repo.get_summary(charge_legacy_id)
            cash_before = pre_summary.portfolio.cash
            balance_after = await self._portfolio_repo.deduct_cash(
                charge_legacy_id,
                fee_amount,
                allow_partial=True,
            )
            charged = cash_before - balance_after
            if charged < 0:
                charged = 0.0
            description = f"Custodia anual {pct:.2f} % · patrimonio {total_equity:.2f} €"
            if charged < fee_amount:
                description += (
                    f" · cargo parcial por saldo (aplicado {charged:.2f} € de {fee_amount:.2f} €)"
                )
            await self._ledger_repo.append_custody_fee(
                account_id=scope.account.id,
                portfolio_id=charge_portfolio_id,
                amount=charged,
                currency=scope.account.currency,
                balance_after=balance_after,
                reference_id=f"custody-{period}",
                description=description,
            )
            await self._account_repo.touch_activity(scope.account.id)
            # Tras el cargo persistido, el guard duradero (ledger) ya protege el
            # año; liberar el mutex para no bloquear reintentos de otros periodos.
            await release_custody_charge(scope.account.id, period)
            return True
        except Exception:
            await release_custody_charge(scope.account.id, period)
            raise


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
        idempotency_key: str | None = None,
    ) -> TradeResult:
        scope = await self._account_repo.resolve_scope(account_id, portfolio_id)
        # M4: doble POST con la misma idempotency_key → una sola transacción.
        # Devuelve la transacción original (misma shape) con un summary fresco, sin duplicar.
        if idempotency_key:
            existing = await self._portfolio_repo.find_transaction_by_idempotency(
                scope.legacy_portfolio_id,
                idempotency_key,
            )
            if existing is not None:
                summary = await self._portfolio_repo.get_summary(scope.legacy_portfolio_id)
                return TradeResult(transaction=existing, summary=summary)
        settings = scope.account.settings or settings_from_dict(None)
        from decimal import Decimal

        notional = float(Decimal(str(quantity)) * Decimal(str(price)))
        fees = calculate_trade_fees(
            notional,
            trade_type,  # type: ignore[arg-type]
            settings,
            currency=scope.account.currency,
        )
        result = await self._portfolio_repo.execute_trade(
            instrument_id=instrument_id,
            trade_type=trade_type,  # type: ignore[arg-type]
            quantity=quantity,
            price=price,
            legacy_portfolio_id=scope.legacy_portfolio_id,
            fee_amount=fees.total,
            idempotency_key=idempotency_key,
        )
        amount = -result.transaction.total if trade_type == "buy" else result.transaction.total
        # M3: balance_after = cash real grabado por el repo (ya incluye comisiones),
        # NO un recálculo manual que doble-contaría las fees.
        trade_balance = result.summary.portfolio.cash
        await self._ledger_repo.append_trade(
            account_id=scope.account.id,
            portfolio_id=scope.portfolio.id,
            entry_type=trade_type,
            amount=amount,
            currency=scope.account.currency,
            balance_after=trade_balance,
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
                balance_after=result.summary.portfolio.cash,
                reference_id=result.transaction.id,
                description=description,
            )
        await self._account_repo.touch_activity(scope.account.id)
        return result


class GetTaxReport:
    """Obtiene Tax Report."""
    def __init__(
        self,
        account_repo: SqlAlchemyAccountRepository,
        portfolio_repo: SqlAlchemyPortfolioRepository,
        ledger_repo: SqlAlchemyLedgerRepository,
    ) -> None:
        self._account_repo = account_repo
        self._portfolio_repo = portfolio_repo
        self._ledger_repo = ledger_repo

    async def execute(self, account_id: str, year: int):
        scope = await self._account_repo.resolve_scope(account_id)
        await ApplyCustodyFees(
            self._account_repo,
            self._portfolio_repo,
            self._ledger_repo,
        ).execute(scope)
        settings = scope.account.settings or settings_from_dict(None)
        tax = settings.tax

        portfolios = await self._account_repo.list_portfolios(account_id)
        # F-FIN-2: ejercicio fiscal [inicio, fin) — canonical en dominio (fiscal_year_range).
        # Las transacciones se cargan SOLO hasta el fin del ejercicio (incluye carry-in
        # de compras previas para FIFO/avg, excluye años futuros) SIN techo truncante
        # (antes limit=10000 cortaba las compras antiguas y rompía el cost basis).
        fiscal_start, fiscal_end = fiscal_year_range(year, tax.fiscal_year_start_month)
        transactions: list[Transaction] = []
        seen_ids: set[str] = set()
        for portfolio in portfolios:
            if not portfolio.legacy_portfolio_id:
                continue
            batch = await self._portfolio_repo.list_transactions(
                legacy_portfolio_id=portfolio.legacy_portfolio_id,
                limit=None,
                executed_before=fiscal_end,
            )
            for tx in batch:
                if tx.id not in seen_ids:
                    seen_ids.add(tx.id)
                    transactions.append(tx)
        transactions.sort(key=lambda tx: tx.executed_at)

        # F-AUD2/P2.1: el ledger del ejercicio fiscal se carga SIN techo físico.
        # Antes limit=10_000 podía cortar entradas de fees de un ejercicio grande
        # (rompiendo el mapeo fee->transacción). El filtro [fiscal_start, fiscal_end)
        # ya lo acota a ese ejercicio; total_fees_for_account por separado sin límite.
        ledger_entries = await self._ledger_repo.list_for_account(
            scope.account.id,
            limit=None,
            offset=0,
            executed_from=fiscal_start,
            executed_to=fiscal_end,
        )
        fees_by_tx = map_ledger_fees_to_transactions(ledger_entries)
        total_ledger_fees = await self._ledger_repo.total_fees_for_account(
            scope.account.id,
            executed_from=fiscal_start,
            executed_to=fiscal_end,
        )

        report_tx = [
            TaxReportTransaction(
                id=tx.id,
                type=tx.type,
                instrument_id=tx.instrument_id,
                symbol=tx.symbol,
                quantity=tx.quantity,
                price=tx.price,
                total=tx.total,
                executed_at=tx.executed_at,
            )
            for tx in transactions
        ]

        # M-3 (puente, decisión iv): la cara unrealized del report se deriva del residual
        # abierto con la MISMA semántica FIFO/avg que la cara realized (fee capitalizada),
        # en lugar de usar pos.quantity*pos.avg_cost (fee-excluida). storage/avg_cost de la
        # posición NO cambia; este "puente" con fee solo alimenta la cara fiscal del report.
        prices: dict[str, float] = {}
        live_quantities: dict[str, float] = {}
        for portfolio in portfolios:
            if not portfolio.legacy_portfolio_id:
                continue
            summary = await self._portfolio_repo.get_summary(portfolio.legacy_portfolio_id)
            for pos in summary.positions:
                live_quantities[pos.instrument_id] = pos.quantity
                if pos.last_price is not None:
                    prices[pos.instrument_id] = pos.last_price

        unrealized = open_positions_with_fee_basis(
            report_tx,
            method=tax.cost_basis_method,
            prices=prices,
            live_quantities=live_quantities,
        )

        report = build_tax_report(
            account_id=scope.account.id,
            currency=scope.account.currency,
            method=tax.cost_basis_method,
            jurisdiction=tax.jurisdiction,
            year=year,
            transactions=report_tx,
            fees_by_transaction_id=fees_by_tx,
            positions=unrealized,
            fiscal_year_start_month=tax.fiscal_year_start_month,
            capital_gains_tax_pct=tax.capital_gains_tax_pct,
            dividend_withholding_pct=tax.dividend_withholding_pct,
        )
        if total_ledger_fees > report.fees_paid_total:
            return replace(report, fees_paid_total=total_ledger_fees)
        return report
