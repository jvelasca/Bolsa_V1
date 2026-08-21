"""Use-case de informe fiscal."""

from dataclasses import replace

from bolsa_domain.account_settings import settings_from_dict
from bolsa_domain.entities.portfolio import Transaction
from bolsa_domain.tax_report import (
    TaxReportSummary,
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

    async def execute(self, account_id: str, year: int) -> TaxReportSummary:
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
