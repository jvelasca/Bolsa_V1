"""R-7/Phase-1 — idempotencia de custodia (doble cargo en GET) + release AUTO.

Tres sub-casos:
1. ``claim_custody_charge``/``release_custody_charge`` serializan por cuenta+periodo
   (mutex en memoria; Redis no disponible en este entorno → fallback de memoria).
2. ``ApplyCustodyFees.execute`` aplica el cargo UNA sola vez aunque dos lecturas
   (summary + tax) entren a la vez: la segunda debe saltarse.
3. ``release_auto_execute_idempotency`` libera un claim AUTO no confirmado para
   permitir reintento (fix de fill fallido).
"""

from __future__ import annotations

import pytest

from bolsa_application.accounts import ApplyCustodyFees
from bolsa_application.risk_runtime import (
    claim_auto_execute_idempotency,
    claim_custody_charge,
    clear_custody_memory_for_tests,
    clear_idempotency_memory_for_tests,
    make_custody_idempotency_key,
    release_auto_execute_idempotency,
    release_custody_charge,
)
from bolsa_domain.account_settings import settings_from_dict


class _FakeLedger:
    def __init__(self, last_charge_at=None) -> None:
        self._last = last_charge_at
        self.appended: list[dict] = []

    async def last_custody_charge_at(self, account_id: str):  # noqa: ARG001
        return self._last

    async def append_custody_fee(self, **kwargs) -> dict:
        self.appended.append(kwargs)
        return {"id": "ledger-1", "executed_at": "t"}


class _FakeAccountRepo:
    def __init__(self, portfolios) -> None:
        self._portfolios = portfolios
        self.activities = 0

    async def list_portfolios(self, account_id):  # noqa: ARG001
        return self._portfolios

    async def touch_activity(self, account_id):  # noqa: ARG001
        self.activities += 1


class _FakePortfolioRepo:
    def __init__(self, cash: float, equity: float) -> None:
        self._cash = cash
        self._equity = equity
        self.deducted: float | None = None

    async def get_summary(self, portfolio_id):  # noqa: ARG001
        portfolio = type("P", (), {"cash": self._cash})
        return type("S", (), {"total_equity": self._equity, "portfolio": portfolio})

    async def deduct_cash(self, portfolio_id, amount, *, allow_partial=False):  # noqa: ARG001
        applied = min(amount, self._cash)
        self._cash -= applied
        self.deducted = applied
        return self._cash


class _Scope:
    def __init__(self, portfolio, portfolios) -> None:
        self.account = type("A", (), {"id": "acc-1", "currency": "EUR", "settings": None})
        self.portfolio = portfolio
        self._portfolios = portfolios


@pytest.fixture(autouse=True)
def _clear_memory():
    clear_custody_memory_for_tests()
    clear_idempotency_memory_for_tests()
    yield
    clear_custody_memory_for_tests()
    clear_idempotency_memory_for_tests()


def _scope_with_charged_ledger(last_charge_at):
    portfolio = type("P", (), {"id": "pf-id", "legacy_portfolio_id": "pf-legacy"})
    portfolios = [portfolio]
    scope = _Scope(portfolio, portfolios)
    ledger = _FakeLedger(last_charge_at=last_charge_at)
    account_repo = _FakeAccountRepo(portfolios)
    portfolio_repo = _FakePortfolioRepo(cash=10_000.0, equity=100_000.0)
    return ApplyCustodyFees(account_repo, portfolio_repo, ledger), scope, ledger


def test_custody_claim_and_release():
    key = make_custody_idempotency_key("acc-1", "2026")
    assert key == "custody|acc-1|2026"
    assert asyncio_run(claim_custody_charge("acc-1", "2026")) is True
    assert asyncio_run(claim_custody_charge("acc-1", "2026")) is False  # ya tomado
    asyncio_run(release_custody_charge("acc-1", "2026"))
    assert asyncio_run(claim_custody_charge("acc-1", "2026")) is True  # reintento OK


def _settings_with_custody(pct: float):
    return settings_from_dict(
        {"commission": {"custodyAnnualPct": pct}, "tax": {"costBasisMethod": "FIFO"}}
    )


