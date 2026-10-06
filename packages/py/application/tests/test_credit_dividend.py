"""Dividendo: bruto y retención en el mismo paso, fuera del turno AUTO."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from bolsa_application.accounts.dividend import CreditDividend, split_dividend
from bolsa_domain.entities.account import LedgerEntry
from bolsa_domain.errors import IdempotencyKeyReused


def test_split_dividend_withholds_nineteen_percent() -> None:
    gross, withheld, net = split_dividend(Decimal("100"), Decimal("19"))
    assert gross == Decimal("100.000000")
    assert withheld == Decimal("19.000000")
    assert net == Decimal("81.000000")


@dataclass
class _Tax:
    dividend_withholding_pct: float = 19.0


@dataclass
class _Settings:
    tax: _Tax


@dataclass
class _Account:
    id: str = "acc-1"
    currency: str = "EUR"
    settings: _Settings | None = None


@dataclass
class _Portfolio:
    id: str = "pf-1"
    legacy_portfolio_id: str = "legacy-1"


@dataclass
class _Scope:
    account: _Account
    portfolio: _Portfolio
    legacy_portfolio_id: str


class _Accounts:
    def __init__(self, pct: float) -> None:
        self.scope = _Scope(
            account=_Account(settings=_Settings(tax=_Tax(dividend_withholding_pct=pct))),
            portfolio=_Portfolio(),
            legacy_portfolio_id="legacy-1",
        )
        self.touched = 0

    async def resolve_scope(self, account_id: str) -> _Scope:
        return self.scope

    async def lock_account(self, account_id: str) -> None:
        return None

    async def touch_activity(self, account_id: str) -> None:
        self.touched += 1


class _Cash:
    def __init__(self) -> None:
        self.balance = 0.0
        self.credits: list[float] = []
        self.debits: list[float] = []

    async def _credit_cash_row(self, legacy_portfolio_id: str, amount: float) -> float:
        self.credits.append(amount)
        self.balance += amount
        return self.balance

    async def _debit_cash_row(self, legacy_portfolio_id: str, amount: float) -> float:
        self.debits.append(amount)
        self.balance -= amount
        return self.balance


class _Ledger:
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
        for entry in self.entries:
            if (
                entry.account_id == account_id
                and entry.reference_type == reference_type
                and entry.reference_id == reference_id
                and entry.type == type
            ):
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
        **_: object,
    ) -> LedgerEntry:
        self._seq += 1
        entry = LedgerEntry(
            id=f"led-{self._seq}",
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
            executed_at=(datetime(2026, 1, 1, tzinfo=UTC) + timedelta(microseconds=self._seq)).isoformat(),
        )
        self.entries.append(entry)
        return entry


@pytest.mark.asyncio
async def test_credit_dividend_posts_gross_and_withholding_once() -> None:
    accounts = _Accounts(19)
    cash = _Cash()
    ledger = _Ledger()
    use_case = CreditDividend(accounts, cash, ledger)  # type: ignore[arg-type]
    first = await use_case.execute("acc-1", gross=100, idempotency_key="div-1")
    second = await use_case.execute("acc-1", gross=100, idempotency_key="div-1")
    assert first.gross == 100
    assert first.withholding == 19
    assert first.net == 81
    assert first.balance_after == 81
    assert second == first
    assert cash.balance == 81
    assert cash.credits == [100]
    assert cash.debits == [19]
    assert [entry.type for entry in ledger.entries] == ["dividend", "dividend_withholding"]
    assert accounts.touched == 1


@pytest.mark.asyncio
async def test_credit_dividend_rejects_reused_key_with_other_gross() -> None:
    use_case = CreditDividend(_Accounts(19), _Cash(), _Ledger())  # type: ignore[arg-type]
    await use_case.execute("acc-1", gross=100, idempotency_key="div-1")
    with pytest.raises(IdempotencyKeyReused):
        await use_case.execute("acc-1", gross=50, idempotency_key="div-1")


def test_auto_turn_does_not_call_the_dividend_use_case() -> None:
    worker = (
        Path(__file__).resolve().parents[4]
        / "apps"
        / "api-python"
        / "src"
        / "bolsa_api"
        / "background"
        / "auto_simulation_worker.py"
    )
    source = worker.read_text(encoding="utf-8")
    assert "CreditDividend" not in source
    assert "credit_dividend" not in source
