"""AUTO-11 — la costura del estado Adaptive durable dentro del worker (crash y recuperación).

Lo que se prueba es la COSTURA, no la aritmética (esa vive en
``packages/py/application/tests/test_auto_adaptive_recovery.py``): que el estado se reconstruya del
journal **antes** del primer plan del proceso, que un crash durante el cooldown no levante la pausa
antes de su ventana mínima, que un cambio de política conserve el contador y lo declare, que sin
fuente durable el contador vacío se declare (nunca "no había pausas"), y que la recomendación se
publique DESPUÉS de que el motor determinista la consumió.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import pytest

from bolsa_analytics.cognitive.auto_adaptive import (
    ADAPTIVE_POLICY_VERSION,
    ADAPTIVE_STRATEGY_COOLDOWN,
    AdaptivePolicy,
    build_adaptive_plan,
)
from bolsa_analytics.cognitive.auto_self_evaluation import StrategySelfEvaluation
from bolsa_analytics.cognitive.measurement import (
    MEASUREMENT_COMPLETE,
    MEASUREMENT_UNKNOWN,
)
from bolsa_api.background.auto_simulation_worker import (
    AutoSimulationWorker,
    build_adaptive_recommendation_sink,
    build_adaptive_state_reader,
)
from bolsa_application.auto_adaptive_journal import (
    AUTO_ADAPTIVE_RECOMMENDATION_EVENT,
    build_adaptive_recommendation_entry,
)
from bolsa_application.auto_adaptive_recovery import (
    ADAPTIVE_STATE_WINDOW_DEFAULT,
    AdaptiveStateReading,
    read_adaptive_state,
)
from bolsa_application.auto_cycle_regime_reader import CycleRegimeReading
from bolsa_domain.entities.cognitive_artifacts import DecisionJournalEntryRecord

_ACCOUNT = "acc-1"
_AS_OF = "2026-09-22T10:00:00Z"
_FLOOR = 0.35


def _row(
    version: str,
    *,
    decisive: bool = False,
    expectancy: str | None = None,
    win_rate: float | None = None,
) -> StrategySelfEvaluation:
    """Fila de self-evaluation mínima con SOLO lo que Adaptive lee (el resto, ausente)."""
    return StrategySelfEvaluation(
        strategy_version=version,
        trades=0,
        wins=0,
        losses=0,
        realized_pnl=Decimal("0"),
        expectancy_currency=Decimal(expectancy) if expectancy is not None else None,
        expectancy_r=None,
        net_expectancy_r=None,
        win_rate=win_rate,
        profit_factor=None,
        avg_win_currency=None,
        avg_loss_currency=None,
        mfe_r=None,
        mae_r=None,
        slippage_currency=None,
        rejection_cost_return=None,
        drawdown_currency=Decimal("0"),
        drawdown_share=None,
        traded=0,
        rejected=0,
        expired=0,
        missed=0,
        sample_quality="",
        results_measurement=MEASUREMENT_COMPLETE if decisive else MEASUREMENT_UNKNOWN,
        risk_measurement=MEASUREMENT_UNKNOWN,
        net_r_measurement=MEASUREMENT_UNKNOWN,
        cycles_without_cost=0,
        excursions_measurement=MEASUREMENT_UNKNOWN,
        slippage_measurement=MEASUREMENT_UNKNOWN,
        rejection_cost_measurement=MEASUREMENT_UNKNOWN,
        drawdown_measurement=MEASUREMENT_UNKNOWN,
        decisive=decisive,
        notes=(),
    )


def _policy() -> AdaptivePolicy:
    return AdaptivePolicy(win_rate_floor=_FLOOR)


class _Journal:
    """Sink+lector de mentira sobre el MISMO material: escribe filas y las reconstruye de verdad.

    El lector usa ``read_adaptive_state`` (el módulo real) en vez de devolver un valor a mano: así
    la costura prueba la reconstrucción completa y no una promesa.
    """

    def __init__(self, *, broken_read: bool = False) -> None:
        self.entries: list[DecisionJournalEntryRecord] = []
        self.reads = 0
        self._broken = broken_read

    async def sink(self, entry: DecisionJournalEntryRecord) -> None:
        self.entries.append(entry)

    async def reader(self, _account_id: str | None) -> AdaptiveStateReading:
        self.reads += 1
        if self._broken:
            raise RuntimeError("journal caído")
        return read_adaptive_state(
            list(reversed(self.entries)),
            min_pause_cycles=_policy().min_pause_cycles,
            running_policy_version=ADAPTIVE_POLICY_VERSION,
            window=ADAPTIVE_STATE_WINDOW_DEFAULT,
        )


class _BrokenSink:
    async def __call__(self, _entry: DecisionJournalEntryRecord) -> None:
        raise RuntimeError("journal no disponible")


def _worker(
    *,
    reader: Any | None = None,
    sink: Any | None = None,
    enabled: bool = True,
    reservations: Any | None = None,
    regime_reader: Any | None = None,
) -> AutoSimulationWorker:
    worker = object.__new__(AutoSimulationWorker)
    worker._account_id = _ACCOUNT
    worker._engine_id = "auto-sim"
    worker._adaptive_reader = reader
    worker._adaptive_sink = sink
    worker._v2_adaptive_paused_cycles = {}
    # AUTO-13 paso 4: la memoria de la rampa arranca vacia (el lector durable la siembra).
    worker._v2_adaptive_reactivated_at = {}
    worker._v2_adaptive_paused_cycles_entered = {}
    worker._v2_adaptive_state_recovered = False
    worker._v2_cycle_trace_reconciled = False
    worker._v2_tunables = SimpleNamespace(
        adaptive_enabled=enabled,
        adaptive_win_rate_floor=_FLOOR,
        regime_override=None,
    )
    worker._time = SimpleNamespace(strftime=lambda _fmt: _AS_OF)
    worker._reservation_store = reservations
    worker._cycle_regime_reader = regime_reader
    return worker


def _paused_entry(*, as_of: str = _AS_OF, policy: str = ADAPTIVE_POLICY_VERSION):
    """Fila durable de una evaluación que PAUSÓ ``v42`` (evidencia del turno anterior)."""
    plan = build_adaptive_plan(
        (_row("v42", decisive=True, expectancy="-2"),),
        "TREND_UP",
        policy=_policy(),
    )
    assert plan.rotation.paused == frozenset({"v42"})
    entry = build_adaptive_recommendation_entry(
        plan=plan, actor="auto-sim", as_of=as_of, account_id=_ACCOUNT
    )
    assert entry is not None
    return plan, entry


# ── Crash durante el cooldown (P1 de la auditoría de V2.51) ─────────────────────────


def test_the_thresholds_alone_would_lift_the_pause_before_its_minimum_window() -> None:
    """El bug que AUTO-11 cierra, aislado: sin memoria el turno reactiva una pausa vigente.

    La muestra de la versión deja de ser decisoria, así que los umbrales de pausa ya NO se
    disparan: lo único que sostiene la pausa es el contador de cooldown.
    """
    now = (_row("v42", decisive=False, win_rate=0.5),)

    without_memory = build_adaptive_plan(now, "TREND_UP", policy=_policy(), paused_cycles={})
    with_memory = build_adaptive_plan(now, "TREND_UP", policy=_policy(), paused_cycles={"v42": 1})

    assert not without_memory.is_paused("v42"), "contador a 0 ⇒ reactivación (el bug)"
    assert with_memory.is_paused("v42")
    assert with_memory.rotation.reason_for("v42") == ADAPTIVE_STRATEGY_COOLDOWN


def test_a_crash_during_the_cooldown_is_healed_from_the_journal() -> None:
    """Turno N pausa ⇒ crash ANTES de encadenar el contador ⇒ el journal lo devuelve."""
    _plan_turn_n, entry = _paused_entry()
    reading = read_adaptive_state(
        [entry],
        min_pause_cycles=_policy().min_pause_cycles,
        running_policy_version=ADAPTIVE_POLICY_VERSION,
    )

    assert reading.paused_cycles == {"v42": 1}, "la racha se rehace de la evaluación durable"

    now = (_row("v42", decisive=False, win_rate=0.5),)
    recovered = build_adaptive_plan(
        now, "TREND_UP", policy=_policy(), paused_cycles=reading.paused_cycles
    )

    assert recovered.is_paused("v42"), "la pausa NO se levanta antes de su ventana mínima"
    assert recovered.rotation.reason_for("v42") == ADAPTIVE_STRATEGY_COOLDOWN


@pytest.mark.asyncio
async def test_the_worker_seeds_the_counter_from_the_journal_on_startup() -> None:
    journal = _Journal()
    _plan_turn_n, entry = _paused_entry()
    journal.entries.append(entry)
    worker = _worker(reader=journal.reader)

    await worker._v2_recover_adaptive_state()

    assert worker._v2_adaptive_paused_cycles == {"v42": 1}
    assert journal.reads == 1


@pytest.mark.asyncio
async def test_the_recovery_runs_once_per_process() -> None:
    journal = _Journal()
    _plan_turn_n, entry = _paused_entry()
    journal.entries.append(entry)
    worker = _worker(reader=journal.reader)

    await worker._v2_recover_adaptive_state()
    worker._v2_adaptive_paused_cycles = {"v42": 1}
    await worker._v2_recover_adaptive_state()

    assert journal.reads == 1, "la segunda llamada no vuelve a leer ni pisa el estado encadenado"


# ── Recomputar el mismo turno tras el reinicio da el MISMO plan ─────────────────────


def test_recomputing_the_same_material_after_a_restart_returns_the_same_recommendation() -> None:
    """Mismo material + mismo contador reconstruido ⇒ misma evidencia y misma identidad.

    Es el gate de "crash entre journal y decisión": la recomendación durable no depende de que el
    proceso siguiera vivo, solo de la historia que quedó escrita.
    """
    rows = (
        _row("v42", decisive=True, expectancy="3"),
        _row("v99", decisive=True, expectancy="1"),
    )
    entered = {"v99": 1}
    first = build_adaptive_plan(rows, "TREND_UP", policy=_policy(), paused_cycles=entered)
    entry = build_adaptive_recommendation_entry(
        plan=first, actor="auto-sim", as_of=_AS_OF, account_id=_ACCOUNT, paused_cycles=entered
    )
    assert entry is not None

    reading = read_adaptive_state(
        [entry],
        min_pause_cycles=_policy().min_pause_cycles,
        running_policy_version=ADAPTIVE_POLICY_VERSION,
    )
    assert reading.paused_cycles == entered, "el contador que entró se reconstruye"

    second = build_adaptive_plan(
        rows, "TREND_UP", policy=_policy(), paused_cycles=reading.paused_cycles
    )
    again = build_adaptive_recommendation_entry(
        plan=second, actor="auto-sim", as_of=_AS_OF, account_id=_ACCOUNT, paused_cycles=reading.paused_cycles
    )

    assert second.as_dict() == first.as_dict()
    assert again is not None
    assert again.payload == entry.payload
    assert again.decision_id == entry.decision_id


# ── Continuidad de política ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_a_policy_change_keeps_the_counter_and_is_declared(
    caplog: pytest.LogCaptureFixture,
) -> None:
    reading = AdaptiveStateReading(
        paused_cycles={"v42": 2},
        policy_versions=("auto9-v1", "auto9-v2"),
        policy_version_mismatch=True,
        evaluated=2,
        requested=ADAPTIVE_STATE_WINDOW_DEFAULT,
    )
    worker = _worker(reader=_constant_reader(reading))

    with caplog.at_level(logging.WARNING):
        await worker._v2_recover_adaptive_state()

    assert worker._v2_adaptive_paused_cycles == {"v42": 2}, "no se resetea con la política nueva"
    assert "policy version mismatch" in caplog.text
    assert "auto9-v1" in caplog.text


# ── Los huecos declarados: nunca "no había pausas" ──────────────────────────────────


@pytest.mark.asyncio
async def test_without_a_reader_the_counter_stays_empty_and_is_declared(
    caplog: pytest.LogCaptureFixture,
) -> None:
    worker = _worker(reader=None)

    with caplog.at_level(logging.WARNING):
        await worker._v2_recover_adaptive_state()

    assert worker._v2_adaptive_paused_cycles == {}
    assert "NOT durable" in caplog.text


@pytest.mark.asyncio
async def test_a_broken_reader_degrades_declaring_instead_of_silently_resetting(
    caplog: pytest.LogCaptureFixture,
) -> None:
    worker = _worker(reader=_Journal(broken_read=True).reader)

    with caplog.at_level(logging.WARNING):
        await worker._v2_recover_adaptive_state()

    assert worker._v2_adaptive_paused_cycles == {}
    assert "UNREAD" in caplog.text, "el hueco se declara; nunca se disfraza de 'no había pausas'"


@pytest.mark.asyncio
async def test_with_the_adaptive_flag_off_there_is_no_read_at_all() -> None:
    journal = _Journal()
    worker = _worker(reader=journal.reader, enabled=False)

    await worker._v2_recover_adaptive_state()

    assert journal.reads == 0, "con el flag OFF el tick no paga I/O nuevo"
    assert worker._v2_adaptive_paused_cycles == {}


# ── La recomendación se publica DESPUÉS de que el motor la consumió ─────────────────


@pytest.mark.asyncio
async def test_the_recommendation_is_published_with_the_counter_that_entered() -> None:
    sink = _Journal()
    worker = _worker(sink=sink.sink)
    plan = build_adaptive_plan(
        (_row("v42", decisive=True, expectancy="-2"),), "TREND_UP", policy=_policy()
    )
    worker._v2_adaptive_paused_cycles_entered = {"v42": 1}

    await worker._v2_journal_adaptive_recommendation(plan)

    assert len(sink.entries) == 1
    entry = sink.entries[0]
    assert entry.event_type == AUTO_ADAPTIVE_RECOMMENDATION_EVENT
    assert entry.payload is not None
    assert entry.payload["pausedCycles"] == {"v42": 1}, "el contador de ENTRADA, no el de salida"
    assert entry.payload["rotation"]["paused"] == ["v42"]
    assert entry.created_at == _AS_OF


@pytest.mark.asyncio
async def test_without_a_plan_or_without_a_sink_nothing_is_written() -> None:
    sink = _Journal()
    worker = _worker(sink=sink.sink)

    await worker._v2_journal_adaptive_recommendation(None)
    await _worker(sink=None)._v2_journal_adaptive_recommendation(
        build_adaptive_plan((_row("v42", decisive=True, expectancy="3"),), "TREND_UP")
    )

    assert sink.entries == []


@pytest.mark.asyncio
async def test_a_broken_sink_degrades_declaring_and_keeps_the_turn(
    caplog: pytest.LogCaptureFixture,
) -> None:
    worker = _worker(sink=_BrokenSink())
    plan = build_adaptive_plan(
        (_row("v42", decisive=True, expectancy="-2"),), "TREND_UP", policy=_policy()
    )

    with caplog.at_level(logging.ERROR):
        await worker._v2_journal_adaptive_recommendation(plan)

    assert "adaptive recommendation journal failed" in caplog.text


# ── Reconciliación del rastro de ciclo en el arranque ───────────────────────────────


class _Reservations:
    def __init__(self, cycle_ids: tuple[str, ...]) -> None:
        self._rows = [
            SimpleNamespace(cycle_id=cycle_id, reservation_id=f"RES-{index}")
            for index, cycle_id in enumerate(cycle_ids)
        ]
        self.calls: list[tuple[str | None, int]] = []

    async def list_recent_with_cycle(self, account_id: str | None, *, limit: int = 500):
        self.calls.append((account_id, limit))
        return list(self._rows)


class _RegimeReader:
    def __init__(self, reading: CycleRegimeReading) -> None:
        self._reading = reading
        self.asked: list[tuple[str, ...]] = []

    async def __call__(self, cycle_ids):
        self.asked.append(tuple(cycle_ids))
        return self._reading


@pytest.mark.asyncio
async def test_a_reserved_cycle_without_a_confirmed_trace_is_declared_at_startup(
    caplog: pytest.LogCaptureFixture,
) -> None:
    reservations = _Reservations(("cyc-aaa", "cyc-bbb"))
    regime = _RegimeReader(CycleRegimeReading(regime_by_cycle={"cyc-aaa": "TREND_UP"}))
    worker = _worker(reservations=reservations, regime_reader=regime)

    with caplog.at_level(logging.WARNING):
        await worker._v2_reconcile_cycle_traces()

    assert reservations.calls == [(_ACCOUNT, ADAPTIVE_STATE_WINDOW_DEFAULT)]
    assert regime.asked == [("cyc-aaa", "cyc-bbb")]
    assert "GAPS" in caplog.text
    assert "cyc-bbb" in caplog.text, "el ciclo sin traza se nombra, no se cuenta y se calla"


@pytest.mark.asyncio
async def test_a_clean_crossing_is_declared_clean(caplog: pytest.LogCaptureFixture) -> None:
    reservations = _Reservations(("cyc-aaa",))
    regime = _RegimeReader(CycleRegimeReading(regime_by_cycle={"cyc-aaa": "TREND_UP"}))
    worker = _worker(reservations=reservations, regime_reader=regime)

    with caplog.at_level(logging.INFO):
        await worker._v2_reconcile_cycle_traces()

    assert "reconciliation clean" in caplog.text


@pytest.mark.asyncio
async def test_the_reconciliation_runs_once_per_process() -> None:
    reservations = _Reservations(("cyc-aaa",))
    regime = _RegimeReader(CycleRegimeReading())
    worker = _worker(reservations=reservations, regime_reader=regime)

    await worker._v2_reconcile_cycle_traces()
    await worker._v2_reconcile_cycle_traces()

    assert len(reservations.calls) == 1


@pytest.mark.asyncio
async def test_without_the_cycle_window_there_is_nothing_to_reconcile(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Hermético: sin la ventana de reservas no se inventa un cruce ni se afirma que está limpio."""
    regime = _RegimeReader(CycleRegimeReading())
    worker = _worker(reservations=SimpleNamespace(), regime_reader=regime)

    with caplog.at_level(logging.INFO):
        await worker._v2_reconcile_cycle_traces()

    assert regime.asked == []
    assert caplog.text == ""


