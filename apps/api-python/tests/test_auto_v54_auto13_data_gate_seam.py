"""AUTO-13 — la costura del Data Gate en el worker (contador de fallos + ancla durable).

Lo que se prueba es la COSTURA del paso 2, no la tabla pura del gate (esa vive en
``packages/py/analytics/tests/test_auto_adaptive_data_gate.py``): que un fallo del sink deje de
ser un renglón de log y pase a ser un hecho CONTADO (consecutivo, con reset en el éxito), y que el
ancla durable de antigüedad del journal se mida del ``asOf`` de la última publicación y **sobreviva
a un reinicio**. Además, la regla que evita el deadlock: la antigüedad sola **no** bloquea; solo
bloquea cuando el propio proceso ha fallado al publicar (corroboración), de modo que un journal
sano tras un hueco largo se cura con su primera escritura y uno muerto se sigue detectando.
"""

from __future__ import annotations

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
    DATA_GATE_BLOCKED,
    DATA_GATE_DEGRADED,
    DATA_GATE_OK,
    DATA_GATE_STALE,
    assess_data_gate,
)
from bolsa_api.background.auto_simulation_worker import AutoSimulationWorker
from bolsa_application.auto_adaptive_recovery import (
    ADAPTIVE_STATE_WINDOW_DEFAULT,
    AdaptiveStateReading,
    read_adaptive_state,
)
from bolsa_domain.entities.cognitive_artifacts import DecisionJournalEntryRecord

_ACCOUNT = "acc-1"
_T0 = "2026-09-22T10:00:00Z"
#: Diez ciclos de evaluación (a la cadencia declarada de 60s) después de ``_T0``.
_T_PLUS_10 = "2026-09-22T10:10:00Z"
_FLOOR = 0.35
_MIN_PAUSE = 3


class _Clock:
    """Reloj mínimo: ``_v2_instant`` solo llama a ``strftime`` con el formato ISO-UTC."""

    def __init__(self, instant: str) -> None:
        self._instant = instant

    def strftime(self, _fmt: str) -> str:
        return self._instant


class _Journal:
    """Sink+lector de mentira sobre el MISMO material: escribe filas y las reconstruye de verdad.

    El lector usa ``read_adaptive_state`` (el módulo real) para que la costura pruebe la
    reconstrucción del ancla (``last_published_at``) y no una promesa a mano.
    """

    def __init__(self, *, fail_sink: bool = False) -> None:
        self.entries: list[DecisionJournalEntryRecord] = []
        self.reads = 0
        self.sink_calls = 0
        self._fail_sink = fail_sink

    async def sink(self, entry: DecisionJournalEntryRecord) -> None:
        self.sink_calls += 1
        if self._fail_sink:
            raise RuntimeError("journal caído")
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
    enabled: bool = True,
    now: str = _T0,
    failures: int = 0,
    anchor: int | None = None,
) -> AutoSimulationWorker:
    worker = object.__new__(AutoSimulationWorker)
    worker._account_id = _ACCOUNT
    worker._engine_id = "auto-sim"
    worker._adaptive_sink = sink if sink is not None else (journal.sink if journal else None)
    worker._adaptive_reader = reader if reader is not None else (journal.reader if journal else None)
    worker._v2_adaptive_paused_cycles = {}
    # AUTO-13 paso 4: la memoria de la rampa arranca vacia (el lector durable la siembra).
    worker._v2_adaptive_reactivated_at = {}
    worker._v2_adaptive_paused_cycles_entered = {}
    worker._v2_adaptive_state_recovered = False
    worker._v2_cycle_trace_reconciled = False
    worker._v2_adaptive_sink_failures = failures
    worker._v2_adaptive_sink_last_success_at = None
    worker._v2_adaptive_journal_anchor_age = anchor
    worker._v2_adaptive_state_reading = None
    worker._v2_tunables = SimpleNamespace(
        adaptive_enabled=enabled,
        adaptive_win_rate_floor=_FLOOR,
        regime_override=None,
    )
    worker._time = _Clock(now)
    return worker


# ── El contador de fallos consecutivos del sink (§21) ───────────────────────────────


@pytest.mark.asyncio
async def test_a_successful_publication_resets_the_streak_and_reanchors() -> None:
    """Publicar bien no solo calla el error: borra la racha y reancla el journal a 0 ciclos."""
    journal = _Journal()
    worker = _worker(journal=journal, failures=2, now=_T0)

    await worker._v2_journal_adaptive_recommendation(_plan())

    assert worker._v2_adaptive_sink_failures == 0
    assert worker._v2_adaptive_sink_last_success_at == _T0
    assert worker._v2_adaptive_journal_anchor_age == 0
    assert len(journal.entries) == 1


@pytest.mark.asyncio
async def test_consecutive_sink_failures_are_counted_and_grade_the_gate() -> None:
    """1 fallo ⇒ ``DEGRADED``; 3 consecutivos ⇒ ``STALE``; un éxito RESETEA la racha."""
    sink = _FlakySink(_Journal(), fail_for=3)
    worker = _worker(sink=sink)

    await worker._v2_journal_adaptive_recommendation(_plan())
    assert worker._v2_adaptive_sink_failures == 1
    assert (
        assess_data_gate(sink_failures=worker._v2_adaptive_sink_failures).status
        == DATA_GATE_DEGRADED
    )

    await worker._v2_journal_adaptive_recommendation(_plan())
    await worker._v2_journal_adaptive_recommendation(_plan())
    assert worker._v2_adaptive_sink_failures == 3
    assert assess_data_gate(sink_failures=3).status == DATA_GATE_STALE

    await worker._v2_journal_adaptive_recommendation(_plan())  # escribe: resetea
    assert worker._v2_adaptive_sink_failures == 0
    assert sink.successes == 1


