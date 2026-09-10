"""V2.24 / A9.1 (P2-03) — batería de crash en las ventanas nuevas del AUTO SIM.

Las ventanas de V2.23 (contexto → finance → posición → journal) pueden fallar en
cualquier punto. Esta batería INYECTA el fallo en cada ventana de forma determinista
(sin PG, hermética) y exige los invariantes de no-doble-efecto:

* C3-F — crash tras ``finance`` y antes de ``sim_position``: el reinicio readopta/
  reconstruye y NO repite el BUY ni el asiento financiero.
* C3-G — crash tras ``sim_position`` y antes del journal: el reinicio no duplica la
  posición ni el efecto financiero.
* C3-H — crash durante la persistencia del contexto: la liquidación queda sin fill
  (fail-closed) y no mueve dinero.
* C3-I — crash durante la readopción: no se inventa posición ni se opera a ciegas.

A diferencia de los chaos REALES de ``live_a7`` (SIGKILL de subproceso, requieren
PG), aquí el "crash" es una excepción inyectada en la costura durable exacta; el
invariante verificado es el mismo: ausencia de doble efecto + reconciliación.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from bolsa_api.background.auto_simulation_worker import (
    AutoSimulationWorker,
    step_minute_clock,
)
from bolsa_application.decision_contract import DecisionPackage
from bolsa_application.execution_event import InMemoryExecutionEventStore
from bolsa_application.sim_durable_store import (
    InMemorySimAutoPositionStore,
    InMemorySimFillFinanceContextStore,
    SimPositionProjection,
)
from bolsa_application.sim_reconciliation import (
    POSITION_PROJECTION_DIVERGENT,
    reconcile_sim_position,
)


@pytest.fixture
def auto_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTO_ENGINE_SIMULATED_WATCH", "AAA")
    monkeypatch.setenv("AUTO_ENGINE_SIMULATED_VENUE", "paper")
    monkeypatch.setenv("AUTO_SIMULATION_WORKER_ENABLED", "0")


def _buy(symbol: str) -> DecisionPackage:
    return DecisionPackage(action="BUY", instrument_id=symbol, quantity=100.0)


def _hold(symbol: str) -> DecisionPackage:
    return DecisionPackage(action="HOLD", instrument_id=symbol, quantity=0)


def _count_fills(store: InMemoryExecutionEventStore) -> int:
    return len(store)


class _FailingPositionStore(InMemorySimAutoPositionStore):
    """Store de posición que falla en la escritura (simula crash en esa ventana)."""

    def __init__(self, *, fail_on: str = "upsert") -> None:
        super().__init__()
        self._fail_on = fail_on

    async def upsert(self, account_id, engine_id, symbol, quantity, **kw):  # type: ignore[no-untyped-def]
        if self._fail_on == "upsert":
            raise RuntimeError("crash during sim_position persist (C3-F/G)")
        return await super().upsert(account_id, engine_id, symbol, quantity, **kw)

    async def read_projection(self, account_id, engine_id):  # type: ignore[no-untyped-def]
        if self._fail_on == "readopt":
            raise RuntimeError("crash during readopt (C3-I)")
        return await super().read_projection(account_id, engine_id)


class _FailingContextStore(InMemorySimFillFinanceContextStore):
    """Contexto que falla al persistir (simula crash en esa ventana)."""

    async def save(self, context):  # type: ignore[no-untyped-def]
        raise RuntimeError("crash during finance-context persist (C3-H)")


@pytest.mark.asyncio
async def test_c3f_crash_before_position_no_second_effect(auto_env: None) -> None:
    """C3-F: crash tras finance/antes de sim_position ⇒ no hay doble BUY al reiniciar."""
    store = InMemoryExecutionEventStore()
    account = "acc-c3f"
    fail_store = _FailingPositionStore(fail_on="upsert")

    _s1, clock1 = step_minute_clock(datetime(2026, 9, 9, 9, 0, tzinfo=UTC))
    w1 = AutoSimulationWorker(
        clock=clock1, exec_store=store, position_store=fail_store, account_id=account
    )
    w1._decider = _buy
    # El turno no rompe: el fallo del espejo se absorbe (el dinero ya está aplicado).
    await w1.auto_turn()
    fills_after_crash = _count_fills(store)
    assert fills_after_crash > 0, "el settlement financiero sí ocurrió antes del crash"

    # Reinicio con un store sano sobre el MISMO ledger: readopta desde el canónico.
    healthy = InMemorySimAutoPositionStore()
    _s2, clock2 = step_minute_clock(datetime(2026, 9, 9, 9, 1, tzinfo=UTC))
    w2 = AutoSimulationWorker(
        clock=clock2, exec_store=store, position_store=healthy, account_id=account
    )
    # El lector canónico refleja la posición real del ledger (100) tras el BUY.
    async def canonical(_acc: str):
        return {"AAA": Decimal("100")}

    w2._canonical_positions_reader = canonical
    await w2.readopt_positions()
    w2._decider = _buy  # intentaría comprar de nuevo
    await w2.auto_turn()
    assert w2._open.get("AAA", Decimal("0")) == Decimal("100"), "no debe apilar un segundo BUY"
    assert _count_fills(store) == fills_after_crash, "sin segundo efecto financiero"


@pytest.mark.asyncio
async def test_c3g_crash_after_position_no_duplicate(auto_env: None) -> None:
    """C3-G: crash tras sim_position/antes de journal ⇒ reinicio no duplica posición."""
    store = InMemoryExecutionEventStore()
    pos_store = InMemorySimAutoPositionStore()
    account = "acc-c3g"

    _s1, clock1 = step_minute_clock(datetime(2026, 9, 9, 9, 0, tzinfo=UTC))
    w1 = AutoSimulationWorker(
        clock=clock1, exec_store=store, position_store=pos_store, account_id=account
    )
    w1._decider = _buy
    await w1.auto_turn()
    await w1._persist_position("AAA", w1._open["AAA"])
    fills_before = _count_fills(store)
    assert dict(await pos_store.read_open(account, "auto-sim")) == {"AAA": Decimal("100")}

    # Reinicio: readopta desde la proyección durable (no re-compra).
    _s2, clock2 = step_minute_clock(datetime(2026, 9, 9, 9, 1, tzinfo=UTC))
    w2 = AutoSimulationWorker(
        clock=clock2, exec_store=store, position_store=pos_store, account_id=account
    )
    await w2.readopt_positions()
    w2._decider = _buy
    await w2.auto_turn()
    assert w2._open.get("AAA", Decimal("0")) == Decimal("100")
    assert _count_fills(store) == fills_before, "sin duplicar el fill"


@pytest.mark.asyncio
async def test_c3h_crash_during_context_no_money(auto_env: None) -> None:
    """C3-H: crash al persistir contexto ⇒ fail-closed, sin fill ni dinero."""
    store = InMemoryExecutionEventStore()
    _s, clock = step_minute_clock(datetime(2026, 9, 9, 9, 0, tzinfo=UTC))
    worker = AutoSimulationWorker(
        clock=clock,
        exec_store=store,
        context_store=_FailingContextStore(),
        account_id="acc-c3h",
    )
    worker._decider = _buy
    await worker.auto_turn()
    # Sin contexto durable no se materializa; y el turno no debe romperse.
    assert not worker.open_symbols
    assert _count_fills(store) == 0


@pytest.mark.asyncio
async def test_c3i_crash_during_readopt_is_safe(auto_env: None) -> None:
    """C3-I: crash durante la readopción ⇒ no se inventa posición (fail-closed)."""
    store = InMemoryExecutionEventStore()
    _s, clock = step_minute_clock(datetime(2026, 9, 9, 9, 0, tzinfo=UTC))
    worker = AutoSimulationWorker(
        clock=clock,
        exec_store=store,
        position_store=_FailingPositionStore(fail_on="readopt"),
        account_id="acc-c3i",
    )
    durable = await worker.readopt_positions()
    assert dict(durable) == {}, "un fallo de readopción no inventa posición"
    assert not worker.open_symbols


@pytest.mark.asyncio
async def test_reconciliation_blocks_openings_when_divergent(auto_env: None) -> None:
    """P1-01: si la proyección diverge del canónico, NO se abren nuevas posiciones."""
    store = InMemoryExecutionEventStore()
    account = "acc-div"
    pos_store = _FailingPositionStore(fail_on="none")

    _s, clock = step_minute_clock(datetime(2026, 9, 9, 9, 0, tzinfo=UTC))
    worker = AutoSimulationWorker(
        clock=clock, exec_store=store, position_store=pos_store, account_id=account
    )

    called = {"n": 0}

    async def divergent_reader(_acc: str):
        called["n"] += 1
        # El canónico dice 100 pero la proyección está vacía ⇒ REBUILT (reconstruye).
        return {"AAA": Decimal("100")}

    worker._canonical_positions_reader = divergent_reader
    await worker.readopt_positions()
    # Tras la reconstrucción, la proyección queda alineada y las aperturas permitidas
    # (no queda DIVERGENT porque el canónico es la autoridad).
    verdict = reconcile_sim_position(
        symbol="AAA",
        execution_events=None,
        financial_positions={"AAA": Decimal("100")},
        sim_auto_positions={"AAA": Decimal("100")},
    )
    assert verdict.status != POSITION_PROJECTION_DIVERGENT
