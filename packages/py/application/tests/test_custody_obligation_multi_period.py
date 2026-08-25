"""R-11 C1 / R-10.6 — custodia MULTI-periodo: no se pierde la obligación PENDING.

Escenarios (fakes, sin DB) sobre la semántica nueva de ``ApplyCustodyFees`` y
``RunCustodyJob`` con ``UNIQUE(account_id, period)``:
- Un PENDING de un año anterior y el cargo del periodo actual COEXISTEN: la liquidación
  de deuda no sobrescribe el PENDING histórico (antes con PK ``account_id`` el upsert
  pisaba la fila y se perdía la deuda).
- La liquidación de PENDING antiguo se hace PRIMERO antes de cobrar el periodo actual:
  si al llegar al nuevo periodo ya hay cash, el PENDING antiguo se salda (APPLIED) y
  luego se genera el cargo del periodo nuevo.
- El job de custodia reporta ``pending`` cuando queda alguna obligación PENDING.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from bolsa_domain.account_settings import settings_from_dict

from bolsa_application.accounts import ApplyCustodyFees
from bolsa_application.custody_job import RunCustodyJob
from bolsa_application.risk_runtime import (
    clear_custody_memory_for_tests,
    clear_idempotency_memory_for_tests,
)


def _now() -> datetime:
    return datetime.now(UTC)


def _current_period() -> str:
    return _now().strftime("%Y")


class _FakeObligationRepo:
    """Repo fake multi-periodo: filas por (account_id, period)."""

    def __init__(self, seeded: dict | None = None) -> None:
        self.rows: dict[tuple[str, str], dict] = {}
        if seeded is not None:
            self.rows[(seeded["account_id"], seeded["period"])] = dict(seeded)
        self.upserted: list[dict] = []

    @staticmethod
    def _as_object(row: dict) -> SimpleNamespace:
        # El repo real devuelve ``CustodyObligation`` (acceso por atributo).
        return SimpleNamespace(**row)

    async def get_pending_by_account(self, account_id: str):
        return [
            self._as_object(r)
            for k, r in sorted(self.rows.items())
            if k[0] == account_id and r["status"] == "PENDING"
        ]

    async def upsert(self, **kwargs) -> dict:
        self.upserted.append(kwargs)
        key = (kwargs["account_id"], kwargs["period"])
        self.rows[key] = dict(kwargs)
        return dict(kwargs)


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

    async def list_active_accounts(self, *, owner_user_id=None, for_custody_job=False):
        _ = owner_user_id, for_custody_job
        return [SimpleNamespace(id="acc-1", status="active")]

    async def resolve_scope(self, account_id, portfolio_id=None):  # noqa: ARG001
        portfolio = self._portfolios[0]
        account = SimpleNamespace(
            id=account_id,
            currency="EUR",
            settings=_settings_with_custody(0.2),
        )
        return SimpleNamespace(account=account, portfolio=portfolio)


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


def _settings_with_custody(pct: float):
    return settings_from_dict(
        {
            "commission": {"presetId": "custom", "custodyAnnualPct": pct},
            "tax": {"costBasisMethod": "FIFO"},
        }
    )


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


def _pending_seed(account_id: str, period: str) -> dict:
    return {
        "account_id": account_id,
        "period": period,
        "status": "PENDING",
        "outstanding": 400.0,
        "total_fee": 400.0,
    }


def test_pending_anterior_coexiste_con_periodo_actual() -> None:
    """PENDING previo + periodo actual con cash insuficiente → ambas filas coexisten.

    Antes (PK ``account_id``) el upsert del periodo nuevo pisaba la fila y se perdía la
    deuda de 2026; con ``UNIQUE(account_id, period)`` el PENDING previo pervive.
    """
    prior = "prior"
    current = _current_period()
    assert prior != current
    obligation = _FakeObligationRepo(seeded=_pending_seed("acc-1", prior))
    portfolio = SimpleNamespace(id="pf-id", legacy_portfolio_id="pf-legacy", is_default=True)
    scope = SimpleNamespace(
        account=SimpleNamespace(id="acc-1", currency="EUR", settings=_settings_with_custody(0.2)),
        portfolio=portfolio,
    )
    uc = ApplyCustodyFees(
        _FakeAccountRepo([portfolio]),
        _FakePortfolioRepo(cash=0.0, equity=40_000.0),
        _FakeLedger(),
        custody_obligation_repo=obligation,
    )

    assert asyncio_run(uc.execute(scope)) is True

    # El PENDING previo NO se pierde (no fue sobrescrito por el periodo actual).
    prior_row = obligation.rows[("acc-1", prior)]
    assert prior_row["status"] == "PENDING"
    assert prior_row["outstanding"] == pytest.approx(400.0)
    # El periodo actual genera SU propio PENDING (cash 0 < fee 80).
    current_row = obligation.rows.get(("acc-1", current))
    assert current_row is not None
    assert current_row["status"] == "PENDING"
    assert current_row["outstanding"] == pytest.approx(80.0)
    # No hay cargo ledger (cash 0 → no se descuenta ni se escribe ledger).
    assert obligation.upserted


def test_liquida_pending_anterior_antes_de_cobrar_periodo_actual() -> None:
    """Al llegar el nuevo periodo con cash, se salda el PENDING antiguo PRIMERO.

    La deuda de 2026 se liquidó (APPLIED, ledger ``custody-2026``) antes de generar el
    cargo de 2027 (ledger ``custody-2027``); Σ ledger == Σ cash en todo estado.
    """
    prior = "prior"
    current = _current_period()
    obligation = _FakeObligationRepo(seeded=_pending_seed("acc-1", prior))
    portfolio = SimpleNamespace(id="pf-id", legacy_portfolio_id="pf-legacy", is_default=True)
    scope = SimpleNamespace(
        account=SimpleNamespace(id="acc-1", currency="EUR", settings=_settings_with_custody(0.2)),
        portfolio=portfolio,
    )
    portfolio_repo = _FakePortfolioRepo(cash=1000.0, equity=40_000.0)
    ledger = _FakeLedger()
    uc = ApplyCustodyFees(
        _FakeAccountRepo([portfolio]),
        portfolio_repo,
        ledger,
        custody_obligation_repo=obligation,
    )

    assert asyncio_run(uc.execute(scope)) is True

    # El PENDING previo quedó APPLIED/outstanding 0 (deuda saldada primero).
    prior_row = obligation.rows[("acc-1", prior)]
    assert prior_row["status"] == "APPLIED"
    assert prior_row["outstanding"] == pytest.approx(0.0)
    # El periodo actual también quedó APPLIED (cash 600 >= fee 80).
    current_row = obligation.rows[("acc-1", current)]
    assert current_row["status"] == "APPLIED"
    assert current_row["outstanding"] == pytest.approx(0.0)
    # Orden: primero custodia del pendiente (año previo), luego el periodo actual.
    refs = [a["reference_id"] for a in ledger.appended]
    assert refs == [f"custody-{prior}", f"custody-{current}"]
    # Σ ledger == Σ cash: descuentos 400 + 80 = 480 → cash 1000 - 480 = 520.
    assert portfolio_repo._cash == pytest.approx(520.0)


def test_job_reporta_pending_cuando_queda_obligacion_pendiente() -> None:
    """Job de custodia reporta ``pending`` si queda alguna obligación PENDING.

    Cuenta con una PENDING previa y cash insuficiente para saldarla: el periodo actual
    deja otra PENDING → ``get_pending_by_account``>0 → el agregado marca ``pending``.
    """
    prior = "prior"
    current = _current_period()
    assert prior != current
    portfolio = SimpleNamespace(id="pf-id", legacy_portfolio_id="pf-legacy", is_default=True)
    portfolios = [portfolio]
    account_repo = _FakeAccountRepo(portfolios)
    portfolio_repo = _FakePortfolioRepo(cash=50.0, equity=40_000.0)
    ledger = _FakeLedger()
    obligation = _FakeObligationRepo(seeded=_pending_seed("acc-1", prior))
    job = RunCustodyJob(
        account_repo,  # type: ignore[arg-type]
        portfolio_repo,
        ledger,
        obligation,
    )

    result = asyncio_run(job.execute())

    assert result["scanned"] == 1
    assert result["pending"] == 1
    assert result["applied_complete"] == 0
    assert result["results"][0]["outcome"] == "pending"
    # El pendiente previo pervive (solo se descargó lo que el cash permitía).
    assert obligation.rows[("acc-1", prior)]["status"] == "PENDING"