@pytest.mark.asyncio
async def test_a_broken_reservation_read_is_declared_not_treated_as_clean(
    caplog: pytest.LogCaptureFixture,
) -> None:
    class _Broken:
        async def list_recent_with_cycle(self, _account_id, *, limit: int = 500):
            raise RuntimeError("PG caído")

    regime = _RegimeReader(CycleRegimeReading())
    worker = _worker(reservations=_Broken(), regime_reader=regime)

    with caplog.at_level(logging.ERROR):
        await worker._v2_reconcile_cycle_traces()

    assert "reservations read failed" in caplog.text
    assert regime.asked == []


# ── Los dos constructores reales de la sesión del tick ──────────────────────────────


class _FakeSession:
    """Sesión de mentira con lo justo que toca el sink: ``add`` (sync), ``flush``/``commit``."""

    def __init__(self, *, fail_on: str | None = None) -> None:
        self.added: list[Any] = []
        self.calls: list[str] = []
        self._fail_on = fail_on

    def _step(self, name: str) -> None:
        self.calls.append(name)
        if self._fail_on == name:
            raise RuntimeError(f"sesión rota en {name}")

    def add(self, row: Any) -> None:
        self._step("add")
        self.added.append(row)

    async def flush(self) -> None:
        self._step("flush")

    async def commit(self) -> None:
        self._step("commit")

    async def rollback(self) -> None:
        self._step("rollback")


