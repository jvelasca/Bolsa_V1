"""AUTO-15 — la costura del contador DURABLE del gate en el worker (racha que sobrevive).

La ventana que cierra la fase, probada por el camino REAL del worker (no por el store suelto): un
proceso acumula fallos consecutivos del sink, se cae, y el proceso NUEVO **sigue viendo la racha**
(``STALE`` con 3), en vez de arrancar a 0 y creerse sano. El control negativo es la mitad de la
prueba: con el mismo journal y los mismos fills, **sin** store durable el reinicio lee 0 y el gate
queda ``OK``. Si el control no existiera, "el gate ve la racha" también pasaría con un gate muerto.

También se fija lo declarado: el fallo se **persiste**, el éxito resetea **sin amplificar** (sin
racha viva no escribe), la procedencia viaja en el hecho ``sinkFailuresDurable``, y un store que
falla **no se disfraza** de persistencia (la racha queda en el proceso y se declara).
"""

from __future__ import annotations

import asyncio
import logging
from types import SimpleNamespace
from typing import Any

import pytest

from bolsa_analytics.cognitive.auto_adaptive import (
    ADAPTIVE_POLICY_VERSION,
    AdaptivePlan,
    AllocationPlan,
    RotationDecision,
    RotationPlan,
)
from bolsa_analytics.cognitive.auto_adaptive_data_gate import (
    DATA_GATE_OK,
    DATA_GATE_STALE,
)
from bolsa_api.background.auto_simulation_worker import AutoSimulationWorker
from bolsa_application.adaptive_gate_store import (
    AdaptiveGateState,
    InMemoryAdaptiveGateStore,
)
from bolsa_application.auto_adaptive_recovery import (
    ADAPTIVE_STATE_WINDOW_DEFAULT,
    AdaptiveStateReading,
    adaptive_state_unread,
    read_adaptive_state,
)
from bolsa_domain.entities.cognitive_artifacts import DecisionJournalEntryRecord

_ACCOUNT = "acc-1"
_ENGINE = "auto-sim"
_T0 = "2026-09-22T10:00:00Z"
_T_PLUS_10 = "2026-09-22T10:10:00Z"
#: Régimen juzgable: evita que el hueco de régimen (``regime_absent``) ensucie la comparación.
_REGIME = "BULL_TREND"
_FLOOR = 0.35
_MIN_PAUSE = 3


def _run(coro: Any) -> Any:
    return asyncio.run(coro)


class _Clock:
    """Reloj mínimo: ``_v2_instant`` solo llama a ``strftime`` con el formato ISO-UTC."""

    def __init__(self, instant: str) -> None:
        self._instant = instant

    def strftime(self, _fmt: str) -> str:
        return self._instant


class _Journal:
    """Sink+lector de mentira sobre el MISMO material: escribe filas y las reconstruye de verdad."""

    def __init__(self) -> None:
        self.entries: list[DecisionJournalEntryRecord] = []
        self.reads = 0

    async def sink(self, entry: DecisionJournalEntryRecord) -> None:
        self.entries.append(entry)

    async def reader(self, _account_id: str | None) -> AdaptiveStateReading:
        self.reads += 1
        return read_adaptive_state(
            list(self.entries),
            min_pause_cycles=_MIN_PAUSE,
            running_policy_version=ADAPTIVE_POLICY_VERSION,
            window=ADAPTIVE_STATE_WINDOW_DEFAULT,
        )


class _FlakySink:
    """Sink que falla las primeras ``fail_for`` escrituras y luego escribe de verdad."""

    def __init__(self, journal: _Journal, *, fail_for: int) -> None:
        self._journal = journal
        self._remaining = fail_for
        self.failures = 0
        self.successes = 0

    async def __call__(self, entry: Any) -> None:
        if self._remaining > 0:
            self._remaining -= 1
            self.failures += 1
            raise RuntimeError("journal caído")
        await self._journal.sink(entry)
        self.successes += 1


class _CountingStore(InMemoryAdaptiveGateStore):
    """Store in-memory que CUENTA lo que le piden, para probar que con el flag OFF no se le toca."""

    def __init__(self, seed: tuple[AdaptiveGateState, ...] = ()) -> None:
        super().__init__(seed)
        self.loads = 0
        self.failures_recorded = 0
        self.successes_recorded = 0

    async def load(self, account_id: str, engine_id: str) -> AdaptiveGateState | None:
        self.loads += 1
        return await super().load(account_id, engine_id)

    async def record_failure(
        self, account_id: str, engine_id: str, *, at: str | None = None
    ) -> int:
        self.failures_recorded += 1
        return await super().record_failure(account_id, engine_id, at=at)

    async def record_success(
        self, account_id: str, engine_id: str, *, at: str | None = None
    ) -> int:
        self.successes_recorded += 1
        return await super().record_success(account_id, engine_id, at=at)


