"""AUTO Operational Monitor (``M2``) — la costura del sumidero de auditoría en el worker.

Lo que se prueba es la COSTURA, no la aritmética (esa vive en
``packages/py/application/tests/test_auto_operational_audit.py``): que el journal de decisión
del turno, la carrera de claim y la decisión del barrido dejen su traza en el spine con su
sesión (dueño/caller); que sin sink no se escriba nada (Δ = 0); que un sink que revienta no
tumbe el turno pero **se declare**; y que el sink real commitea y deja la sesión limpia.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from types import SimpleNamespace
from typing import Any

import pytest

from bolsa_api.background.auto_simulation_worker import (
    AutoSimulationWorker,
    build_operational_audit_sink,
    flat_price_script,
)
from bolsa_application.auto_operational_audit import (
    REASON_GRACE_WINDOW_KEEP,
    REASON_SESSION_OWNED,
    RECONCILIATION_KEEP,
    RECONCILIATION_RELEASE,
    build_entry_order_entry,
    build_reservation_claim_entry,
)
from bolsa_application.auto_operational_monitor import (
    AUTO_CYCLE_SETTLEMENT_EVENT,
    AUTO_ENTRY_DECISION_EVENT,
    AUTO_ENTRY_ORDER_EVENT,
    AUTO_PROTECTION_EVENT,
    AUTO_RESERVATION_CLAIM_EVENT,
    AUTO_RESERVATION_RECONCILIATION_EVENT,
)
from bolsa_domain.entities.cognitive_artifacts import DecisionJournalEntryRecord

_ACCOUNT = "acc-1"


class _Collector:
    """Sink de mentira: registra lo que el worker publica."""

    def __init__(self) -> None:
        self.entries: list[DecisionJournalEntryRecord] = []

    async def __call__(self, entry: DecisionJournalEntryRecord) -> None:
        self.entries.append(entry)


class _BrokenSink:
    async def __call__(self, _entry: DecisionJournalEntryRecord) -> None:
        raise RuntimeError("spine no disponible")


class _FakeSession:
    """Sesión mínima del sink real: ``add`` (sync), ``flush``/``commit``/``rollback``."""

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


def _worker(*, sink: Any | None = None) -> AutoSimulationWorker:
    worker = object.__new__(AutoSimulationWorker)
    worker._account_id = _ACCOUNT
    worker._engine_id = "auto-sim"
    worker._operational_audit_sink = sink
    worker._audit_session_id = None
    worker._v2_reservation_grace = timedelta(seconds=61)
    worker._time = SimpleNamespace(strftime=lambda _fmt: "2026-10-01T10:00:00Z")
    # v2.88.25 — la fuente de precio y el store de fills que usan los nuevos productores.
    worker._price_source = None
    worker._price_script = flat_price_script
    worker._context_store = None
    return worker


def _reservation(*, reservation_id: str, cycle_id: str | None, instrument: str = "AAA") -> Any:
    return SimpleNamespace(
        reservation_id=reservation_id,
        cycle_id=cycle_id,
        instrument_id=instrument,
    )


def _journal_entry(*, cycle_id: str, decision_id: str = "dec-aaa") -> DecisionJournalEntryRecord:
    return DecisionJournalEntryRecord(
        id=f"JNL-{decision_id}",
        decision_id=decision_id,
        event_type=AUTO_ENTRY_DECISION_EVENT,
        actor="auto-sim",
        created_at="2026-10-01T09:59:00Z",
        account_id=_ACCOUNT,
        instrument_id="AAA",
        payload={"cycleId": cycle_id, "instrumentId": "AAA", "rank": 1},
    )


# ── El journal de decisión del turno deja de vivir sólo en RAM ───────────────────────


@pytest.mark.asyncio
async def test_entry_decisions_are_persisted_with_their_identity() -> None:
    """La decisión se persiste tal cual: la FK ``decision_sessions`` no se invade (Δ de forma)."""
    sink = _Collector()
    worker = _worker(sink=sink)
    await worker._v2_journal_entry_decisions([_journal_entry(cycle_id="cyc-aaa")])

    assert len(sink.entries) == 1
    entry = sink.entries[0]
    assert entry.event_type == AUTO_ENTRY_DECISION_EVENT
    assert entry.decision_id == "dec-aaa"
    assert entry.session_id is None
    assert entry.payload is not None
    assert entry.payload["cycleId"] == "cyc-aaa"


@pytest.mark.asyncio
async def test_entry_decision_without_account_is_stamped_for_the_global_read() -> None:
    """El productor no trae ``account_id``: el tramo de TRAZADO lo sella (no es una decisión).

    Es lo que permite al monitor leer el último ``auto_entry_decision`` por
    ``account_id + event_type`` sin depender de las reservas visibles.
    """
    sink = _Collector()
    worker = _worker(sink=sink)
    entry = DecisionJournalEntryRecord(
        id="JNL-dec-bbb",
        decision_id="dec-bbb",
        event_type=AUTO_ENTRY_DECISION_EVENT,
        actor="auto-sim",
        created_at="2026-10-01T09:59:00Z",
        instrument_id="AAA",
        payload={"cycleId": "cyc-bbb", "instrumentId": "AAA", "rank": 1},
    )
    await worker._v2_journal_entry_decisions([entry])

    assert len(sink.entries) == 1
    stamped = sink.entries[0]
    assert stamped.account_id == _ACCOUNT
    # El hecho persistido no se reescribe más allá de los sellos de trazado (identidad
    # intacta): ``account_id`` y, aditivo, ``payload.engineId`` para la lectura por motor.
    assert stamped.decision_id == "dec-bbb"
    assert stamped.payload["cycleId"] == "cyc-bbb"
    assert stamped.payload["rank"] == 1
    assert stamped.payload["engineId"] == "auto-sim"


@pytest.mark.asyncio
async def test_entry_decision_seals_the_engine_id_for_the_scoped_read() -> None:
    """(A4) El tramo de trazado sella ``payload.engineId`` cuando el productor no lo trae.

    Es lo que permite acotar ``lastDecisionAt`` a ``account_id + engine_id``: dos motores de
    la misma cuenta no comparten "última decisión".
    """
    sink = _Collector()
    worker = _worker(sink=sink)
    await worker._v2_journal_entry_decisions([_journal_entry(cycle_id="cyc-aaa")])

    assert sink.entries[0].payload is not None
    assert sink.entries[0].payload["engineId"] == "auto-sim"


@pytest.mark.asyncio
async def test_entry_decision_keeps_a_producer_engine_id_without_rewriting() -> None:
    """Un ``engineId`` ya presente NO se pisa: el sello es solo para quien no lo declara."""
    sink = _Collector()
    worker = _worker(sink=sink)
    entry = DecisionJournalEntryRecord(
        id="JNL-dec-ccc",
        decision_id="dec-ccc",
        event_type=AUTO_ENTRY_DECISION_EVENT,
        actor="auto-sim",
        created_at="2026-10-01T09:59:00Z",
        account_id=_ACCOUNT,
        instrument_id="AAA",
        payload={"cycleId": "cyc-ccc", "engineId": "auto-otro"},
    )
    await worker._v2_journal_entry_decisions([entry])

    assert sink.entries[0].payload is not None
    assert sink.entries[0].payload["engineId"] == "auto-otro"


@pytest.mark.asyncio
async def test_entry_decision_keeps_a_producer_account_without_rewriting() -> None:
    sink = _Collector()
    worker = _worker(sink=sink)
    await worker._v2_journal_entry_decisions([_journal_entry(cycle_id="cyc-aaa")])
    assert sink.entries[0].account_id == _ACCOUNT


@pytest.mark.asyncio
async def test_without_a_sink_the_journal_is_not_written() -> None:
    worker = _worker(sink=None)
    await worker._v2_journal_entry_decisions([_journal_entry(cycle_id="cyc-aaa")])
    assert worker._operational_audit_sink is None


# ── La carrera de claim (ganado/perdido) queda en el spine ───────────────────────────


@pytest.mark.asyncio
async def test_claim_race_is_recorded_won_and_lost() -> None:
    sink = _Collector()
    worker = _worker(sink=sink)
    await worker._v2_journal_reservation_claims(
        [
            (_reservation(reservation_id="RES-dec-aaa", cycle_id="cyc-aaa"), True),
            (_reservation(reservation_id="RES-dec-bbb", cycle_id="cyc-bbb"), False),
        ]
    )

    assert len(sink.entries) == 2
    assert all(entry.event_type == AUTO_RESERVATION_CLAIM_EVENT for entry in sink.entries)
    by_reservation = {entry.payload["reservation_id"]: entry for entry in sink.entries if entry.payload}
    assert by_reservation["RES-dec-aaa"].payload["claimed"] is True
    assert by_reservation["RES-dec-bbb"].payload["claimed"] is False
    # La sesión va en el payload (no en la columna con FK): ambas carreras la declaran.
    assert (
        by_reservation["RES-dec-aaa"].payload["caller"]
        == by_reservation["RES-dec-bbb"].payload["caller"]
    )


# ── La decisión del barrido (KEEP/RELEASE) queda en el spine ─────────────────────────


@pytest.mark.asyncio
async def test_reconciliation_decisions_are_recorded_with_caller_and_age() -> None:
    sink = _Collector()
    worker = _worker(sink=sink)
    await worker._v2_journal_reconciliation_decisions(
        [
            (
                _reservation(reservation_id="RES-1", cycle_id="cyc-aaa"),
                RECONCILIATION_RELEASE,
                "fill",
                True,
                True,
            ),
            (
                _reservation(reservation_id="RES-2", cycle_id="cyc-bbb"),
                RECONCILIATION_KEEP,
                REASON_GRACE_WINDOW_KEEP,
                False,
                False,
            ),
            (
                _reservation(reservation_id="RES-3", cycle_id=None),
                RECONCILIATION_KEEP,
                REASON_SESSION_OWNED,
                True,
                None,
            ),
        ]
    )

    assert len(sink.entries) == 3
    assert all(entry.event_type == AUTO_RESERVATION_RECONCILIATION_EVENT for entry in sink.entries)
    payloads = {entry.payload["reservation_id"]: entry.payload for entry in sink.entries if entry.payload}
    assert payloads["RES-1"]["decision"] == "RELEASE"
    assert payloads["RES-1"]["reason"] == "fill"
    assert payloads["RES-1"]["graceWindowSeconds"] == 61.0
    assert payloads["RES-2"]["decision"] == "KEEP"
    assert payloads["RES-2"]["reason"] == REASON_GRACE_WINDOW_KEEP
    assert payloads["RES-3"]["aged"] is None
    assert payloads["RES-3"]["agedMeasurement"] == "UNKNOWN"
    # Todo lo decidido por esta sesión la declara como ``caller`` en el payload (ownership
    # del barrido); la columna ``session_id`` queda limpia por la FK a ``decision_sessions``.
    assert all(entry.payload is not None and entry.payload["caller"] for entry in sink.entries)
    assert all(entry.session_id is None for entry in sink.entries)


# ── Fail-open declarado ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_a_broken_sink_degrades_declaring_and_does_not_raise(
    caplog: pytest.LogCaptureFixture,
) -> None:
    worker = _worker(sink=_BrokenSink())
    with caplog.at_level(logging.ERROR):
        await worker._v2_journal_entry_decisions([_journal_entry(cycle_id="cyc-aaa")])

    assert "operational audit failed" in caplog.text
    assert "entry_decision" in caplog.text


# ── El cableado del runner: el sink real, sobre la sesión del tick ──────────────────


@pytest.mark.asyncio
async def test_the_real_sink_commits_the_entry_on_the_tick_session() -> None:
    session = _FakeSession()
    sink = build_operational_audit_sink(session)
    entry = build_reservation_claim_entry(
        reservation_id="RES-dec-aaa",
        cycle_id="cyc-aaa",
        claimed=True,
        actor="auto-sim",
        session_id="sess-a",
        as_of="2026-10-01T10:00:00Z",
        account_id=_ACCOUNT,
        instrument_id="AAA",
    )
    assert entry is not None

    await sink(entry)

    assert session.calls == ["add", "flush", "commit"], "sin commit no hay durabilidad"
    assert session.added[0].id == entry.id
    assert session.added[0].payload["reservation_id"] == "RES-dec-aaa"


@pytest.mark.asyncio
async def test_a_broken_write_leaves_the_tick_session_clean() -> None:
    session = _FakeSession(fail_on="commit")
    sink = build_operational_audit_sink(session)
    entry = build_reservation_claim_entry(
        reservation_id="RES-dec-aaa",
        cycle_id="cyc-aaa",
        claimed=False,
        actor="auto-sim",
        session_id="sess-a",
        as_of="2026-10-01T10:00:00Z",
        account_id=_ACCOUNT,
    )
    assert entry is not None

    with pytest.raises(RuntimeError, match="sesión rota en commit"):
        await sink(entry)

    assert session.calls[-1] == "rollback", "la sesión se deja limpia para el resto del turno"


# ── Regresión del rojo v2.88.21-beta: worker sin la costura declarada ────────────────


@pytest.mark.asyncio
async def test_a_worker_without_the_seam_attribute_is_a_declared_noop() -> None:
    """Un worker montado con ``object.__new__`` (patrón de los tests de un solo método) **no**
    pasa por ``__init__``, así que no declara ``_operational_audit_sink``. Leerlo a pelo
    reventaba con ``AttributeError`` **en medio de un turno real** —es el rojo que tumbó el
    ``python`` offline del tag ``v2.88.21-beta``—. El default a nivel de CLASE lo hace ``None``
    ⇒ la ausencia de sink es exactamente el ``Δ = 0`` que promete el flag OFF, también por esta
    vía de construcción.
    """
    worker = object.__new__(AutoSimulationWorker)
    worker._account_id = _ACCOUNT

    # Las tres costuras deben ser no-ops declarados: sin sink no hay nada que emitir.
    await worker._v2_journal_entry_decisions([])
    await worker._v2_journal_reservation_claims(
        [(_reservation(reservation_id="RES-1", cycle_id="cyc-1"), True)]
    )
    await worker._v2_journal_reconciliation_decisions(
        [
            (
                _reservation(reservation_id="RES-1", cycle_id="cyc-1"),
                RECONCILIATION_KEEP,
                None,
                True,
                None,
            )
        ]
    )


# ── v2.88.25 — la ORDEN DE ENTRADA y la LIQUIDACIÓN dejan su traza en el spine ───────


@pytest.mark.asyncio
async def test_entry_order_is_persisted_with_account_and_engine() -> None:
    """El productor sella ``account_id`` y ``payload.engineId`` y conserva pedido vs aplicado."""
    sink = _Collector()
    worker = _worker(sink=sink)
    await worker._v2_journal_entry_order(
        order_id="ORD-1",
        instrument_id="AAA",
        requested_qty=100,
        applied_qty=73.5,
        partial=True,
        cycle_id="cyc-aaa",
    )

    assert len(sink.entries) == 1
    entry = sink.entries[0]
    assert entry.event_type == AUTO_ENTRY_ORDER_EVENT
    assert entry.account_id == _ACCOUNT
    assert entry.payload is not None
    assert entry.payload["engineId"] == "auto-sim"
    assert entry.payload["orderId"] == "ORD-1"
    assert entry.payload["requestedQty"] == 100.0
    assert entry.payload["appliedQty"] == 73.5
    assert entry.payload["partial"] is True
    # Sin ``PriceSource`` inyectada y con el script hermético, la fuente es SYNTHETIC.
    assert entry.payload["priceSource"] == "SYNTHETIC"
    assert entry.payload["cycleId"] == "cyc-aaa"


@pytest.mark.asyncio
async def test_entry_order_without_a_sink_is_a_declared_noop() -> None:
    worker = _worker(sink=None)
    await worker._v2_journal_entry_order(
        order_id="ORD-1",
        instrument_id="AAA",
        requested_qty=100,
        applied_qty=100,
        partial=False,
        cycle_id="cyc-aaa",
    )
    assert worker._operational_audit_sink is None


def test_seal_identity_keeps_a_producer_engine_id() -> None:
    """El sello de trazado NO pisa un ``engineId`` ya declarado por el productor."""
    worker = _worker(sink=None)
    entry = build_entry_order_entry(
        order_id="ORD-1",
        instrument_id="AAA",
        side="buy",
        requested_qty=100,
        applied_qty=100,
        partial=False,
        price_source="MARKET_CLOSE",
        cycle_id="cyc-aaa",
        actor="auto-sim",
        as_of="2026-10-01T10:00:00Z",
    )
    assert entry is not None
    from dataclasses import replace as _replace

    entry = _replace(entry, payload={**(entry.payload or {}), "engineId": "auto-otro"})
    sealed = worker._v2_seal_audit_identity(entry)
    assert sealed.payload["engineId"] == "auto-otro"


@pytest.mark.asyncio
async def test_cycle_settlement_is_persisted_with_declared_pnl_measurement() -> None:
    """Sin store de fills el PnL se DECLARA no medido (``UNKNOWN``), nunca una cifra fingida."""
    sink = _Collector()
    worker = _worker(sink=sink)
    await worker._v2_journal_cycle_settlement(
        instrument_id="AAA",
        closed_qty=10,
        cycle_id="cyc-aaa",
        exit_reason="time_exit",
    )

    assert len(sink.entries) == 1
    entry = sink.entries[0]
    assert entry.event_type == AUTO_CYCLE_SETTLEMENT_EVENT
    assert entry.account_id == _ACCOUNT
    assert entry.payload is not None
    assert entry.payload["engineId"] == "auto-sim"
    assert entry.payload["pnl"] is None
    assert entry.payload["pnlMeasurement"] == "UNKNOWN"
    assert entry.payload["closedQty"] == 10.0
    assert entry.payload["cycleId"] == "cyc-aaa"


@pytest.mark.asyncio
async def test_cycle_settlement_without_a_sink_is_a_declared_noop() -> None:
    worker = _worker(sink=None)
    await worker._v2_journal_cycle_settlement(
        instrument_id="AAA",
        closed_qty=10,
        cycle_id="cyc-aaa",
        exit_reason=None,
    )
    assert worker._operational_audit_sink is None


# ── v2.88.26 — la PROTECCIÓN deja su traza en el spine ───────────────────────────────


@pytest.mark.asyncio
async def test_protection_is_persisted_with_account_and_engine() -> None:
    """El productor sella ``account_id``/``engineId`` y conserva before→after y la transición."""
    sink = _Collector()
    worker = _worker(sink=sink)
    await worker._v2_journal_protection(
        kind="STOP_RATCHET_APPLIED",
        instrument_id="AAA",
        cycle_id="cyc-aaa",
        position_id="pos-1",
        lifecycle_from="T1_REACHED",
        lifecycle_to="TRAILING",
        stop_before=95.0,
        stop_after=99.0,
        trailing_status="armed",
        revision_id="REV-1",
        source="protect",
    )

    assert len(sink.entries) == 1
    entry = sink.entries[0]
    assert entry.event_type == AUTO_PROTECTION_EVENT
    assert entry.account_id == _ACCOUNT
    assert entry.payload is not None
    assert entry.payload["engineId"] == "auto-sim"
    assert entry.payload["kind"] == "STOP_RATCHET_APPLIED"
    assert entry.payload["lifecycleFrom"] == "T1_REACHED"
    assert entry.payload["lifecycleTo"] == "TRAILING"
    assert entry.payload["stopBefore"] == 95.0
    assert entry.payload["stopAfter"] == 99.0
    assert entry.payload["trailingStatus"] == "armed"
    assert entry.payload["revisionId"] == "REV-1"
    assert entry.payload["cycleId"] == "cyc-aaa"


@pytest.mark.asyncio
async def test_protection_without_a_cycle_is_a_declared_noop() -> None:
    """Sin ``cycle_id`` no se puede atar el hecho al ciclo: el builder no lo finge."""
    sink = _Collector()
    worker = _worker(sink=sink)
    await worker._v2_journal_protection(
        kind="PROTECT_APPLIED",
        instrument_id="AAA",
        cycle_id=None,
    )
    assert sink.entries == []


@pytest.mark.asyncio
async def test_protection_without_a_sink_is_a_declared_noop() -> None:
    worker = _worker(sink=None)
    await worker._v2_journal_protection(
        kind="PROTECT_APPLIED",
        instrument_id="AAA",
        cycle_id="cyc-aaa",
    )
    assert worker._operational_audit_sink is None


@pytest.mark.asyncio
async def test_a_broken_sink_on_protection_does_not_tumble_the_turn() -> None:
    """Publicar no puede tumbar el turno: el fallo se registra y la traza se declara perdida."""
    worker = _worker(sink=_BrokenSink())
    await worker._v2_journal_protection(
        kind="PROTECT_APPLIED",
        instrument_id="AAA",
        cycle_id="cyc-aaa",
    )
