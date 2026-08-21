"""Use-cases de resumen de cuentas (margen y hub listing)."""

from bolsa_domain.entities.account import (
    AccountSummary,
    InvestmentAccount,
    InvestmentPortfolio,
)
from bolsa_domain.entities.portfolio import PortfolioSummary
from bolsa_infrastructure.database.repositories.account_repository import (
    SqlAlchemyAccountRepository,
)
from bolsa_infrastructure.database.repositories.ledger_repository import SqlAlchemyLedgerRepository
from bolsa_infrastructure.database.repositories.portfolio_repository import (
    SqlAlchemyPortfolioRepository,
)


def _account_summary_from_portfolio(
    *,
    account: InvestmentAccount,
    default_portfolio: InvestmentPortfolio,
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