class _BrokenStore(InMemoryAdaptiveGateStore):
    """Store que revienta: prueba que el hueco se declara y que la racha no se inventa."""

    async def load(self, account_id: str, engine_id: str) -> AdaptiveGateState | None:
        raise RuntimeError("estado durable caído")

    async def record_failure(
        self, account_id: str, engine_id: str, *, at: str | None = None
    ) -> int:
        raise RuntimeError("estado durable caído")


def _plan(
    *, paused: tuple[str, ...] = ("v42",), versions: tuple[str, ...] = ("v42",)
) -> AdaptivePlan:
    """Plan Adaptive mínimo con el contrato real (el payload no es lo que se prueba aquí)."""
    decisions = tuple(
        RotationDecision(strategy_version=version, active=version not in paused)
        for version in versions
    )
    return AdaptivePlan(
        rotation=RotationPlan(decisions),
        allocation=AllocationPlan({}),
        regime="TREND_UP",
        policy_version=ADAPTIVE_POLICY_VERSION,
    )


def _worker(
    *,
    journal: _Journal | None = None,
    sink: Any | None = None,
    reader: Any | None = None,
    gate_store: Any | None = None,
    enabled: bool = True,
    now: str = _T0,
    failures: int = 0,
) -> AutoSimulationWorker:
    """Worker mínimo por el mismo camino real (sin ``__init__``), con el store del gate inyectado."""
    worker = object.__new__(AutoSimulationWorker)
    worker._account_id = _ACCOUNT
    worker._engine_id = _ENGINE
    worker._adaptive_sink = sink if sink is not None else (journal.sink if journal else None)
    worker._adaptive_reader = reader if reader is not None else (journal.reader if journal else None)
    worker._adaptive_gate_store = gate_store
    worker._v2_adaptive_paused_cycles = {}
    worker._v2_adaptive_reactivated_at = {}
    worker._v2_adaptive_paused_cycles_entered = {}
    worker._v2_adaptive_state_recovered = False
    worker._v2_cycle_trace_reconciled = False
    worker._v2_adaptive_sink_failures = failures
    worker._v2_adaptive_sink_failures_durable = False
    worker._v2_adaptive_sink_last_success_at = None
    worker._v2_adaptive_journal_anchor_age = None
    worker._v2_adaptive_state_reading = None
    worker._v2_tunables = SimpleNamespace(
        adaptive_enabled=enabled,
        adaptive_win_rate_floor=_FLOOR,
        regime_override=None,
    )
    worker._time = _Clock(now)
    return worker


def _gate(worker: AutoSimulationWorker) -> Any:
    """La lectura del gate por el MISMO método del worker que usa el tick."""
    return worker._v2_adaptive_data_gate(
        report=SimpleNamespace(by_strategy=()),
        confidence=SimpleNamespace(by_strategy=None, recent_available=None),
        regime=_REGIME,
    )


# ── La racha duradera: el reinicio no la olvida (con su control negativo) ────────────


def test_a_measured_streak_survives_the_restart_and_the_gate_still_sees_it() -> None:
    """3 fallos ⇒ ``STALE``; el proceso nuevo LEE la racha y sigue en ``STALE``, no en ``OK``."""
    store = InMemoryAdaptiveGateStore()
    first = _worker(sink=_FlakySink(_Journal(), fail_for=3), gate_store=store)
    for _ in range(3):
        _run(first._v2_journal_adaptive_recommendation(_plan()))

    assert first._v2_adaptive_sink_failures == 3
    row = _run(store.load(_ACCOUNT, _ENGINE))
    assert row is not None and row.sink_failures == 3

    restarted = _worker(gate_store=store, now=_T_PLUS_10)
    _run(restarted._v2_recover_adaptive_gate_streak())

    assert restarted._v2_adaptive_sink_failures == 3
    assert restarted._v2_adaptive_sink_failures_durable is True
    reading = _gate(restarted)
    assert reading.status == DATA_GATE_STALE
    assert reading.as_dict()["sinkFailuresDurable"] is True


def test_without_the_durable_store_the_restart_reads_zero_the_control() -> None:
    """CONTROL NEGATIVO: mismos fallos y mismo journal, sin store ⇒ el reinicio lee 0 y el gate ``OK``.

    Sin este control, "el gate ve la racha" pasaría también con un gate muerto que nunca mira nada.
    """
    journal = _Journal()
    first = _worker(sink=_FlakySink(journal, fail_for=3))
    for _ in range(3):
        _run(first._v2_journal_adaptive_recommendation(_plan()))
    assert first._v2_adaptive_sink_failures == 3

    restarted = _worker(journal=journal, now=_T_PLUS_10)
    _run(restarted._v2_recover_adaptive_gate_streak())

    assert restarted._v2_adaptive_sink_failures == 0
    assert restarted._v2_adaptive_sink_failures_durable is False
    assert _gate(restarted).status == DATA_GATE_OK


