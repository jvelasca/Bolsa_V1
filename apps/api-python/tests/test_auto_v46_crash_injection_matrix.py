"""V2.46.x (AUTO-6 hardening) — matriz de INYECCIÓN de crash por transición.

La auditoría de ``v2.46-beta`` señaló la limitación central del Crash Day: el broker SIM
liquida TODAS las tranchas de una orden dentro del mismo tick, así que nunca existía una
ventana real ``fill #1 → CRASH → fill #2 pendiente``. El Crash Day certificaba el estado
durable que deja el calendario determinista, no una interrupción EN MEDIO de la
materialización. Esta matriz cierra ese hueco: inyecta la muerte en cada TRANSICIÓN y
exige, tras el reinicio, **exactly-once del efecto financiero**.

Dos capas, cada una con su costura exacta:

CAPA 1 — el efecto financiero (``apply_execution_financial_once``): el crash se modela
dejando la fila en el estado EXACTO en que la deja el proceso muerto (sin terminal), que
es lo que un ``kill -9`` produce de verdad:

* ``CRASH_AFTER_CAPTURED`` — capturada; muere antes de tomar el APPLYING.
* ``CRASH_AFTER_APPLYING`` — ganó el APPLYING y murió antes de materializar (lease del
  dueño caído): el reinicio RECLAMA el lease y aplica.
* ``CRASH_AFTER_APPLIED`` — el terminal APPLIED es durable: el reinicio NO vuelve a aplicar.
* ``CRASH_AFTER_PARTIAL_FILL`` — la trancha #1 quedó aplicada; muere con la #2 en vuelo;
  el reinicio materializa SOLO la #2 y el total es la suma, nunca el doble.

CAPA 2 — la emisión AUTO (el worker real, stores durables compartidos): el crash se inyecta
con una excepción ``BaseException`` en la costura (los ``except Exception`` del worker NO
la capturan, igual que no capturan un ``kill -9``):

* ``CRASH_AFTER_DECISION`` — la decisión se tomó y el claim NO llegó a persistir.
* ``CRASH_AFTER_CLAIM`` / ``CRASH_AFTER_RESERVATION`` — el claim se ganó y la reserva es
  durable, pero no se emitió orden.

``CRASH_AFTER_ORDER_INTENT`` (la identidad de salida) ya está certificado por
``test_auto_v44_exit_crash_matrix.py`` (C1/C2/C3) y NO se duplica aquí.

Hermético: sin PG, sin red, reloj y precios deterministas.
"""

from __future__ import annotations

import pytest

from bolsa_application.auto_v2_entry import V2_ENGINE_ENV
from bolsa_application.execution_event import (
    ExecutionEvent,
    InMemoryExecutionEventStore,
    apply_execution_financial_once,
)
from bolsa_application.reservation_store import InMemoryReservationStore
from tests.test_auto_v46_crash_recovery import (
    _buy_once,
    _partial_fill_instrument_id,
    _Stores,
    _worker,
)

ACCOUNT = "acc-crash-injection"


@pytest.fixture
def v46_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """El mismo entorno del camino real del Crash Day (el del worker, no un atajo)."""
    monkeypatch.setenv("AUTO_ENGINE_SIMULATED_VENUE", "paper")
    monkeypatch.setenv("AUTO_SIMULATION_WORKER_ENABLED", "0")
    monkeypatch.setenv(V2_ENGINE_ENV, "1")
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_REGIME", "BULL_TREND")
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_EQUITY", "100000")
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_GOVERNOR", "1")


class _Crash(BaseException):
    """La muerte del proceso: NO deriva de ``Exception``.

    Es deliberado: los ``except Exception`` defensivos del worker (que convierten un fallo
    de store en un veto fail-closed) no deben capturar una muerte real de proceso. Un
    ``kill -9`` tampoco da la oportunidad de ejecutar un ``except``.
    """


# ── CAPA 1 · el efecto financiero (FSM durable) ──────────────────────────────────


