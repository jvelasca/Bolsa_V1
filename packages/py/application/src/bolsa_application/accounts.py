"""Use-cases de cuentas DEMO/trading, ledger y trades."""

from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError

from bolsa_application.risk_runtime import claim_custody_charge, release_custody_charge
from bolsa_domain.account_settings import calculate_trade_fees, settings_from_dict
from bolsa_domain.entities.account import (
    AccountSummary,
    CashMovementResult,
    InvestmentAccount,
    LedgerEntry,
)
from bolsa_domain.entities.portfolio import PortfolioSummary, TradeResult, Transaction
from bolsa_domain.errors import IdempotencyKeyExists, IdempotencyKeyReused
from bolsa_domain.tax_report import (
    TaxReportTransaction,
    build_tax_report,
    fiscal_year_range,
    map_ledger_fees_to_transactions,
    open_positions_with_fee_basis,
)
from bolsa_infrastructure.database.db_errors import is_unique_violation
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


@asynccontextmanager
async def _idempotent_savepoint(session):
    """Abre un SAVEPOINT si hay una sesión real; no-op en tests con fakes.

    R-8A/P0-B: permite revertir SOLO el intento de escritura del perdedor de una
    carrera de idempotencia (``add_cash``/``deduct_cash`` + ``append_cash_movement``)
    sin descartar el estado de la transacción de la request. En los tests con repos
    fake (que no exponen ``session``) se ejecuta como no-op y el patrón sigue
    comportándose igual que antes (sin colisiones reales).
    """
    if session is None:
        yield
        return
    async with session.begin_nested():
        yield


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
        # R-10 F4b: GET de solo lectura — la custodia se aplica en el job periódico
        # (RunCustodyJob), nunca muta el estado por side-effect en lectura.
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


def _cash_payload_matches(
    entry: LedgerEntry,
    *,
    amount: float,
    note: str | None,
    storage_sign: int,
) -> bool:
    """Compara el payload entrante de un deposit/withdraw contra lo persistido.

    El valor financiero crítico es el ``amount``. La entrada de ledger guarda el
    deposit con el importe positivo y el withdraw con su signo (negativo); la
    comparación aplica ``storage_sign`` (1 para deposit, -1 para withdraw) para
    alinear el entrante con el signo de almacenamiento. Se normaliza a ``Decimal``
    (con ``Decimal(str(x))``) y se compara por igualdad exacta a escala financiera
    de 6 decimales (Numeric(18,6)); no se usa ninguna tolerancia. ``note``/description
    se comparan exactamente sólo si el entrante aporta nota. Si algún campo
    difiere, la key se está reutilizando con un payload distinto → conflicto.
    """
    from decimal import Decimal

    amount_matches = Decimal(str(entry.amount)).quantize(Decimal("0.000001")) == Decimal(str(amount * storage_sign)).quantize(Decimal("0.000001"))
    if not amount_matches:
        return False
    if note is not None:
        return note == entry.description
    return True


def _assert_cash_payload_matches(
    entry: LedgerEntry,
    *,
    amount: float,
    note: str | None,
    storage_sign: int,
    idempotency_key: str,
) -> None:
    if not _cash_payload_matches(
        entry,
        amount=amount,
        note=note,
        storage_sign=storage_sign,
    ):
        raise IdempotencyKeyReused(idempotency_key)


def _trade_payload_matches(existing: Transaction, *, instrument_id: str, trade_type: str, quantity: float, price: float) -> bool:
    """Compara el payload entrante de un trade contra la transacción persistida.

    Coincide si `instrument_id`, `trade_type`, `quantity` y `price` son iguales.
    Se normaliza a ``Decimal`` (con ``Decimal(str(x))``) y se compara quantity/price
    por igualdad exacta a escala financiera de 6 decimales (Numeric(18,6)); no se
    usa ninguna tolerancia. ``total`` es derivable (quantity*price + fees) y no se
    compara directamente.
    """
    from decimal import Decimal

    if existing.instrument_id != instrument_id:
        return False
    if existing.type != trade_type:
        return False
    if Decimal(str(existing.quantity)).quantize(Decimal("0.000001")) != Decimal(str(quantity)).quantize(Decimal("0.000001")):
        return False
    if Decimal(str(existing.price)).quantize(Decimal("0.000001")) != Decimal(str(price)).quantize(Decimal("0.000001")):
        return False
    return True


