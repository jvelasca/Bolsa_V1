"""ListAccountSummaries skips custody and loads each portfolio once."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from types import SimpleNamespace

from bolsa_application.accounts import ListAccountSummaries
from bolsa_domain.entities.portfolio import Portfolio, PortfolioSummary


@dataclass
class _Account:
    id: str
    name: str = "A"
    leverage: float = 1.0


@dataclass
class _FakeAccountRepo:
    accounts: list[_Account]
    resolve_calls: list[str]

    async def list_accounts(
        self,
        account_type: str | None = None,
        owner_user_id: str | None = None,
    ) -> list[_Account]:
        # El fake devuelve todas las cuentas: los filtros de la firma (account_type /
        # owner_user_id, que la capa ListAccountSummaries delega al repo real) no
        # aplican sobre un set no filtrable publicado por el test.
        return list(self.accounts)

    async def resolve_scope(self, account_id: str, portfolio_id: str | None):
        self.resolve_calls.append(account_id)
        account = next(a for a in self.accounts if a.id == account_id)
        portfolio = SimpleNamespace(id=f"p-{account_id}", legacy_portfolio_id=f"leg-{account_id}")
        return SimpleNamespace(
            account=account,
            portfolio=portfolio,
            legacy_portfolio_id=portfolio.legacy_portfolio_id,
        )


@dataclass
class _FakePortfolioRepo:
    summary_calls: list[str]

    async def get_summary(self, legacy_portfolio_id: str | None = None) -> PortfolioSummary:
        self.summary_calls.append(str(legacy_portfolio_id))
        return PortfolioSummary(
            portfolio=Portfolio(id="p", name="P", currency="EUR", cash=1000.0),
            positions=[],
            total_market_value=0.0,
            total_cost=0.0,
            total_unrealized_pnl=0.0,
            total_equity=1000.0,
        )


def test_list_account_summaries_declara_el_realizado_ausente() -> None:
    """H3: la lista NO calcula el realizado (política detail-only) → ``None`` honesto.

    El detalle ``GetAccountSummary`` sí lo calcula; la lista lo deja declarado para no
    pagar el coste O(N) de agregar el historial por cuenta (ver docstring de la clase).
    """
    accounts = [_Account(id="a1"), _Account(id="a2")]
    account_repo = _FakeAccountRepo(accounts=accounts, resolve_calls=[])
    portfolio_repo = _FakePortfolioRepo(summary_calls=[])
    use_case = ListAccountSummaries(account_repo, portfolio_repo)  # type: ignore[arg-type]

    items = asyncio.run(use_case.execute())

    # Ni 0 fabricado ni valor parcial: el hueco se DECLARA (`None`), no se rellena.
    assert all(item.total_realized_pnl is None for item in items)


def test_list_account_summaries_one_summary_per_account() -> None:
    accounts = [_Account(id="a1"), _Account(id="a2")]
    account_repo = _FakeAccountRepo(accounts=accounts, resolve_calls=[])
    portfolio_repo = _FakePortfolioRepo(summary_calls=[])
    use_case = ListAccountSummaries(account_repo, portfolio_repo)  # type: ignore[arg-type]

    items = asyncio.run(use_case.execute())

    assert len(items) == 2
    assert [item.account.id for item in items] == ["a1", "a2"]
    assert account_repo.resolve_calls == ["a1", "a2"]
    assert portfolio_repo.summary_calls == ["leg-a1", "leg-a2"]
    assert all(item.total_equity == 1000.0 for item in items)
