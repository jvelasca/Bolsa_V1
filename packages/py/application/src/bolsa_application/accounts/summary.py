"""Use-cases de resumen de cuentas (margen y hub listing)."""

from bolsa_application.accounts.tax import collect_report_inputs
from bolsa_domain.account_settings import settings_from_dict
from bolsa_domain.entities.account import (
    AccountSummary,
    InvestmentAccount,
    InvestmentPortfolio,
)
from bolsa_domain.entities.portfolio import PortfolioSummary
from bolsa_domain.tax_report import (
    TaxReportTransaction,
    compute_all_time_realized_pnl,
)
from bolsa_infrastructure.database.repositories.account_repository import (
    SqlAlchemyAccountRepository,
)
from bolsa_infrastructure.database.repositories.ledger_repository import SqlAlchemyLedgerRepository
from bolsa_infrastructure.database.repositories.portfolio_repository import (
    SqlAlchemyPortfolioRepository,
)


async def _all_time_realized_pnl(
    *,
    account_id: str,
    account_repo: SqlAlchemyAccountRepository,
    portfolio_repo: SqlAlchemyPortfolioRepository,
    ledger_repo: SqlAlchemyLedgerRepository | None,
) -> float | None:
    """P&L realizado AGREGADO de todo el historial, o ``None`` si no es medible.

    Reutiliza la MISMA vía de recogida/fees/método que ``GetTaxReport``
    (``collect_report_inputs`` + ``compute_all_time_realized_pnl``), de modo que el valor
    concilie con ``net_realized_gain`` del report para un ejercicio que contenga todas las
    ventas.

    Fail-closed (UNKNOWN ≠ 0): sin ``ledger_repo`` no se pueden mapear las fees del ledger
    y el realizado NO conciliaría con el tax report → ``None`` («Sin dato todavía»), nunca un
    valor parcial fabricado. Con historial vacío el dominio devuelve ``0.0`` (hecho conocido:
    una cuenta sin operaciones cerradas tiene 0 de realizado, no un dato ausente).
    """
    if ledger_repo is None:
        return None
    scope = await account_repo.resolve_scope(account_id)
    settings = scope.account.settings or settings_from_dict(None)
    method = settings.tax.cost_basis_method
    transactions, fees_by_tx = await collect_report_inputs(
        account_repo=account_repo,
        portfolio_repo=portfolio_repo,
        ledger_repo=ledger_repo,
        account_id=scope.account.id,
    )
    # Fees aplicadas como en la cara realized del tax report (fee de compra capitalizada
    # en el cost-basis, fee de venta descontada de los proceeds).
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
            fee_amount=fees_by_tx.get(tx.id, 0.0),
        )
        for tx in transactions
    ]
    return compute_all_time_realized_pnl(transactions=report_tx, method=method)


def _account_summary_from_portfolio(
    *,
    account: InvestmentAccount,
    default_portfolio: InvestmentPortfolio,
    portfolio_summary: PortfolioSummary,
    total_realized_pnl: float | None = None,
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
        total_realized_pnl=total_realized_pnl,
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
        # F4: P&L realizado agregado de todo el historial (base canónica tax report).
        total_realized_pnl = await _all_time_realized_pnl(
            account_id=scope.account.id,
            account_repo=self._account_repo,
            portfolio_repo=self._portfolio_repo,
            ledger_repo=self._ledger_repo,
        )
        return _account_summary_from_portfolio(
            account=scope.account,
            default_portfolio=scope.portfolio,
            portfolio_summary=summary,
            total_realized_pnl=total_realized_pnl,
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

    async def execute(
        self,
        account_type: str | None = None,
        owner_user_id: str | None = None,
    ) -> list[AccountSummary]:
        accounts = await self._account_repo.list_accounts(
            account_type=account_type,
            owner_user_id=owner_user_id,
        )
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
