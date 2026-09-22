"""AUTO-10 — la costura del journal durable del ciclo dentro del worker (paso 2).

Lo que se prueba es la COSTURA, no la aritmética (esa vive en
``packages/py/application/tests/test_auto_cycle_journal.py``): que el ciclo que **abre** con
su reserva de entrada deje su régimen en el sink durable; que sin sink no se escriba nada y el
turno siga intacto; que un sink que revienta no tumbe el turno pero **se declare**; que un
régimen ausente se publique declarado (``None`` + ``UNKNOWN``) en vez de omitirse; y que un
ciclo sin identidad no se invente.
"""

from __future__ import annotations

import logging
from types import SimpleNamespace
from typing import Any

import pytest

from bolsa_analytics.cognitive.measurement import (
    MEASUREMENT_COMPLETE,
    MEASUREMENT_UNKNOWN,
)
from bolsa_api.background.auto_simulation_worker import (
    AutoSimulationWorker,
    build_cycle_regime_sink,
)
from bolsa_application.auto_cycle_journal import (
    AUTO_CYCLE_REGIME_EVENT,
    build_auto_cycle_regime_entry,
)
from bolsa_application.reservation_store import InMemoryReservationStore
from bolsa_domain.entities.cognitive_artifacts import DecisionJournalEntryRecord

_ACCOUNT = "acc-1"
_REGIME = "trend_up"


def _reservation(
    *,
    reservation_id: str,
    cycle_id: str | None,
    instrument: str = "AAA",
    version: str = "orb-1",
) -> Any:
    """Reserva de ENTRADA mínima: lo que la apertura del ciclo entrega al journal."""
    from bolsa_analytics.cognitive.portfolio_reservation import PortfolioReservation

    return PortfolioReservation(
        reservation_id=reservation_id,
        account_id=_ACCOUNT,
        instrument_id=instrument,
        side="buy",
        quantity=10.0,
        entry=100.0,
        stop=95.0,
        reserved_cash=1000.0,
        reserved_risk=250.0,
        strategy_version_id=version,
        created_at="2026-09-22T08:00:00+00:00",
        cycle_id=cycle_id,
    )


class _Collector:
    """Sink durable de mentira: registra lo que el worker publica."""

    def __init__(self) -> None:
        self.entries: list[DecisionJournalEntryRecord] = []

    async def __call__(self, entry: DecisionJournalEntryRecord) -> None:
        self.entries.append(entry)


class _BrokenSink:
    """Sink que revienta: el turno NO puede tumbarse por una traza."""

    async def __call__(self, _entry: DecisionJournalEntryRecord) -> None:
        raise RuntimeError("journal no disponible")


class _FakeSession:
    """Sesión de mentira con lo justo que toca el sink: ``add`` (sync), ``flush``/``commit``.

    ``fail_on`` permite hacer reventar un paso concreto para probar el fail-open declarado.
    """

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


def _worker(*, sink: Any | None = None, regime: str | None = _REGIME) -> AutoSimulationWorker:
    worker = object.__new__(AutoSimulationWorker)
    worker._account_id = _ACCOUNT
    worker._engine_id = "auto-sim"
    worker._reservation_store = InMemoryReservationStore(seed=())
    worker._v2_reservations = ()
    worker._v2_reservation_blocked = frozenset()
    worker._v2_reservation_carryover = frozenset()
    worker._v2_tunables = SimpleNamespace(regime_override=None)
    worker._v2_regime_source = (lambda: regime) if regime is not None else None
    worker._cycle_regime_sink = sink
    # Esta costura prueba la ESCRITURA: el lector queda en None (fuente no consultada).
    worker._cycle_regime_reader = None
    worker._time = SimpleNamespace(strftime=lambda _fmt: "2026-09-22T10:00:00Z")
    return worker


async def _open_cycles(worker: AutoSimulationWorker, *reservations: Any) -> None:
    """Simula la apertura: el tick persiste sus reservas de entrada."""
    await worker._v2_persist_tick_reservations(SimpleNamespace(reservations=tuple(reservations)))


# ── El ciclo que abre publica su régimen ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_each_opened_cycle_publishes_its_regime_durably() -> None:
    sink = _Collector()
    worker = _worker(sink=sink)
    await _open_cycles(
        worker,
        _reservation(reservation_id="RES-dec-aaa", cycle_id="cyc-aaa"),
        _reservation(reservation_id="RES-dec-bbb", cycle_id="cyc-bbb", instrument="BBB"),
    )

    assert len(sink.entries) == 2
    published = {entry.payload["cycleId"]: entry for entry in sink.entries if entry.payload}
    assert set(published) == {"cyc-aaa", "cyc-bbb"}
    entry = published["cyc-aaa"]
    assert entry.decision_id == "dec-aaa", "la identidad se deriva del ciclo, no se inventa"
    assert entry.event_type == AUTO_CYCLE_REGIME_EVENT
    assert entry.payload["marketRegime"] == _REGIME
    assert entry.payload["regimeMeasurement"] == MEASUREMENT_COMPLETE
    assert entry.payload["strategyVersion"] == "orb-1"
    assert entry.account_id == _ACCOUNT
    assert entry.instrument_id == "AAA"
    assert entry.created_at == "2026-09-22T10:00:00Z"


