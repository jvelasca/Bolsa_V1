"""V2.46.x (AUTO-6 hardening) — recuperación DURABLE de la parada dura ante un crash.

La auditoría de ``v2.46-beta`` dejó este escenario como el único P0 abierto de la parada
dura: el Crash Day certificaba ``BUY parcial + RISK_OFF + time_exit``, pero **no**
``HARD KILL + CRASH + RESTART``. El código durable ya existía (``auto_kill_state`` +
``_v2_load_kill_state`` en el arranque); lo que faltaba era el golden test que demuestre la
secuencia completa sobre la costura real:

    T0  AUTO activo
    T1  un PRODUCTOR real activa el HALT (reconciliación no medible con reservas vivas)
    T2  el HALT queda persistido
    T3  CRASH (la RAM se pierde: se abandona el worker)
    T4  RESTART (worker NUEVO sobre los MISMOS stores durables)
    T5  la parada se RESTAURA: NO ENTRY; la salida protectora SÍ se autoriza
    T6  liberar exige ``reconciliation_id``; con él, RUNNING

Hermético: sin PG, sin red. La muerte se modela como lo que es —pérdida de RAM—: se
construye un worker nuevo sobre los mismos stores durables (mismo patrón que
``test_auto_v44_exit_crash_matrix.py``, del que se reutilizan los helpers).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from bolsa_analytics.cognitive.portfolio_reservation import build_reservation
from bolsa_application.auto_v2_entry import V2_ENGINE_ENV
from bolsa_application.decision_contract import DecisionPackage
from bolsa_application.execution_event import InMemoryExecutionEventStore
from bolsa_application.kill_switch_store import InMemoryKillSwitchStore, KillState
from tests.test_auto_v44_exit_crash_matrix import (
    ACCOUNT_ID,
    ENGINE_ID,
    _hold,
    _restart,
    _seed_buy_position,
    _Stores,
)


@pytest.fixture
def v2_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """El mismo entorno del camino real (``auto_turn``), no un atajo de test."""
    monkeypatch.setenv("AUTO_ENGINE_SIMULATED_WATCH", "AAA")
    monkeypatch.setenv("AUTO_ENGINE_SIMULATED_VENUE", "paper")
    monkeypatch.setenv("AUTO_SIMULATION_WORKER_ENABLED", "0")
    monkeypatch.setenv(V2_ENGINE_ENV, "1")
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_REGIME", "BULL_TREND")
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_EQUITY", "100000")
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_GOVERNOR", "1")


class _UnreadableAppliedStore(InMemoryExecutionEventStore):
    """El listado de fills materializados NO se puede leer.

    Es un productor REAL de la parada dura: ``read_applied_fill_facts`` degrada a
    ``UNKNOWN``, de modo que con reservas VIVAS el libro de compromiso no es medible y
    ``_v2_reconcile_reservations`` activa ``RECONCILIATION_FAILURE`` (no un veto blando).
    """

    async def list_applied(
        self,
        account_id: str | None,
        *,
        limit: int = 1000,
    ) -> list[Any]:
        raise RuntimeError("execution_events unreadable")


def _buy() -> Any:
    def _d(symbol: str) -> DecisionPackage:
        return DecisionPackage(action="BUY", instrument_id=symbol, quantity=10)

    return _d


async def _seed_live_reservation(
    stores: _Stores, *, reservation_id: str = "RES-hardkill-live"
) -> None:
    """Una reserva de compra VIVA: hay capital comprometido que no se pudo reconciliar."""
    await stores.reservations.save(
        build_reservation(
            reservation_id=reservation_id,
            account_id=ACCOUNT_ID,
            tick_id="2026-09-15T09:00:00Z",
            instrument_id="AAA",
            side="buy",
            sector="tech",
            quantity=100,
            entry=100.0,
            created_at="2026-09-15T09:00:00Z",
        )
    )


@pytest.mark.asyncio
async def test_the_reconciliation_failure_producer_persists_a_halt_across_a_crash(
    v2_env: None,
) -> None:
    """Un productor REAL deja el HALT durable; tras un crash el reinicio lo RESTAURA."""
    stores = _Stores()
    stores.exec_store = _UnreadableAppliedStore()
    await _seed_live_reservation(stores)

    w1 = _restart(stores, minute=0)
    w1._account_id = ACCOUNT_ID
    w1._engine_id = ENGINE_ID
    await w1._v2_reconcile_reservations(startup=True)

    assert w1._v2_kill_switch_halted() is True, "la reconciliación rota para el sistema"

    state = await stores.kill_state.load(ACCOUNT_ID, ENGINE_ID)
    assert state is not None and state.engaged is True
    assert state.reason == "RECONCILIATION_FAILURE"
    assert state.engagement_id, "la activación tiene identidad auditable"

    # T3 — CRASH: la RAM se pierde. T4 — RESTART: worker NUEVO sobre los mismos stores.
    w2 = _restart(stores, minute=1)
    assert w2._v2_kill_switch_halted() is False, "el worker nuevo nace sin memoria del HALT"

    await w2._v2_load_kill_state()

    assert w2._v2_kill_switch_halted() is True, "T5: el HALT se RESTAURA al arrancar"
    assert w2._v2_kill_switch.reason == "RECONCILIATION_FAILURE"
    assert w2._v2_kill_switch.engagement_id == state.engagement_id, (
        "la identidad de la activación original sobrevive al reinicio"
    )

    w2._decider = _buy()
    await w2.auto_turn()
    assert w2.open_symbols == (), "con la parada restaurada NO se abre riesgo nuevo"


@pytest.mark.asyncio
async def test_a_restored_halt_blocks_entry_but_not_the_protective_exit(
    v2_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """La parada veta aperturas, pero nunca bloquea una salida protectora autorizada."""
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_EQUITY", "84000")  # RISK_OFF: cierre protector
    stores = _Stores()
    await _seed_buy_position(
        stores, execution_id="buy-hardkill", qty=Decimal("200"), price=Decimal("100")
    )

    w1 = _restart(stores, minute=0)
    w1._account_id = ACCOUNT_ID
    w1._engine_id = ENGINE_ID
    await w1.engage_kill_switch_durable(
        "RECONCILIATION_FAILURE", at="2026-09-15T09:00:00Z"
    )

    w2 = _restart(stores, minute=1)
    await w2._v2_load_kill_state()
    assert w2._v2_kill_switch_halted() is True
    await w2.readopt_positions()

    w2._decider = _buy()
    await w2.auto_turn()

    assert w2.open_symbols == (), "ninguna apertura mientras el HALT esté activo"
    assert w2._open.get("AAA", Decimal("0")) == 0, (
        "la salida protectora SÍ se autoriza: el HALT no deja al sistema atrapado"
    )


@pytest.mark.asyncio
async def test_release_requires_a_reconciliation_id_and_converges_to_running(
    v2_env: None,
) -> None:
    """Solo una reconciliación explícita devuelve el sistema a RUNNING, y queda persistida."""
    stores = _Stores()
    w1 = _restart(stores, minute=0)
    w1._account_id = ACCOUNT_ID
    w1._engine_id = ENGINE_ID
    await w1.engage_kill_switch_durable(
        "RECONCILIATION_FAILURE", at="2026-09-15T09:00:00Z"
    )

    assert (
        await w1.release_kill_switch_durable(reconciliation_ok=True, reconciliation_id=None)
        is False
    )
    assert w1._v2_kill_switch_halted() is True, "sin reconciliation_id NO se levanta"

    assert (
        await w1.release_kill_switch_durable(
            reconciliation_ok=True, reconciliation_id="recon-hardkill-77"
        )
        is True
    )
    assert w1._v2_kill_switch_halted() is False

    state = await stores.kill_state.load(ACCOUNT_ID, ENGINE_ID)
    assert state is not None
    assert state.engaged is False
    assert state.release_reconciliation_id == "recon-hardkill-77"

    # El reinicio NO revive la parada: RUNNING es el estado convergido.
    w2 = _restart(stores, minute=1)
    await w2._v2_load_kill_state()
    assert w2._v2_kill_switch_halted() is False

    w2._decider = _hold()
    await w2.auto_turn()
    assert w2._v2_kill_switch_halted() is False


@pytest.mark.asyncio
async def test_a_durable_release_from_another_process_lifts_a_live_halt(
    v2_env: None,
) -> None:
    """Un HALT VIVO se levanta con una liberación durable POSTERIOR (vía operador/API).

    Es la vía por la que la API levanta la parada de un worker que corre en OTRO proceso:
    escribe la liberación con su ``reconciliation_id`` y el worker la adopta en el
    siguiente turno, sin reiniciarse.
    """
    stores = _Stores()
    w = _restart(stores, minute=0)
    w._account_id = ACCOUNT_ID
    w._engine_id = ENGINE_ID
    await w.engage_kill_switch_durable(
        "RECONCILIATION_FAILURE", at="2026-09-15T09:00:00Z"
    )
    assert w._v2_kill_switch_halted() is True

    # Otro proceso (la API) escribe la liberación durable, más NUEVA que la activación.
    await stores.kill_state.save(
        KillState(
            account_id=ACCOUNT_ID,
            engine_id=ENGINE_ID,
            engaged=False,
            reengagements=1,
            released_at="2026-09-15T09:05:00Z",
            release_actor="operator",
            release_reconciliation_id="recon-operator-1",
            updated_at="2026-09-15T09:05:00Z",
        )
    )

    await w._v2_load_kill_state()
    assert w._v2_kill_switch_halted() is False, (
        "una liberación durable posterior levanta el HALT vivo"
    )


@pytest.mark.asyncio
async def test_a_stale_durable_release_does_not_lift_a_newer_halt(
    v2_env: None,
) -> None:
    """Una liberación MÁS ANTIGUA que el halt local no lo levanta (la re-activación manda)."""
    stores = _Stores()
    stores.kill_state = InMemoryKillSwitchStore(
        seed=(
            KillState(
                account_id=ACCOUNT_ID,
                engine_id=ENGINE_ID,
                engaged=False,
                reengagements=1,
                released_at="2026-09-15T09:00:00Z",
                release_actor="operator",
                release_reconciliation_id="recon-old",
                updated_at="2026-09-15T09:00:00Z",
            ),
        )
    )
    w = _restart(stores, minute=0)
    w._account_id = ACCOUNT_ID
    w._engine_id = ENGINE_ID
    # Latch LOCAL posterior, sin persistir: la fila durable sigue siendo el release viejo.
    w.engage_kill_switch("RECONCILIATION_FAILURE", at="2026-09-15T09:10:00Z")
    assert w._v2_kill_switch_halted() is True

    await w._v2_load_kill_state()
    assert w._v2_kill_switch_halted() is True, (
        "un release ANTERIOR al halt no puede levantarlo"
    )