class _LedgerEffect:
    """El efecto financiero: idempotente por ``execution_id`` (como el kernel real)."""

    def __init__(self) -> None:
        self.applied: list[str] = []

    async def apply(self, execution: ExecutionEvent) -> bool:
        if execution.execution_id in self.applied:
            return False
        self.applied.append(execution.execution_id)
        return True


def _event(execution_id: str, qty: float = 100.0) -> ExecutionEvent:
    return ExecutionEvent(
        execution_id=execution_id,
        order_id=f"o-{execution_id}",
        venue="paper",
        qty=qty,
        account_id=ACCOUNT,
    )


async def _restart_apply(
    store: InMemoryExecutionEventStore,
    ledger: _LedgerEffect,
    execution: ExecutionEvent,
) -> str:
    """Reinicio: worker NUEVO; ``lease_window_seconds=0`` = el dueño anterior está muerto."""
    return await apply_execution_financial_once(
        store,
        execution=execution,
        apply_finance=ledger.apply,
        owner="w2",
        lease_window_seconds=0,
    )


@pytest.mark.asyncio
async def test_crash_after_captured_applies_exactly_once() -> None:
    """CAPTURED es durable y el proceso muere antes de tomar el APPLYING."""
    store = InMemoryExecutionEventStore()
    ledger = _LedgerEffect()
    event = _event("ev-captured")
    await store.capture(event)
    assert (await store.get(event.execution_id)).status == "CAPTURED"  # type: ignore[union-attr]

    outcome = await _restart_apply(store, ledger, event)
    assert outcome == "applied"
    assert ledger.applied == [event.execution_id]

    # Un segundo reinicio no vuelve a materializar: el terminal es durable.
    again = await _restart_apply(store, ledger, event)
    assert again == "already_applied"
    assert ledger.applied == [event.execution_id]


@pytest.mark.asyncio
async def test_crash_after_applying_reclaims_the_dead_lease_and_applies_once() -> None:
    """APPLYING con dueño caído: el reinicio RECLAMA el lease y materializa UNA vez."""
    store = InMemoryExecutionEventStore()
    ledger = _LedgerEffect()
    event = _event("ev-applying")
    await store.capture(event)
    assert await store.start_apply(event.execution_id, owner="w1") is True
    assert (await store.get(event.execution_id)).status == "APPLYING"  # type: ignore[union-attr]
    # CRASH: el dueño w1 nunca llega a marcar terminal.

    outcome = await _restart_apply(store, ledger, event)
    assert outcome == "applied"
    assert ledger.applied == [event.execution_id]

    again = await _restart_apply(store, ledger, event)
    assert again == "already_applied"
    assert ledger.applied == [event.execution_id]


@pytest.mark.asyncio
async def test_crash_after_applied_has_no_second_effect() -> None:
    """El terminal APPLIED sobrevive: el reinicio devuelve ``already_applied`` sin re-aplicar."""
    store = InMemoryExecutionEventStore()
    ledger = _LedgerEffect()
    event = _event("ev-applied")
    await store.capture(event)
    assert await store.start_apply(event.execution_id, owner="w1") is True
    assert (
        await store.mark_applied(
            event.execution_id, lease_owner="w1", lease_generation=1
        )
        is True
    )
    # CRASH justo después del terminal durable.

    outcome = await _restart_apply(store, ledger, event)
    assert outcome == "already_applied"
    assert ledger.applied == [], "un fill ya APPLIED no se vuelve a materializar"


@pytest.mark.asyncio
async def test_crash_between_partial_fills_never_doubles_the_effect() -> None:
    """Trancha #1 aplicada, #2 en vuelo, crash: el reinicio materializa SOLO la #2."""
    store = InMemoryExecutionEventStore()
    ledger = _LedgerEffect()

    first = _event("fill-1#1", qty=60.0)
    second = _event("fill-1#2", qty=40.0)

    # La trancha #1 se materializa por completo (APPLIED durable).
    assert await _restart_apply(store, ledger, first) == "applied"
    assert ledger.applied == [first.execution_id]

    # La trancha #2 queda CAPTURED+APPLYING sin terminal: CRASH en medio del fill.
    await store.capture(second)
    assert await store.start_apply(second.execution_id, owner="w1") is True

    # REINICIO: converge la #2 una sola vez; la #1 no se repite.
    assert await _restart_apply(store, ledger, second) == "applied"
    assert ledger.applied == [first.execution_id, second.execution_id]

    # El total es la SUMA de las tranchas, nunca el doble.
    assert len(ledger.applied) == 2
    assert sorted(ledger.applied) == sorted([first.execution_id, second.execution_id])