def _assert_trade_payload_matches(existing: Transaction, *, instrument_id: str, trade_type: str, quantity: float, price: float, idempotency_key: str) -> None:
    if not _trade_payload_matches(
        existing,
        instrument_id=instrument_id,
        trade_type=trade_type,
        quantity=quantity,
        price=price,
    ):
        raise IdempotencyKeyReused(idempotency_key)


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


class ApplyCustodyFees:
    """Aplica Custody Fees (R-11 C1 / R-10.6) — multi-periodo."""

    CUSTODY_INTERVAL_DAYS = 365

    def __init__(
        self,
        account_repo: SqlAlchemyAccountRepository,
        portfolio_repo: SqlAlchemyPortfolioRepository,
        ledger_repo: SqlAlchemyLedgerRepository,
        custody_obligation_repo: CustodyObligationRepository | None = None,
    ) -> None:
        self._account_repo = account_repo
        self._portfolio_repo = portfolio_repo
        self._ledger_repo = ledger_repo
        self._obligation_repo = custody_obligation_repo

    async def execute(self, scope) -> bool:
        settings = scope.account.settings or settings_from_dict(None)
        pct = settings.commission.custody_annual_pct
        if pct is None or pct <= 0:
            return False

        now = datetime.now(UTC)
        period = now.strftime("%Y")

        # Dedup duradero vía ledger: si ya se cobró ESTE periodo, no repetir.
        # (Consulta previa al claim: serializa la ventana concurrente abajo; este
        # guard se apoya en la fila ya persistida y sobrevive a reinicios.)
        last = await self._ledger_repo.last_custody_charge_at(scope.account.id)
        if last is not None:
            last_dt = last if last.tzinfo else last.replace(tzinfo=UTC)
            if (now - last_dt).days < self.CUSTODY_INTERVAL_DAYS:
                return False

        # Mutex atómico (SET NX) por cuenta+periodo: evita el doble cargo cuando
        # dos entradas superan el guard de arriba a la vez.
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

            session = getattr(self._ledger_repo, "session", None)

            # 1) Liquidar primero los PENDING más antiguos (saldar deuda, no cobrar
            #    periodo nuevo). Cada (deduct_cash + append_custody_fee(custody-<año>))
            #    va junto en el mismo SAVEPOINT (invariante Σ ledger == cash). El
            #    UNIQUE de ledger por (account, custody, custody-<año>, fee) impide
            #    doble liquidación del mismo pendiente; este guard NO bloquea los
            #    PENDING de años anteriores (no es el cobro del periodo actual).
            if self._obligation_repo is not None:
                pending_list = await self._obligation_repo.get_pending_by_account(
                    scope.account.id
                )
                for pending in pending_list:
                    pre_summary = await self._portfolio_repo.get_summary(charge_legacy_id)
                    cash = pre_summary.portfolio.cash
                    if cash <= 0 or pending.outstanding <= 0:
                        continue
                    to_charge = min(pending.outstanding, cash)
                    new_outstanding = pending.outstanding - to_charge
                    balance_after = cash - to_charge
                    description = (
                        f"Custodia {pending.period} (pendiente) {pct:.2f} % · "
                        f"patrimonio {total_equity:.2f} €"
                    )
                    async with _idempotent_savepoint(session):
                        await self._portfolio_repo.deduct_cash(
                            charge_legacy_id, to_charge, allow_partial=True
                        )
                        await self._ledger_repo.append_custody_fee(
                            account_id=scope.account.id,
                            portfolio_id=charge_portfolio_id,
                            amount=to_charge,
                            currency=scope.account.currency,
                            balance_after=balance_after,
                            reference_id=f"custody-{pending.period}",
                            description=description,
                        )
                        await self._account_repo.touch_activity(scope.account.id)
                        settled = new_outstanding <= 0
                        await self._obligation_repo.upsert(
                            account_id=scope.account.id,
                            period=pending.period,
                            status="APPLIED" if settled else "PENDING",
                            outstanding=new_outstanding,
                            total_fee=pending.total_fee,
                        )

            # 2) Cobro del periodo actual con el cash restante. cash >= fee → APPLIED
            #    (cobro completo); cash < fee → PENDING con outstanding = fee - cash.
            pre_summary = await self._portfolio_repo.get_summary(charge_legacy_id)
            cash_before = pre_summary.portfolio.cash
            description = f"Custodia anual {pct:.2f} % · patrimonio {total_equity:.2f} €"
            if cash_before >= fee_amount:
                # Cobro completo, no parcial: solo con saldo suficiente se descuenta
                # cash y se escribe el ledger. balance_after (F3) ya viene descontado;
                # invariante Σ ledger == cash se mantiene (no cargo parcial).
                balance_after = cash_before - fee_amount
                async with _idempotent_savepoint(session):
                    await self._portfolio_repo.deduct_cash(
                        charge_legacy_id,
                        fee_amount,
                        allow_partial=False,
                    )
                    await self._ledger_repo.append_custody_fee(
                        account_id=scope.account.id,
                        portfolio_id=charge_portfolio_id,
                        amount=fee_amount,
                        currency=scope.account.currency,
                        balance_after=balance_after,
                        reference_id=f"custody-{period}",
                        description=description,
                    )
                    await self._account_repo.touch_activity(scope.account.id)
                    if self._obligation_repo is not None:
                        await self._obligation_repo.upsert(
                            account_id=scope.account.id,
                            period=period,
                            status="APPLIED",
                            outstanding=0.0,
                            total_fee=fee_amount,
                        )
                # Tras el cargo persistido (dentro del SAVEPOINT, atómico con el touch
                # de activity y el upsert de obligación), el guard duradero (ledger) ya
                # protege el año; liberar mutex.
                await release_custody_charge(scope.account.id, period)
                return True
            # cash < fee: NO se descuenta, NO se escribe ledger (invariante Σ ledger ==
            # cash intacto) y NO se marca DONE. Se registra la obligación del periodo
            # como PENDING con el resto pendiente por cobrar (reintento F4b/job).
            if self._obligation_repo is not None:
                outstanding = fee_amount - cash_before
                async with _idempotent_savepoint(session):
                    await self._obligation_repo.upsert(
                        account_id=scope.account.id,
                        period=period,
                        status="PENDING",
                        outstanding=outstanding,
                        total_fee=fee_amount,
                    )
                    await self._account_repo.touch_activity(scope.account.id)
            await release_custody_charge(scope.account.id, period)
            return True
        except IntegrityError as exc:
            # R-9.3/P1: el 2º request concurrente que sí ganó el claim pero chocó
            # con el UNIQUE de custodia → ya se cobró este periodo (o, al liquidar
            # un PENDING, ya se saldó antes). Liberar mutex y devolver False
            # (idempotente). El SAVEPOINT revirtió su escritura.
            if is_unique_violation(exc):
                await release_custody_charge(scope.account.id, period)
                return False
            raise
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
        idempotency_key: str,
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

        notional = float(Decimal(str(quantity)) * Decimal(str(price)))
        fees = calculate_trade_fees(
            notional,
            trade_type,  # type: ignore[arg-type]
            settings,
            currency=scope.account.currency,
        )
        # R-10 F3: capturar el cash ANTES de mutar (execute_trade deducirá el notional
        # + fees y devolverá un summary POST-fee). Sin esta lectura previa no habría
        # base para escribir balance_after secuenciales (trade → fee).
        cash_before = (await self._portfolio_repo.get_summary(scope.legacy_portfolio_id)).portfolio.cash
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
        amount = -result.transaction.total if trade_type == "buy" else result.transaction.total
        # R-10 F3: balance_after SECUENCIAL por fila.
        #   trade: cash tras aplicar SOLO el notional (aún sin fee).
        #   fee:   cash tras aplicar notional + fee (= cash final post-operación).
        # Semántica invariante: balance_after[n] == balance_after[n-1] + amount[n].
        trade_balance = cash_before + amount
        fee_balance = trade_balance - abs(fees.total)
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
                balance_after=fee_balance,
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
        # R-10 F4b: GET de solo lectura — la custodia la aplica el job periódico,
        # no se muta estado en la lectura de tax report.
        scope = await self._account_repo.resolve_scope(account_id)
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
