"""A-2 — idempotencia de Deposit/Withdraw (R-7/Fase 2).

Verifica que reintentar con la misma idempotency_key NO vuelve a mover efectivo:
rejuega el movimiento original desde el ledger (guard previo a mutar cash) y
conserva la misma shape. Sin base de datos: repos fake en memoria.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from bolsa_domain.entities.account import LedgerEntry

from bolsa_application.accounts import DepositCashToAccount, WithdrawCashFromAccount


@dataclass
class _FakeAccount:
    id: str = "acc-1"
    currency: str = "EUR"


@dataclass
class _FakePortfolio:
    id: str = "pf-1"
    legacy_portfolio_id: str = "legacy-1"


@dataclass
class _FakeScope:
    """Shape mínima del AccountScope que usan los use-cases."""
    account: _FakeAccount
    portfolio: _FakePortfolio
    legacy_portfolio_id: str


class _FakeSummary:
    """Shape mínima del PortfolioSummary que usa el withdraw (portfolio.cash)."""

    def __init__(self, cash: float) -> None:
        self.portfolio = _FakeSummary._P(cash)

    @dataclass
    class _P:
        cash: float


class _FakeAccountRepo:
    def __init__(self) -> None:
        # Mapa account_id -> scope, para poder ejercitar operaciones cross-account.
        self.scopes: dict[str, _FakeScope] = {}
        self.touched = 0

    def _scope_for(self, account_id: str) -> _FakeScope:
        scope = self.scopes.get(account_id)
        if scope is None:
            # acc-1 conserva el legacy_portfolio_id original ("legacy-1") para los
            # tests existentes; otras cuentas usan su propio legacy (baldes aislados).
            legacy = "legacy-1" if account_id == "acc-1" else f"legacy-{account_id}"
            scope = _FakeScope(
                account=_FakeAccount(id=account_id, currency="EUR"),
                portfolio=_FakePortfolio(id=f"pf-{account_id}", legacy_portfolio_id=legacy),
                legacy_portfolio_id=legacy,
            )
            self.scopes[account_id] = scope
        return scope

    async def resolve_scope(self, account_id: str) -> _FakeScope:
        return self._scope_for(account_id)

    async def touch_activity(self, account_id: str) -> None:
        self.touched += 1


class _FakePortfolioRepo:
    def __init__(self) -> None:
        # Cash por portfolio (legacy_portfolio_id) para poder verificar balances por cuenta.
        self._cash: dict[str, float] = {}

    def _key(self, legacy_portfolio_id: str) -> str:
        return legacy_portfolio_id or "legacy-1"

    async def add_cash(self, legacy_portfolio_id: str, amount: float) -> float:
        key = self._key(legacy_portfolio_id)
        self._cash[key] = self._cash.get(key, 0.0) + amount
        return self._cash[key]

    async def deduct_cash(self, legacy_portfolio_id: str, amount: float) -> float:
        key = self._key(legacy_portfolio_id)
        self._cash[key] = self._cash.get(key, 0.0) - amount
        return self._cash[key]

    async def get_summary(self, legacy_portfolio_id: str) -> _FakeSummary:
        return _FakeSummary(self._cash.get(self._key(legacy_portfolio_id), 0.0))

    @property
    def cash(self) -> float:
        # Comodidad para los tests existentes: cash del portfolio por defecto (legacy-1).
        return self._cash.get("legacy-1", 0.0)


class _FakeLedgerRepo:
    """Emula find_cash_movement_by_reference + append_cash_movement."""

    def __init__(self) -> None:
        self.entries: list[LedgerEntry] = []
        self._seq = 0

    async def find_cash_movement_by_reference(
        self,
        reference_type: str,
        reference_id: str,
        *,
        account_id: str,
        type: str,
    ) -> LedgerEntry | None:
        # Igual semántica que el repo real y que el UNIQUE por-cuenta+type.
        for entry in self.entries:
            if (
                entry.account_id == account_id
                and entry.reference_type == reference_type
                and entry.reference_id == reference_id
                and entry.type == type
            ):
                return entry
        return None

    def entries_for(self, account_id: str) -> list[LedgerEntry]:
        return [e for e in self.entries if e.account_id == account_id]

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
async def test_deposit_without_key_requires_key() -> None:
    """R-10 F1: la idempotency_key es OBLIGATORIA a nivel de firma (estrategia C).

    La "escotilla residual" (omitir clave → movimiento nuevo) desaparece: omitir la
    clave lanza TypeError porque es un argumento keyword-only requerido."""
    ledger = _FakeLedgerRepo()
    portfolio = _FakePortfolioRepo()
    use_case = DepositCashToAccount(_FakeAccountRepo(), portfolio, ledger)

    with pytest.raises(TypeError):
        await use_case.execute("acc-1", amount=100.0)
    with pytest.raises(TypeError):
        await use_case.execute("acc-1", amount=100.0)
    assert portfolio.cash == 0.0
    assert len(ledger.entries) == 0


@pytest.mark.asyncio
async def test_withdraw_idempotent_same_key_does_not_double_debit() -> None:
    ledger = _FakeLedgerRepo()
    portfolio = _FakePortfolioRepo()
    account = _FakeAccountRepo()
    deposit = DepositCashToAccount(account, portfolio, ledger)
    await deposit.execute("acc-1", amount=1000.0, idempotency_key="dep-seed")

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
        await withdraw.execute("acc-1", amount=10.0, idempotency_key="wd-1")


@pytest.mark.asyncio
async def test_cross_account_same_key_each_deposits_own_amount() -> None:
    """R-9.1 cross-account (P0): la misma idempotency_key en dos cuentas es un
    movimiento distinto por cuenta. El guard (ya por cuenta) no debe absorber la
    segunda cuenta; ambas ingresan su importe y quedan 2 entradas de ledger."""
    ledger = _FakeLedgerRepo()
    portfolio = _FakePortfolioRepo()
    account = _FakeAccountRepo()
    deposit = DepositCashToAccount(account, portfolio, ledger)

    dep1 = await deposit.execute("acc-1", amount=200.0, idempotency_key="shared-key")
    dep2 = await deposit.execute("acc-2", amount=300.0, idempotency_key="shared-key")

    # Cada cuenta ingresó su importe (cash aislado por cuenta).
    assert portfolio.cash == 200.0  # acc-1 → legacy-1
    summary_acc2 = await portfolio.get_summary(
        account._scope_for("acc-2").legacy_portfolio_id
    )
    assert summary_acc2.portfolio.cash == 300.0

    # 2 movimientos, cuentas distintas, misma reference_id (idempotency_key).
    assert len(ledger.entries) == 2
    assert {e.account_id for e in ledger.entries} == {"acc-1", "acc-2"}
    assert {e.reference_id for e in ledger.entries} == {"shared-key"}
    # Cada entrada corresponde a su cuenta con su importe.
    assert dep1.kind == "external_deposit"
    assert dep2.kind == "external_deposit"
    assert dep1.account_id == "acc-1"
    assert dep2.account_id == "acc-2"
    assert dep1.amount == 200.0
    assert dep2.amount == 300.0

    # Un repliegue por cuenta con la misma key NO vuelve a mover dinero.
    replay1 = await deposit.execute("acc-1", amount=200.0, idempotency_key="shared-key")
    replay2 = await deposit.execute("acc-2", amount=300.0, idempotency_key="shared-key")
    assert portfolio.cash == 200.0
    summary_acc2_replay = await portfolio.get_summary(
        account._scope_for("acc-2").legacy_portfolio_id
    )
    assert summary_acc2_replay.portfolio.cash == 300.0
    assert len(ledger.entries) == 2
    assert replay1.amount == 200.0
    assert replay2.amount == 300.0


@pytest.mark.asyncio
async def test_same_key_deposit_then_withdrawal_are_distinct_movements() -> None:
    """R-9.1 cross-type: misma cuenta + misma key pero operación distinta
    (deposit vs withdrawal) son movimientos separados gracias al filtro por
    ``type``. Un retiro con una key ya usada para un depósito de la misma cuenta
    NO rejuega el depósito (que además vería tipo distinto y no colisionaría)."""
    ledger = _FakeLedgerRepo()
    portfolio = _FakePortfolioRepo()
    account = _FakeAccountRepo()
    deposit = DepositCashToAccount(account, portfolio, ledger)
    withdraw = WithdrawCashFromAccount(account, portfolio, ledger)

    # Misma key usada primero para un depósito y después para un retiro.
    dep = await deposit.execute("acc-1", amount=500.0, idempotency_key="same-key")
    wd = await withdraw.execute("acc-1", amount=200.0, idempotency_key="same-key")

    assert dep.kind == "external_deposit"
    assert wd.kind == "external_withdrawal"
    assert portfolio.cash == 300.0

    # Dos movimientos distintos de la misma cuenta + misma reference_id (la key),
    # diferenciados por ``type``; el filtro por type los trata como idempotencias
    # independientes (mismo comportamiento que el UNIQUE por-cuenta+type).
    assert len(ledger.entries) == 2
    assert {e.type for e in ledger.entries} == {"deposit", "withdrawal"}
    assert {e.reference_id for e in ledger.entries} == {"same-key"}

    # Replay del retiro con el depósito presente NO rejuega el depósito.
    replay_wd = await withdraw.execute("acc-1", amount=200.0, idempotency_key="same-key")
    assert replay_wd.kind == "external_withdrawal"
    assert replay_wd.amount == -200.0
    assert replay_wd.id == "same-key"
    assert portfolio.cash == 300.0
    assert len(ledger.entries) == 2