# ── CAPA 2 · la emisión AUTO (worker real sobre stores durables) ──────────────────


class _CrashBeforeClaim(InMemoryReservationStore):
    """Muere ANTES de que el claim se persista (crash tras la decisión)."""

    async def save_claim(self, reservation: object) -> bool:  # type: ignore[override]
        raise _Crash("crash after decision, before claim")


class _CrashAfterClaim(InMemoryReservationStore):
    """El claim se GANA (reserva durable) y el proceso muere a continuación."""

    async def save_claim(self, reservation: object) -> bool:  # type: ignore[override]
        await super().save_claim(reservation)
        raise _Crash("crash after claim, before order emission")


def _live_reservations(store: InMemoryReservationStore) -> list[object]:
    return [row for row in store._rows.values() if row.is_live]  # noqa: SLF001 — lectura de test.


def _buy_order_ids(stores: _Stores) -> set[str]:
    ids: set[str] = set()
    for event in stores.exec_store._rows.values():  # noqa: SLF001 — lectura de test.
        venue_order_id = str(event.venue_order_id or "")
        if "-buy-" in venue_order_id:
            ids.add(venue_order_id)
    return ids


@pytest.mark.asyncio
async def test_crash_after_decision_emits_exactly_one_order_after_restart(
    v46_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """La decisión se tomó pero el claim no persistió: el reinicio emite UNA orden."""
    symbol = _partial_fill_instrument_id("cix-dec")
    monkeypatch.setenv("AUTO_ENGINE_SIMULATED_WATCH", symbol)
    stores = _Stores()
    stores.reservations = _CrashBeforeClaim()

    w1 = _worker(stores, minute=0, decider=_buy_once(symbol))
    with pytest.raises(_Crash):
        await w1.auto_turn()

    assert _live_reservations(stores.reservations) == [], (
        "sin claim durable no hay compromiso de capital"
    )

    # REINICIO: store nuevo (nada quedó a medias) + worker nuevo.
    stores.reservations = InMemoryReservationStore()
    w2 = _worker(stores, minute=1, decider=_buy_once(symbol))
    await w2._v2_reconcile_reservations(startup=True)
    await w2.auto_turn()

    assert len(_live_reservations(stores.reservations)) == 1, "un solo compromiso vivo"
    assert len(_buy_order_ids(stores)) == 1, "una sola orden de compra, no dos"


@pytest.mark.asyncio
async def test_crash_after_claim_does_not_duplicate_the_commitment(
    v46_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """El claim quedó GANADO y durable: el reinicio no apila un segundo compromiso."""
    symbol = _partial_fill_instrument_id("cix-clm")
    monkeypatch.setenv("AUTO_ENGINE_SIMULATED_WATCH", symbol)
    stores = _Stores()
    stores.reservations = _CrashAfterClaim()

    w1 = _worker(stores, minute=0, decider=_buy_once(symbol))
    with pytest.raises(_Crash):
        await w1.auto_turn()

    crashed = _live_reservations(stores.reservations)
    assert len(crashed) == 1, "el claim SÍ quedó persistido antes de la muerte"

    # REINICIO: los mismos datos durables, worker nuevo (RAM nueva).
    stores.reservations = InMemoryReservationStore(seed=tuple(stores.reservations._rows.values()))
    w2 = _worker(stores, minute=1, decider=_buy_once(symbol))
    await w2._v2_reconcile_reservations(startup=True)
    await w2.auto_turn()

    assert len(_live_reservations(stores.reservations)) <= 1, (
        "una identidad, un compromiso: nunca dos reservas vivas del mismo instrumento"
    )
    assert len(_buy_order_ids(stores)) <= 1, (
        "ni dos órdenes: el reinicio converge a un único intent"
    )