@pytest.mark.asyncio
async def test_one_opening_is_one_trace() -> None:
    """Dos reservas del MISMO ciclo en el mismo turno no duplican la traza."""
    sink = _Collector()
    worker = _worker(sink=sink)
    await _open_cycles(
        worker,
        _reservation(reservation_id="RES-1", cycle_id="cyc-aaa"),
        _reservation(reservation_id="RES-2", cycle_id="cyc-aaa"),
    )

    assert len(sink.entries) == 1


@pytest.mark.asyncio
async def test_a_cycle_without_identity_is_not_faked() -> None:
    """Sin ``cycle_id`` no hay entrada: el hueco se declara, no se rellena con un ciclo vacío."""
    sink = _Collector()
    worker = _worker(sink=sink)
    await _open_cycles(
        worker,
        _reservation(reservation_id="RES-1", cycle_id=None),
        _reservation(reservation_id="RES-2", cycle_id="cyc-aaa"),
    )

    assert len(sink.entries) == 1
    assert sink.entries[0].payload is not None
    assert sink.entries[0].payload["cycleId"] == "cyc-aaa"


# ── El hueco declarado: sin régimen se publica, no se omite ─────────────────────────


@pytest.mark.asyncio
async def test_an_absent_regime_is_published_declared_not_skipped() -> None:
    sink = _Collector()
    worker = _worker(sink=sink, regime=None)
    await _open_cycles(worker, _reservation(reservation_id="RES-1", cycle_id="cyc-aaa"))

    assert len(sink.entries) == 1, "el ciclo abre igual: lo que falta es el régimen, no la traza"
    entry = sink.entries[0]
    assert entry.payload is not None
    assert entry.payload["marketRegime"] is None
    assert entry.payload["regimeMeasurement"] == MEASUREMENT_UNKNOWN


# ── Fail-open declarado ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_without_a_sink_the_turn_is_untouched() -> None:
    worker = _worker(sink=None)
    await _open_cycles(worker, _reservation(reservation_id="RES-1", cycle_id="cyc-aaa"))

    assert [row.reservation_id for row in worker._v2_reservations] == ["RES-1"], (
        "el compromiso de capital no depende de que haya journal"
    )


@pytest.mark.asyncio
async def test_a_broken_sink_degrades_declaring_and_keeps_the_commitment(
    caplog: pytest.LogCaptureFixture,
) -> None:
    worker = _worker(sink=_BrokenSink())
    with caplog.at_level(logging.ERROR):
        await _open_cycles(worker, _reservation(reservation_id="RES-1", cycle_id="cyc-aaa"))

    assert [row.reservation_id for row in worker._v2_reservations] == ["RES-1"]
    assert "cycle regime journal failed" in caplog.text, "el fallo se declara, no se silencia"
    assert "cyc-aaa" in caplog.text


# ── El cableado del runner: el sink real, sobre la sesión del tick ──────────────────


@pytest.mark.asyncio
async def test_the_durable_sink_commits_the_entry_on_the_tick_session() -> None:
    """El sink no se conforma con ``flush``: sin commit la fila moriría al cerrar la sesión.

    ``JournalRepository.append`` solo hace ``add`` + ``flush``, así que la durabilidad real
    depende de este commit: es lo que separa "escrito" de "escrito y perdido al cerrar".
    """
    session = _FakeSession()
    sink = build_cycle_regime_sink(session)
    entry = build_auto_cycle_regime_entry(
        cycle_id="cyc-aaa",
        market_regime=_REGIME,
        actor="auto-sim",
        as_of="2026-09-22T10:00:00Z",
        account_id=_ACCOUNT,
        instrument_id="AAA",
    )
    assert entry is not None

    await sink(entry)

    assert session.calls == ["add", "flush", "commit"], "sin commit no hay durabilidad"
    row = session.added[0]
    assert row.id == entry.id
    assert row.decision_id == "dec-aaa"
    assert row.payload["cycleId"] == "cyc-aaa"
    assert row.payload["marketRegime"] == _REGIME


@pytest.mark.asyncio
async def test_a_broken_write_leaves_the_tick_session_clean() -> None:
    """Una traza que no se puede escribir NO puede envenenar la sesión del turno.

    Sin ``rollback`` la sesión quedaría en estado fallido y el SIGUIENTE store del mismo
    turno reventaría: la traza rota tumbaría el compromiso de capital, que es justo lo que
    el fail-open declarado promete que no pasa.
    """
    session = _FakeSession(fail_on="commit")
    sink = build_cycle_regime_sink(session)
    entry = build_auto_cycle_regime_entry(
        cycle_id="cyc-aaa",
        market_regime=_REGIME,
        actor="auto-sim",
        as_of="2026-09-22T10:00:00Z",
        account_id=_ACCOUNT,
    )
    assert entry is not None

    with pytest.raises(RuntimeError, match="sesión rota en commit"):
        await sink(entry)

    assert session.calls[-1] == "rollback", "la sesión se deja limpia para el resto del turno"