def test_custody_charged_once_across_concurrent_reads():
    """Dos lecturas concurrentes (misma cuenta+periodo) → un solo cargo.

    Se simula la ventana concurrente: la primera request toma el mutex (claim) y
    está a medias; la segunda entra y debe saltarse. Además, tras un cargo
    confirmado, el dedup duradero (ledger) impide repetir en el mismo periodo.
    """
    portfolio = type("P", (), {"id": "pf-id", "legacy_portfolio_id": "pf-legacy"})
    portfolios = [portfolio]
    scope = _Scope(portfolio, portfolios)
    scope.account.settings = _settings_with_custody(0.2)
    ledger = _FakeLedger(last_charge_at=None)
    account_repo = _FakeAccountRepo(portfolios)
    portfolio_repo = _FakePortfolioRepo(cash=10_000.0, equity=100_000.0)

    uc = ApplyCustodyFees(account_repo, portfolio_repo, ledger)

    # 1) Ventana concurrente: la 1ª request ya tomó el mutex (claim en vuelo).
    assert asyncio_run(claim_custody_charge("acc-1", "2026")) is True
    # La 2ª request entra y ve el claim ocupado → se salta (no doble cargo).
    assert asyncio_run(uc.execute(scope)) is False
    assert len(ledger.appended) == 0  # sin cargo extra
    asyncio_run(release_custody_charge("acc-1", "2026"))

    # 2) Cargo confirmado: la fila de custodia queda en el ledger → el dedup
    #    duradero impide repetir dentro del periodo (aunque el mutex se libera).
    ledger._last = datetime_now_utc()  # el cargo ya consta en el ledger
    assert asyncio_run(uc.execute(scope)) is False
    assert len(ledger.appended) == 0


def test_custody_no_charge_releases_claim():
    """Si no hay patrimonio (equity<=0), no se cobra y se libera el mutex."""
    portfolio = type("P", (), {"id": "pf-id", "legacy_portfolio_id": "pf-legacy"})
    portfolios = [portfolio]
    scope = _Scope(portfolio, portfolios)
    scope.account.settings = _settings_with_custody(0.2)
    ledger = _FakeLedger(last_charge_at=None)
    account_repo = _FakeAccountRepo(portfolios)
    portfolio_repo = _FakePortfolioRepo(cash=0.0, equity=0.0)

    uc = ApplyCustodyFees(account_repo, portfolio_repo, ledger)
    assert asyncio_run(uc.execute(scope)) is False
    assert len(ledger.appended) == 0  # no cargo
    # el mutex quedó liberado: un siguiente tick con patrimonio puede cobrar
    portfolio_repo._cash = 100_000.0
    portfolio_repo._equity = 100_000.0
    assert asyncio_run(uc.execute(scope)) is True


def test_custody_skips_when_already_charged_this_period():
    """Dedup duradero vía ledger: si ya se cobró este periodo, no repetir."""
    portfolio = type("P", (), {"id": "pf-id", "legacy_portfolio_id": "pf-legacy"})
    portfolios = [portfolio]
    scope = _Scope(portfolio, portfolios)
    scope.account.settings = _settings_with_custody(0.2)
    now = datetime_now_utc()
    ledger = _FakeLedger(last_charge_at=now)  # ya cobrada hace unos días
    account_repo = _FakeAccountRepo(portfolios)
    portfolio_repo = _FakePortfolioRepo(cash=10_000.0, equity=100_000.0)

    uc = ApplyCustodyFees(account_repo, portfolio_repo, ledger)
    assert asyncio_run(uc.execute(scope)) is False
    assert len(ledger.appended) == 0


def test_release_auto_idempotency_allows_retry():
    """Fix C: un fill fallido libera el claim AUTO para permitir reintento."""
    key = "inst-1|2026-08-04|pol-1|entry_long"
    assert asyncio_run(claim_auto_execute_idempotency(key)) is True
    asyncio_run(release_auto_execute_idempotency(key))
    assert asyncio_run(claim_auto_execute_idempotency(key)) is True  # reintento OK


def asyncio_run(coro):
    import asyncio

    return asyncio.run(coro)


def datetime_now_utc():
    from datetime import UTC, datetime

    return datetime.now(UTC)