def test_a_publication_after_the_restart_resets_the_durable_streak() -> None:
    """La racha durable se CURA publicando: el reset llega al store, no solo a la memoria."""
    store = InMemoryAdaptiveGateStore()
    journal = _Journal()
    first = _worker(sink=_FlakySink(journal, fail_for=2), gate_store=store)
    _run(first._v2_journal_adaptive_recommendation(_plan()))
    _run(first._v2_journal_adaptive_recommendation(_plan()))

    restarted = _worker(journal=journal, gate_store=store, now=_T_PLUS_10)
    _run(restarted._v2_recover_adaptive_gate_streak())
    assert restarted._v2_adaptive_sink_failures == 2

    _run(restarted._v2_journal_adaptive_recommendation(_plan()))

    row = _run(store.load(_ACCOUNT, _ENGINE))
    assert restarted._v2_adaptive_sink_failures == 0
    assert row is not None and row.sink_failures == 0
    assert row.last_success_at == _T_PLUS_10
    # El rastro del fallo no se borra: "cuándo empezó" sigue siendo auditable tras curarse.
    assert row.last_failure_at is not None


def test_the_reset_does_not_amplify_writes_when_there_is_no_streak() -> None:
    """Sin racha viva, publicar NO escribe en el store: el camino sano no paga una fila por tick."""
    store = _CountingStore()
    worker = _worker(journal=_Journal(), gate_store=store)

    _run(worker._v2_journal_adaptive_recommendation(_plan()))
    _run(worker._v2_journal_adaptive_recommendation(_plan()))

    assert store.successes_recorded == 2
    # Se pidió el reset las dos veces, pero la tabla sigue VACÍA: no se creó fila.
    assert len(store) == 0


def test_with_the_flag_off_the_durable_streak_is_not_read() -> None:
    """Con el flag OFF no hay I/O nuevo: ni se lee la racha durable ni se toca el contador."""
    store = _CountingStore()
    worker = _worker(gate_store=store, enabled=False, failures=2)

    _run(worker._v2_recover_adaptive_state())

    assert store.loads == 0
    assert worker._v2_adaptive_sink_failures == 2


# ── Lo declarado: la procedencia viaja, y un store roto no se disfraza ───────────────


def test_the_provenance_of_the_streak_is_declared_in_the_gate_reading() -> None:
    """El gate del tick declara si la racha es durable: sin store, NO se afirma durable."""
    store = InMemoryAdaptiveGateStore(
        (AdaptiveGateState(account_id=_ACCOUNT, engine_id=_ENGINE, sink_failures=1),)
    )
    with_store = _worker(gate_store=store)
    _run(with_store._v2_recover_adaptive_gate_streak())
    hermetic = _worker(failures=1)

    assert _gate(with_store).as_dict()["sinkFailuresDurable"] is True
    assert _gate(hermetic).as_dict()["sinkFailuresDurable"] is False
    # La procedencia no gradúa: la MISMA racha da el MISMO estado por los dos caminos.
    assert _gate(with_store).status == _gate(hermetic).status


def test_an_unreadable_store_declares_the_gap_and_does_not_invent_a_streak(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Store roto en el arranque: la racha arranca en 0 y se DECLARA; no se finge ni salud ni fallo."""
    worker = _worker(gate_store=_BrokenStore())

    with caplog.at_level(logging.ERROR):
        _run(worker._v2_recover_adaptive_state())

    assert worker._v2_adaptive_sink_failures == 0
    assert worker._v2_adaptive_sink_failures_durable is False
    assert "UNREAD" in caplog.text


def test_a_store_that_cannot_persist_keeps_the_streak_in_process_and_declares_it(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Un store roto no pierde la racha del proceso: cae al contador local y lo declara."""
    worker = _worker(sink=_FlakySink(_Journal(), fail_for=1), gate_store=_BrokenStore())

    with caplog.at_level(logging.ERROR):
        _run(worker._v2_journal_adaptive_recommendation(_plan()))

    assert worker._v2_adaptive_sink_failures == 1
    assert worker._v2_adaptive_sink_failures_durable is False
    assert "NOT durable" in caplog.text


def test_the_recovery_of_the_streak_is_declared_in_the_log(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """La racha sembrada se publica con su campo, para que el arranque sea auditable."""
    store = InMemoryAdaptiveGateStore(
        (AdaptiveGateState(account_id=_ACCOUNT, engine_id=_ENGINE, sink_failures=2),)
    )
    worker = _worker(gate_store=store, reader=adaptive_state_unread)

    with caplog.at_level(logging.INFO):
        _run(worker._v2_recover_adaptive_state())

    assert "'sinkFailures': 2" in caplog.text