@pytest.mark.asyncio
async def test_a_success_between_failures_breaks_the_streak() -> None:
    """El contador es CONSECUTIVO: un éxito en medio impide llegar al umbral de ``STALE``."""
    flaky = _FlakySink(_Journal(), fail_for=1)
    worker = _worker(sink=flaky)

    await worker._v2_journal_adaptive_recommendation(_plan())  # falla
    assert worker._v2_adaptive_sink_failures == 1
    await worker._v2_journal_adaptive_recommendation(_plan())  # escribe: corta la racha
    await worker._v2_journal_adaptive_recommendation(_plan())  # escribe
    assert worker._v2_adaptive_sink_failures == 0
    assert flaky.successes == 2


# ── El ancla durable: sobrevive al reinicio y solo bloquea corroborada ──────────────


@pytest.mark.asyncio
async def test_the_durable_anchor_survives_a_restart() -> None:
    """Un proceso NUEVO mide la antigüedad del journal sin recordar nada del anterior."""
    journal = _Journal()
    await _worker(journal=journal, now=_T0)._v2_journal_adaptive_recommendation(_plan())
    assert len(journal.entries) == 1

    restarted = _worker(journal=journal, now=_T_PLUS_10)
    await restarted._v2_recover_adaptive_state()

    assert restarted._v2_adaptive_journal_anchor_age == 10


@pytest.mark.asyncio
async def test_the_anchor_alone_does_not_block_until_a_publication_fails() -> None:
    """La antigüedad sin corroborar no bloquea; con un fallo propio, sí (y sigue tras el reinicio)."""
    journal = _Journal()
    await _worker(journal=journal, now=_T0)._v2_journal_adaptive_recommendation(_plan())
    restarted = _worker(journal=journal, now=_T_PLUS_10)
    await restarted._v2_recover_adaptive_state()

    # Sana (sin fallo corroborado): se mide, pero no bloquea.
    assert restarted._v2_adaptive_gate_journal_age() is None
    assert (
        assess_data_gate(
            sink_failures=restarted._v2_adaptive_sink_failures,
            journal_age_cycles=restarted._v2_adaptive_gate_journal_age(),
        ).status
        == DATA_GATE_OK
    )

    # Journal muerto: la escritura falla ⇒ el ancla queda CORROBORADA y el gate bloquea.
    restarted._adaptive_sink = _FlakySink(journal, fail_for=1)
    await restarted._v2_journal_adaptive_recommendation(_plan())

    age = restarted._v2_adaptive_gate_journal_age()
    assert age is not None and age >= 10
    assert (
        assess_data_gate(
            sink_failures=restarted._v2_adaptive_sink_failures, journal_age_cycles=age
        ).status
        == DATA_GATE_BLOCKED
    )


@pytest.mark.asyncio
async def test_a_healthy_journal_does_not_stick_blocked_after_a_long_gap() -> None:
    """El caso que evita el deadlock: journal viejo pero sano ⇒ no bloquea y se cura al escribir."""
    journal = _Journal()
    await _worker(journal=journal, now=_T0)._v2_journal_adaptive_recommendation(_plan())
    restarted = _worker(journal=journal, now=_T_PLUS_10)
    await restarted._v2_recover_adaptive_state()
    assert restarted._v2_adaptive_journal_anchor_age == 10

    # Sin fallo propio, una antigüedad >= gap NO bloquea: si lo hiciera, ``adaptive = None``
    # implicaría no escribir nunca y el ancla jamás se curaría.
    assert restarted._v2_adaptive_gate_journal_age() is None

    await restarted._v2_journal_adaptive_recommendation(_plan())
    assert restarted._v2_adaptive_journal_anchor_age == 0
    assert restarted._v2_adaptive_sink_failures == 0


# ── Los huecos declarados: nunca un ancla fingida ───────────────────────────────────


@pytest.mark.asyncio
async def test_with_the_flag_off_the_anchor_is_not_read() -> None:
    """Con el flag OFF el arranque no paga I/O: ni lectura, ni contador tocado."""
    journal = _Journal()
    worker = _worker(journal=journal, enabled=False, failures=2, anchor=99)

    await worker._v2_recover_adaptive_state()

    assert journal.reads == 0
    assert worker._v2_adaptive_sink_failures == 2
    assert worker._v2_adaptive_journal_anchor_age == 99


@pytest.mark.asyncio
async def test_an_unreadable_journal_declares_the_anchor_unmeasured(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Sin lectura no hay ancla: ``None`` declarada, y lo corroborado es el propio contador."""
    worker = _worker(reader=_broken_reader, now=_T_PLUS_10, failures=1)

    with caplog.at_level(logging.WARNING):
        await worker._v2_recover_adaptive_state()

    assert worker._v2_adaptive_journal_anchor_age is None
    assert "UNREAD" in caplog.text
    assert "journalAgeCycles" in caplog.text
    # Con un fallo propio, la antigüedad efectiva es el contador (ancla 0 + 1): sigue detectable.
    assert worker._v2_adaptive_gate_journal_age() == 1


@pytest.mark.asyncio
async def test_the_measured_anchor_is_declared_in_the_recovery_log(
    caplog: pytest.LogCaptureFixture,
) -> None:
    journal = _Journal()
    await _worker(journal=journal, now=_T0)._v2_journal_adaptive_recommendation(_plan())
    restarted = _worker(journal=journal, now=_T_PLUS_10)

    with caplog.at_level(logging.INFO):
        await restarted._v2_recover_adaptive_state()

    assert "'journalAgeCycles': 10" in caplog.text


async def _broken_reader(_account_id: str | None) -> AdaptiveStateReading:
    raise RuntimeError("journal caído")