@pytest.mark.asyncio
async def test_the_durable_sink_commits_the_recommendation_on_the_tick_session() -> None:
    """Sin commit la recomendación moriría al cerrar la sesión: el cooldown volvería a la RAM."""
    session = _FakeSession()
    sink = build_adaptive_recommendation_sink(session)
    plan = build_adaptive_plan(
        (_row("v42", decisive=True, expectancy="-2"),), "TREND_UP", policy=_policy()
    )
    entry = build_adaptive_recommendation_entry(
        plan=plan, actor="auto-sim", as_of=_AS_OF, account_id=_ACCOUNT
    )
    assert entry is not None

    await sink(entry)

    assert session.calls == ["add", "flush", "commit"]
    assert session.added[0].decision_id == entry.decision_id
    assert session.added[0].event_type == AUTO_ADAPTIVE_RECOMMENDATION_EVENT


@pytest.mark.asyncio
async def test_a_broken_recommendation_write_leaves_the_tick_session_clean() -> None:
    session = _FakeSession(fail_on="commit")
    sink = build_adaptive_recommendation_sink(session)
    plan = build_adaptive_plan(
        (_row("v42", decisive=True, expectancy="-2"),), "TREND_UP", policy=_policy()
    )
    entry = build_adaptive_recommendation_entry(
        plan=plan, actor="auto-sim", as_of=_AS_OF, account_id=_ACCOUNT
    )
    assert entry is not None

    with pytest.raises(RuntimeError, match="sesión rota en commit"):
        await sink(entry)

    assert session.calls[-1] == "rollback", "la sesión se deja limpia para el resto del turno"


