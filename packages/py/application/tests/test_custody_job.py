"""R-10 F4b — RunCustodyJob: custodia fuera del GET, job sobre cuentas ACTIVAS.

Verifica la orquestación del job sobre fakes (mismo patrón que
``test_custody_obligation_pending.py``), con el fake de cuentas distinguiendo
activas/cerradas:
- solo se procesan cuentas ``status == "active"`` (la cerrada no se toca),
- agregado ``{scanned, applied_complete, pending, skipped}`` coherente,
- idempotente ante doble invocación (no re-cobra el mismo periodo),
- multi-periodo (R-11 C1 / R-10.6): ``pending`` se reporta cuando queda alguna
  obligación PENDING (no solo el periodo en curso).
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from bolsa_application.custody_job import RunCustodyJob
from bolsa_application.risk_runtime import (
    clear_custody_memory_for_tests,
    clear_idempotency_memory_for_tests,
)
from bolsa_domain.account_settings import settings_from_dict


class _FakeAccountRepo:
    """Cuentas activas + scope (una cartera por cuenta)."""

    def __init__(self, accounts: list) -> None:
        self._accounts = accounts
        self.touches = 0

    async def list_active_accounts(self):
        return [a for a in self._accounts if a.status == "active"]

    async def resolve_scope(self, account_id: str, portfolio_id=None):  # noqa: ARG001
        account = next(a for a in self._accounts if a.id == account_id)
        portfolio = SimpleNamespace(
            id=f"pf-{account.id}",
            legacy_portfolio_id=f"leg-{account.id}",
            is_default=True,
        )
        return SimpleNamespace(account=account, portfolio=portfolio)

    async def list_portfolios(self, account_id: str):  # noqa: ARG001
        account = next(a for a in self._accounts if a.id == account_id)
        return [
            SimpleNamespace(
                id=f"pf-{account.id}",
                legacy_portfolio_id=f"leg-{account.id}",
                is_default=True,
            )
        ]

    async def touch_activity(self, account_id):  # noqa: ARG001
        self.touches += 1


class _FakePortfolioRepo:
    def __init__(self, cash: float, equity: float) -> None:
        self._cash = cash
        self._equity = equity
        self.deduct_calls: list[dict] = []

    async def get_summary(self, portfolio_id):  # noqa: ARG001
        portfolio = SimpleNamespace(cash=self._cash)
        return SimpleNamespace(total_equity=self._equity, portfolio=portfolio)

    async def deduct_cash(self, portfolio_id, amount, *, allow_partial=False):  # noqa: ARG001
        self.deduct_calls.append({"amount": amount, "allow_partial": allow_partial})
        if amount > self._cash and not allow_partial:
            raise ValueError("Efectivo insuficiente")
        self._cash -= amount
        return self._cash


class _FakeLedger:
    def __init__(self) -> None:
        self._last: dict[str, datetime] = {}
        self.appended: dict[str, list] = {}

    async def last_custody_charge_at(self, account_id: str) -> datetime | None:
        return self._last.get(account_id)

    async def append_custody_fee(self, **kwargs) -> dict:
        account_id = kwargs["account_id"]
        self.appended.setdefault(account_id, []).append(kwargs)
        # Guard duradero: tras cobrar, se recuerda el periodo para impedir re-cobro.
        self._last[account_id] = datetime.now(UTC)
        return {"id": "ledger-1", "executed_at": "t"}


class _FakeObligationRepo:
    """Obligación multi-periodo por (cuenta, periodo) — patrón del repo dedicado."""

    def __init__(self) -> None:
        # account_id -> lista de {period, status, outstanding, ...} ordenadas ASC.
        self.rows: dict[str, list[dict]] = {}
        self.upserted: list[dict] = []

    async def get_pending_by_account(self, account_id: str):
        return [
            dict(r)
            for r in sorted(self.rows.get(account_id, []), key=lambda r: r["period"])
            if r["status"] == "PENDING"
        ]

    async def upsert(self, **kwargs) -> dict:
        self.upserted.append(kwargs)
        account_obligations = self.rows.setdefault(kwargs["account_id"], [])
        for idx, existing in enumerate(account_obligations):
            if existing["period"] == kwargs["period"]:
                account_obligations[idx] = dict(kwargs)
                return dict(kwargs)
        account_obligations.append(dict(kwargs))
        return dict(kwargs)


def _settings_with_custody(pct: float | None):
    # presetId custom para respetar custodyAnnualPct tal cual (con standard_es el
    # parser ignora el dict y fija 0.2 — ver settings_from_dict).
    return settings_from_dict(
        {
            "commission": {"presetId": "custom", "custodyAnnualPct": pct},
            "tax": {"costBasisMethod": "FIFO"},
        }
    )


def _account(account_id: str, status: str, pct: float | None):
    return SimpleNamespace(
        id=account_id,
        status=status,
        currency="EUR",
        settings=_settings_with_custody(pct),
    )


def _build(accounts: list, *, cash: float = 100.0, equity: float = 10_000.0):
    # equity 10_000 * 0.2% = fee 20.0.
    account_repo = _FakeAccountRepo(accounts)
    portfolio_repo = _FakePortfolioRepo(cash=cash, equity=equity)
    ledger = _FakeLedger()
    obligation = _FakeObligationRepo()
    job = RunCustodyJob(
        account_repo,  # type: ignore[arg-type]
        portfolio_repo,
        ledger,
        obligation,
    )
    return job, ledger, portfolio_repo, obligation, account_repo


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


def test_job_solo_procesa_cuentas_activas() -> None:
    """La cuenta cerrada se excluye: scanned==1, solo se procesa la activa."""
    active = _account("acc-active", status="active", pct=0.2)
    closed = _account("acc-closed", status="closed", pct=0.2)
    job, ledger, _, obligation, _ = _build([active, closed])

    result = asyncio_run(job.execute())

    assert result["scanned"] == 1
    assert result["applied_complete"] == 1
    assert [r["accountId"] for r in result["results"]] == ["acc-active"]
    # Si la cerrada se hubiera procesado, habría ledger/obligación para ella.
    assert ledger.appended.get("acc-closed") is None
    assert obligation.rows.get("acc-closed") is None


def test_job_cuenta_con_saldo_cobra_completo() -> None:
    """cash >= fee → APPLIED (applied_complete)."""
    job, ledger, portfolio_repo, obligation, _ = _build(
        [_account("acc-1", "active", 0.2)], cash=100.0, equity=10_000.0
    )

    result = asyncio_run(job.execute())

    assert result["scanned"] == 1
    assert result["applied_complete"] == 1
    assert result["pending"] == 0
    assert len(ledger.appended["acc-1"]) == 1
    assert portfolio_repo._cash == pytest.approx(80.0)
    assert obligation.rows["acc-1"][0]["status"] == "APPLIED"


def test_job_cuenta_con_saldo_insuficiente_queda_pending() -> None:
    """cash < fee → costo no escrito, obligación PENDING (pending)."""
    # equity 10_000 → fee 20.0; cash = 10 < 20.
    job, ledger, portfolio_repo, obligation, _ = _build(
        [_account("acc-1", "active", 0.2)], cash=10.0, equity=10_000.0
    )

    result = asyncio_run(job.execute())

    assert result["scanned"] == 1
    assert result["pending"] == 1
    assert result["applied_complete"] == 0
    assert ledger.appended.get("acc-1") is None
    assert portfolio_repo.deduct_calls == []
    assert portfolio_repo._cash == pytest.approx(10.0)
    assert obligation.rows["acc-1"][0]["status"] == "PENDING"
    assert obligation.rows["acc-1"][0]["outstanding"] == pytest.approx(20.0 - 10.0)


def test_job_cuenta_sin_custodia_skipped() -> None:
    """custodyAnnualPct None → ApplyCustodyFees devuelve False → skipped."""
    job, ledger, _, obligation, _ = _build(
        [_account("acc-1", "active", None)], cash=100.0, equity=10_000.0
    )

    result = asyncio_run(job.execute())

    assert result["scanned"] == 1
    assert result["skipped"] == 1
    assert result["applied_complete"] == 0
    assert ledger.appended.get("acc-1") is None
    assert obligation.rows.get("acc-1") is None


def test_job_idempotente_doble_invocacion() -> None:
    """Segunda pasada no re-cobra: guard duradero de ledger → applied==False → skipped."""
    job, ledger, portfolio_repo, obligation, _ = _build(
        [_account("acc-1", "active", 0.2)], cash=100.0, equity=10_000.0
    )

    first = asyncio_run(job.execute())
    second = asyncio_run(job.execute())

    assert first["applied_complete"] == 1
    assert first["skipped"] == 0
    assert second["applied_complete"] == 0
    assert second["skipped"] == 1
    # Cobrado exactamente una vez (no duplicado por la 2ª pasada).
    assert len(ledger.appended["acc-1"]) == 1
    assert portfolio_repo._cash == pytest.approx(80.0)
    applied_upserts = [
        u for u in obligation.upserted if u["status"] == "APPLIED"
    ]
    assert len(applied_upserts) == 1
    assert applied_upserts[0]["outstanding"] == pytest.approx(0.0)
