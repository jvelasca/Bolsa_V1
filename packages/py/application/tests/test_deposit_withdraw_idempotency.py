"""A-2 — idempotencia de Deposit/Withdraw (R-7/Fase 2).

Verifica que reintentar con la misma idempotency_key NO vuelve a mover efectivo:
rejuega el movimiento original desde el ledger (guard previo a mutar cash) y
conserva la misma shape. Sin base de datos: repos fake en memoria.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from bolsa_application.accounts import DepositCashToAccount, WithdrawCashFromAccount
from bolsa_domain.entities.account import LedgerEntry


@dataclass
class _FakeAccount:
    currency: str = "EUR"


@dataclass
class _FakePortfolio:
    id: str = "pf-1"


@dataclass
class _FakeScope:
    """Shape mínima del AccountScope que usan los use-cases."""
    account: _FakeAccount = field(default_factory=_FakeAccount)
    portfolio: _FakePortfolio = field(default_factory=_FakePortfolio)
    legacy_portfolio_id: str = "legacy-1"


class _FakeSummary:
    """Shape mínima del PortfolioSummary que usa el withdraw (portfolio.cash)."""

    def __init__(self, cash: float) -> None:
        self.portfolio = _FakeSummary._P(cash)

    @dataclass
    class _P:
        cash: float


class _FakeAccountRepo:
    def __init__(self) -> None:
        self.scope = _FakeScope()
        self.touched = 0

    async def resolve_scope(self, account_id: str) -> _FakeScope:
        return self.scope

    async def touch_activity(self, account_id: str) -> None:
        self.touched += 1


class _FakePortfolioRepo:
    def __init__(self) -> None:
        self.cash = 0.0

    async def add_cash(self, legacy_portfolio_id: str, amount: float) -> float:
        self.cash += amount
        return self.cash

    async def deduct_cash(self, legacy_portfolio_id: str, amount: float) -> float:
        self.cash -= amount
        return self.cash

    async def get_summary(self, legacy_portfolio_id: str) -> _FakeSummary:
        return _FakeSummary(self.cash)


class _FakeLedgerRepo:
    """Emula find_cash_movement_by_reference + append_cash_movement."""

    def __init__(self) -> None:
        self.entries: list[LedgerEntry] = []
        self._seq = 0

    async def find_cash_movement_by_reference(
        self,
        reference_type: str,
        reference_id: str,
    ) -> LedgerEntry | None:
        for entry in self.entries:
            if entry.reference_type == reference_type and entry.reference_id == reference_id:
                return entry
        return None

    async def append_cash_movement(
        self,
        *,
        account_id: str,
        portfolio_id: str,
        entry_type: str,
        amount: float,
        currency: str,
        balance_after: float,
        reference_id: str,
        reference_type: str = "transfer",
        description: str | None = None,
    ) -> LedgerEntry:
        self._seq += 1
        entry = LedgerEntry(
            id=f"entry-{self._seq}",
            account_id=account_id,
            portfolio_id=portfolio_id,
            type=entry_type,
            amount=amount,
            currency=currency,
            balance_after=balance_after,
            instrument_id=None,
            symbol=None,
            quantity=None,
            price=None,
            reference_type=reference_type,
            reference_id=reference_id,
            description=description,
            executed_at="2026-08-20T08:00:00Z",
        )
        self.entries.append(entry)
        return entry


@pytest.mark.asyncio
async def test_deposit_idempotent_same_key_does_not_double_credit() -> None:
    ledger = _FakeLedgerRepo()
    portfolio = _FakePortfolioRepo()
    use_case = DepositCashToAccount(_FakeAccountRepo(), portfolio, ledger)

    first = await use_case.execute("acc-1", amount=1000.0, idempotency_key="dep-key-1")
    assert portfolio.cash == 1000.0
    assert len(ledger.entries) == 1

    replay = await use_case.execute("acc-1", amount=1000.0, idempotency_key="dep-key-1")
    # No se vuelve a mover efectivo ni se añade otra entrada.
    assert portfolio.cash == 1000.0
    assert len(ledger.entries) == 1
    # Misma shape: id = idempotency_key, kind/amount/balance coherentes.
    assert replay.id == "dep-key-1"
    assert first.id == "dep-key-1"
    assert replay.kind == "external_deposit"
    assert replay.amount == 1000.0
    assert replay.balance_after == 1000.0


@pytest.mark.asyncio
async def test_deposit_distinct_keys_move_money_twice() -> None:
    ledger = _FakeLedgerRepo()
    portfolio = _FakePortfolioRepo()
    use_case = DepositCashToAccount(_FakeAccountRepo(), portfolio, ledger)

    await use_case.execute("acc-1", amount=100.0, idempotency_key="k-1")
    await use_case.execute("acc-1", amount=50.0, idempotency_key="k-2")
    assert portfolio.cash == 150.0
    assert len(ledger.entries) == 2


@pytest.mark.asyncio
async def test_deposit_without_key_uses_fresh_id() -> None:
    ledger = _FakeLedgerRepo()
    portfolio = _FakePortfolioRepo()
    use_case = DepositCashToAccount(_FakeAccountRepo(), portfolio, ledger)

    result = await use_case.execute("acc-1", amount=100.0)
    assert result.id is not None
    assert result.id != ""
    # Nuevo movimiento en cada llamada sin clave.
    second = await use_case.execute("acc-1", amount=100.0)
    assert second.id != result.id
    assert portfolio.cash == 200.0


@pytest.mark.asyncio
async def test_withdraw_idempotent_same_key_does_not_double_debit() -> None:
    ledger = _FakeLedgerRepo()
    portfolio = _FakePortfolioRepo()
    account = _FakeAccountRepo()
    deposit = DepositCashToAccount(account, portfolio, ledger)
    await deposit.execute("acc-1", amount=1000.0)

    withdraw = WithdrawCashFromAccount(account, portfolio, ledger)
    await withdraw.execute("acc-1", amount=300.0, idempotency_key="wd-key-1")
    assert portfolio.cash == 700.0
    assert len(ledger.entries) == 2

    replay = await withdraw.execute("acc-1", amount=300.0, idempotency_key="wd-key-1")
    # No vuelve a debitar ni añade entrada, ni falla por saldo (guard previo).
    assert portfolio.cash == 700.0
    assert len(ledger.entries) == 2
    assert replay.id == "wd-key-1"
    assert replay.kind == "external_withdrawal"
    assert replay.amount == -300.0
    assert replay.balance_after == 700.0


@pytest.mark.asyncio
async def test_withdraw_replay_does_not_trigger_insufficient_funds() -> None:
    ledger = _FakeLedgerRepo()
    portfolio = _FakePortfolioRepo()
    account = _FakeAccountRepo()
    deposit = DepositCashToAccount(account, portfolio, ledger)
    await deposit.execute("acc-1", amount=100.0, idempotency_key="dep-1")

    withdraw = WithdrawCashFromAccount(account, portfolio, ledger)
    await withdraw.execute("acc-1", amount=100.0, idempotency_key="wd-1")
    # Retirada posterior del resto del saldo deja cash en 0; el replay de la
    # retirada previa NO debe rechazarse por efectivo insuficiente.
    await portfolio.deduct_cash("legacy-1", portfolio.cash)
    replay = await withdraw.execute("acc-1", amount=100.0, idempotency_key="wd-1")
    assert replay.kind == "external_withdrawal"
    assert portfolio.cash == 0.0
    assert len(ledger.entries) == 2


@pytest.mark.asyncio
async def test_withdraw_without_key_requires_funds() -> None:
    ledger = _FakeLedgerRepo()
    portfolio = _FakePortfolioRepo()
    withdraw = WithdrawCashFromAccount(_FakeAccountRepo(), portfolio, ledger)
    with pytest.raises(ValueError, match="Efectivo insuficiente"):
        await withdraw.execute("acc-1", amount=10.0)
