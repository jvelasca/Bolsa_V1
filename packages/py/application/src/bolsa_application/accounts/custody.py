"""Use-case de aplicación de comisiones de custodia."""

from datetime import UTC, datetime

from bolsa_domain.account_settings import settings_from_dict
from bolsa_domain.entities.account import AccountScope
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
from sqlalchemy.exc import IntegrityError

from bolsa_application.risk_runtime import claim_custody_charge, release_custody_charge

from .idempotency import _idempotent_savepoint


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

    async def execute(self, scope: AccountScope) -> bool:
        """Liquida las obligaciones de custodia pendientes de la cuenta.

        R-11 C1 / R-10.6: primero el PENDING más antiguo y después el periodo
        actual. Importe sobre el ``total_equity`` **agregado** de la cuenta, pero el
        cobro se hace siempre desde la cartera seleccionada/default
        (``scope.portfolio``, `custody_charge_source = DEFAULT_PORTFOLIO`); no hay
        transferencia implícita entre carteras.
        """
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
