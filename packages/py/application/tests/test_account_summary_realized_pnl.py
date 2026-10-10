"""F4 — P&L realizado AGREGADO en el resumen de cuenta (use-case).

Cubre que ``GetAccountSummary`` publique el realizado de todo el historial reutilizando la
vía canónica del tax report, y que un realizado NO medible se propague como ``None``
(«Sin dato todavía»), nunca como 0 fabricado.
"""

from __future__ import annotations

import pytest

from bolsa_application.accounts.summary import (
    GetAccountSummary,
    _account_summary_from_portfolio,
    _all_time_realized_pnl,
)
from bolsa_domain.account_settings import AccountSettings, default_account_settings
from bolsa_domain.entities.account import (
    AccountScope,
    InvestmentAccount,
    InvestmentPortfolio,
    LedgerEntry,
)
from bolsa_domain.entities.portfolio import (
    Portfolio,
    PortfolioSummary,
    Transaction,
)


class _FakeAccountRepo:
    def __init__(self, scope: AccountScope) -> None:
        self._scope = scope

    async def resolve_scope(
        self, account_id: str | None, portfolio_id: str | None = None
    ) -> AccountScope:
        return self._scope

    async def list_portfolios(self, account_id: str) -> list[InvestmentPortfolio]:
        return [self._scope.portfolio]


class _FakePortfolioRepo:
    def __init__(
        self, transactions: list[Transaction], summary: PortfolioSummary
    ) -> None:
        self._transactions = transactions
        self._summary = summary

    async def list_transactions(
        self,
        legacy_portfolio_id: str,
        *,
        limit: int | None = 50,
        executed_before: object | None = None,
    ) -> list[Transaction]:
        return list(self._transactions)

    async def get_summary(self, legacy_portfolio_id: str) -> PortfolioSummary:
        return self._summary


class _FakeLedgerRepo:
    def __init__(self, entries: list[LedgerEntry]) -> None:
        self._entries = entries

    async def list_for_account(
        self,
        account_id: str,
        *,
        limit: int | None = 50,
        offset: int = 0,
        portfolio_id: str | None = None,
        executed_from: object | None = None,
        executed_to: object | None = None,
    ) -> list[LedgerEntry]:
        return list(self._entries)


def _settings() -> AccountSettings:
    # FIFO + ES por defecto (método canónico del tax report).
    return default_account_settings()


def _account(settings: AccountSettings | None = None) -> InvestmentAccount:
    return InvestmentAccount(
        id="acc-1",
        user_id="u-1",
        name="A",
        description=None,
        type="simulated",
        status="active",
        currency="EUR",
        base_currency="EUR",
        initial_deposit=100_000.0,
        leverage=1.0,
        margin_call_level_pct=100.0,
        is_default=True,
        settings=settings if settings is not None else _settings(),
        strategy_definition_id=None,
        source_backtest_run_id=None,
        created_at="t",
        updated_at="t",
        last_activity_at=None,
    )


def _portfolio() -> InvestmentPortfolio:
    return InvestmentPortfolio(
        id="pf-1",
        account_id="acc-1",
        legacy_portfolio_id="legacy-1",
        name="P",
        description=None,
        strategy_tag=None,
        sort_order=0,
        is_default=True,
    )


def _transactions() -> list[Transaction]:
    # buy 10@100, sell 5@120 (2026) — sin fee en la transacción: la fee entra por ledger.
    return [
        Transaction(
            id="b",
            type="buy",
            instrument_id="inst-XYZ",
            symbol="XYZ",
            quantity=10.0,
            price=100.0,
            total=1000.0,
            executed_at="2025-05-01T00:00:00Z",
        ),
        Transaction(
            id="s",
            type="sell",
            instrument_id="inst-XYZ",
            symbol="XYZ",
            quantity=5.0,
            price=120.0,
            total=600.0,
            executed_at="2026-06-01T00:00:00Z",
        ),
    ]


def _ledger_fees() -> list[LedgerEntry]:
    def fee(entry_id: str, ref: str, amount: float) -> LedgerEntry:
        return LedgerEntry(
            id=entry_id,
            account_id="acc-1",
            portfolio_id="legacy-1",
            type="fee",
            amount=amount,
            currency="EUR",
            balance_after=0.0,
            instrument_id="inst-XYZ",
            symbol="XYZ",
            quantity=None,
            price=None,
            reference_type="trade",
            reference_id=ref,
            description=None,
            executed_at="2026-06-01T00:00:00Z",
        )

    return [fee("f-b", "b", -5.0), fee("f-s", "s", -3.0)]


def _portfolio_summary() -> PortfolioSummary:
    return PortfolioSummary(
        portfolio=Portfolio(id="pf-1", name="P", currency="EUR", cash=10_000.0),
        positions=[],
        total_market_value=0.0,
        total_cost=0.0,
        total_unrealized_pnl=0.0,
        total_equity=10_000.0,
    )


def _scope() -> AccountScope:
    return AccountScope(
        account=_account(),
        portfolio=_portfolio(),
        legacy_portfolio_id="legacy-1",
    )


@pytest.mark.asyncio
async def test_compute_all_time_realized_pnl_with_ledger_fees() -> None:
    value = await _all_time_realized_pnl(
        account_id="acc-1",
        account_repo=_FakeAccountRepo(_scope()),
        portfolio_repo=_FakePortfolioRepo(_transactions(), _portfolio_summary()),
        ledger_repo=_FakeLedgerRepo(_ledger_fees()),
    )
    # FIFO: (1000+5)/10 por acción * 5 = 502.5; proceeds 600-3 = 597 → +94.5.
    assert value == pytest.approx(94.5)


@pytest.mark.asyncio
async def test_realized_none_cuando_fuente_no_disponible() -> None:
    # Sin ledger_repo no se pueden mapear fees → NO se fabrica un valor parcial.
    value = await _all_time_realized_pnl(
        account_id="acc-1",
        account_repo=_FakeAccountRepo(_scope()),
        portfolio_repo=_FakePortfolioRepo(_transactions(), _portfolio_summary()),
        ledger_repo=None,
    )
    assert value is None


@pytest.mark.asyncio
async def test_get_account_summary_publica_realizado_agregado() -> None:
    use_case = GetAccountSummary(
        _FakeAccountRepo(_scope()),
        _FakePortfolioRepo(_transactions(), _portfolio_summary()),
        _FakeLedgerRepo(_ledger_fees()),
    )
    summary = await use_case.execute("acc-1")
    assert summary.total_realized_pnl == pytest.approx(94.5)


def test_account_summary_from_portfolio_default_es_none() -> None:
    # Fuente ausente → None (hueco declarado), nunca 0.
    summary = _account_summary_from_portfolio(
        account=_account(),
        default_portfolio=_portfolio(),
        portfolio_summary=_portfolio_summary(),
    )
    assert summary.total_realized_pnl is None


def test_account_summary_from_portfolio_propaga_el_valor() -> None:
    summary = _account_summary_from_portfolio(
        account=_account(),
        default_portfolio=_portfolio(),
        portfolio_summary=_portfolio_summary(),
        total_realized_pnl=94.5,
    )
    assert summary.total_realized_pnl == pytest.approx(94.5)
