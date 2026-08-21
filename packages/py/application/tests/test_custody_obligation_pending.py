"""R-10 F4a — custodia parcial silenciosa corregida (ADR 026, Opción B).

Semántica nueva (multi-periodo, R-11 C1 / R-10.6) de ``ApplyCustodyFees``:
- ``cash >= fee`` → cobro completo (``deduct_cash(allow_partial=False)`` +
  ``append_custody_fee(amount=fee)``) y obligación ``APPLIED``/``outstanding=0``.
- ``cash < fee`` → NO se descuenta, NO se escribe ledger, y la obligación queda
  ``PENDING`` con ``outstanding = fee - cash`` (sin perder el saldo pendiente).
- Obligación MULTI-periodo (``UNIQUE(account_id, period)``): un PENDING de un año
  anterior pervive aunque se genere/cobre el periodo actual.
- Repetición del mismo periodo no duplica (guard duradero) y dos intentos
  concurrentes no duplican (UNIQUE → ``return False``).

Se usan fakes (mismo patrón que ``test_custody_idempotency.py``) del repo de
obligación dedicado.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from bolsa_application.accounts import ApplyCustodyFees
from bolsa_application.risk_runtime import (
    clear_custody_memory_for_tests,
    clear_idempotency_memory_for_tests,
)
from bolsa_domain.account_settings import settings_from_dict


class _FakeObligationRepo:
    """Fake del repo dedicado de obligación de custodia (multi-periodo)."""

    def __init__(self) -> None:
        self.upserted: list[dict] = []
        self.rows: dict[str, dict] = {}

    async def get_pending_by_account(self, account_id: str):  # noqa: ARG001
        return [
            dict(r)
            for r in sorted(self.rows.values(), key=lambda r: r["period"])
            if r["status"] == "PENDING"
        ]

    async def upsert(self, **kwargs) -> dict:
        self.upserted.append(kwargs)
        self.rows[kwargs["period"]] = dict(kwargs)
        return self.rows[kwargs["period"]]


class _FakeLedger:
    def __init__(self, last_charge_at=None) -> None:
        self._last = last_charge_at
        self.appended: list[dict] = []
        self.total_cash = 0.0

    async def last_custody_charge_at(self, account_id: str):  # noqa: ARG001
        return self._last

    async def append_custody_fee(self, **kwargs) -> dict:
        self.appended.append(kwargs)
        self.total_cash -= kwargs["amount"]
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
        self.deduct_calls: list[dict] = []

    async def get_summary(self, portfolio_id):  # noqa: ARG001
        portfolio = type("P", (), {"cash": self._cash})
        return type("S", (), {"total_equity": self._equity, "portfolio": portfolio})

    async def deduct_cash(self, portfolio_id, amount, *, allow_partial=False):  # noqa: ARG001
        self.deduct_calls.append({"amount": amount, "allow_partial": allow_partial})
        if amount > self._cash and not allow_partial:
            raise ValueError("Efectivo insuficiente")
        self._cash -= amount
        return self._cash


class _Scope:
    def __init__(self, portfolio, portfolios) -> None:
        self.account = type("A", (), {"id": "acc-1", "currency": "EUR", "settings": None})
        self.portfolio = portfolio
        self._portfolios = portfolios


def _settings_with_custody(pct: float):
    return settings_from_dict(
        {"commission": {"custodyAnnualPct": pct}, "tax": {"costBasisMethod": "FIFO"}}
    )


def _portfolio():
    return type("P", (), {"id": "pf-id", "legacy_portfolio_id": "pf-legacy"})


def _build(cash: float, equity: float, *, obligation_repo=None, last_charge=None):
    portfolio = _portfolio()
    portfolios = [portfolio]
    scope = _Scope(portfolio, portfolios)
    scope.account.settings = _settings_with_custody(0.2)
    ledger = _FakeLedger(last_charge_at=last_charge)
    account_repo = _FakeAccountRepo(portfolios)
    portfolio_repo = _FakePortfolioRepo(cash=cash, equity=equity)
    uc = ApplyCustodyFees(
        account_repo,
        portfolio_repo,
        ledger,
        custody_obligation_repo=obligation_repo,
    )
    return uc, scope, ledger, portfolio_repo, account_repo, obligation_repo


@pytest.fixture(autouse=True)
def _clear_memory():
    clear_custody_memory_for_tests()
    clear_idempotency_memory_for_tests()
    yield
    clear_custody_memory_for_tests()
    clear_idempotency_memory_for_tests()


def asyncio_run(coro):
    import asyncio

    return asyncio.run(coro)


def _now() -> datetime:
    return datetime.now(UTC)


def test_cash_menor_que_fee_register_pending_sin_ledger() -> None:
    """cash < fee: NO append_custody_fee, obligación PENDING con outstanding=fee-cash,
    ledger NO escrito y Σ cash sin cambio (no se descuenta)."""
    obligation = _FakeObligationRepo()
    # equity 10_000 → fee = 20.0; cash = 10 < 20
    uc, scope, ledger, portfolio_repo, account_repo, _ = _build(
        cash=10.0, equity=10_000.0, obligation_repo=obligation
    )

    assert asyncio_run(uc.execute(scope)) is True

    # No se escribió ledger ni se descontó cash.
    assert ledger.appended == []
    assert portfolio_repo.deduct_calls == []
    assert portfolio_repo._cash == 10.0

    # Obligación PENDING con el resto pendiente por cobrar.
    assert len(obligation.upserted) == 1
    upsert = obligation.upserted[0]
    assert upsert["status"] == "PENDING"
    assert upsert["outstanding"] == pytest.approx(20.0 - 10.0)
    assert upsert["total_fee"] == pytest.approx(20.0)
    assert upsert["period"] == _now().strftime("%Y")

    # Σ cash (representado por portfolio_repo._cash) sin cambio.
    assert account_repo.activities >= 1


def test_cash_superior_igual_a_fee_cobra_completo() -> None:
    """cash >= fee: cobro completo (amount == fee), obligación APPLIED/outstanding=0."""
    obligation = _FakeObligationRepo()
    # equity 10_000 → fee = 20.0; cash = 100 >= 20
    uc, scope, ledger, portfolio_repo, account_repo, _ = _build(
        cash=100.0, equity=10_000.0, obligation_repo=obligation
    )

    assert asyncio_run(uc.execute(scope)) is True

    # Ledger con el cargo completo.
    assert len(ledger.appended) == 1
    assert ledger.appended[0]["amount"] == pytest.approx(20.0)
    assert ledger.appended[0]["balance_after"] == pytest.approx(80.0)

    # Se descuenta con allow_partial=False (nunca parcial).
    assert len(portfolio_repo.deduct_calls) == 1
    assert portfolio_repo.deduct_calls[0]["allow_partial"] is False
    assert portfolio_repo.deduct_calls[0]["amount"] == pytest.approx(20.0)
    assert portfolio_repo._cash == pytest.approx(80.0)

    # Obligación APPLIED con outstanding=0.
    assert len(obligation.upserted) == 1
    assert obligation.upserted[0]["status"] == "APPLIED"
    assert obligation.upserted[0]["outstanding"] == pytest.approx(0.0)
    assert obligation.upserted[0]["total_fee"] == pytest.approx(20.0)


def test_repetir_mismo_periodo_no_duplica() -> None:
    """Guard duradero (ledger): si ya se cobró este periodo, no se repite."""
    obligation = _FakeObligationRepo()
    uc, scope, ledger, _, _, _ = _build(
        cash=100.0,
        equity=10_000.0,
        obligation_repo=obligation,
        last_charge=_now(),  # ya cobrada hace unos días
    )

    assert asyncio_run(uc.execute(scope)) is False
    assert ledger.appended == []
    assert obligation.upserted == []


def test_cash_igual_a_fee_cobra_completo() -> None:
    """cash == fee (límite): se cobra el total (>=)."""
    obligation = _FakeObligationRepo()
    # equity 10_000 → fee = 20.0; cash = 20 == fee
    uc, scope, ledger, portfolio_repo, _, _ = _build(
        cash=20.0, equity=10_000.0, obligation_repo=obligation
    )

    assert asyncio_run(uc.execute(scope)) is True
    assert len(ledger.appended) == 1
    assert ledger.appended[0]["amount"] == pytest.approx(20.0)
    assert portfolio_repo._cash == pytest.approx(0.0)
    assert obligation.upserted[0]["status"] == "APPLIED"
    assert obligation.upserted[0]["outstanding"] == pytest.approx(0.0)
