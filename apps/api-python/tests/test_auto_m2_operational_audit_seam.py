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
)
from bolsa_application.auto_operational_audit import (
    REASON_GRACE_WINDOW_KEEP,
    REASON_SESSION_OWNED,
    RECONCILIATION_KEEP,
    RECONCILIATION_RELEASE,
    build_reservation_claim_entry,
)
from bolsa_application.auto_operational_monitor import (
    AUTO_ENTRY_DECISION_EVENT,
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