@pytest.mark.asyncio
async def test_the_reader_without_an_account_declares_the_gap_without_querying() -> None:
    """Sin cuenta no hay ``WHERE`` posible: se declara el hueco en vez de leer otra historia."""
    reader = build_adaptive_state_reader(None, policy=_policy())

    reading = await reader("   ")

    assert reading.read_ok is False
    assert reading.paused_cycles == {}
    assert reading.requested == ADAPTIVE_STATE_WINDOW_DEFAULT


@pytest.mark.asyncio
async def test_the_reader_reads_the_event_by_index_and_applies_the_running_policy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """La historia se juzga con los umbrales de HOY: la política entra por parámetro, no por copia."""
    from bolsa_infrastructure.database.repositories.journal_repository import (
        SqlAlchemyJournalRepository,
    )

    calls: list[dict[str, Any]] = []
    _plan_turn_n, entry = _paused_entry()

    async def fake_list_entries(self, **kwargs):
        calls.append(kwargs)
        return [entry], 1

    monkeypatch.setattr(SqlAlchemyJournalRepository, "list_entries", fake_list_entries)

    reading = await build_adaptive_state_reader(None, policy=_policy())(_ACCOUNT)

    assert calls == [
        {
            "account_id": _ACCOUNT,
            "event_type": AUTO_ADAPTIVE_RECOMMENDATION_EVENT,
            "limit": ADAPTIVE_STATE_WINDOW_DEFAULT,
        }
    ]
    assert reading.paused_cycles == {"v42": 1}
    assert reading.read_ok is True
    assert reading.policy_versions == (ADAPTIVE_POLICY_VERSION,)


def _constant_reader(reading: AdaptiveStateReading) -> Any:
    async def reader(_account_id: str | None) -> AdaptiveStateReading:
        return reading

    return reader
