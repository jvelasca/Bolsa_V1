"""Tests puros de ``auto_operational_monitor`` (M1) — proyección read-only de la cadena AUTO.

No hay I/O: se pasan hechos durables ya leídos (objetos ligeros) y se comprueba la forma del
DTO, el orden de pasos, la declaración de huecos (``unknown``/``absent`` con nota) y la
honestidad de no materializar ``0`` cuando no hay medida.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from bolsa_application.auto_operational_monitor import (
    AUTO_ENTRY_DECISION_EVENT,
    OPERATIONAL_STEPS,
    STEP_ABSENT,
    STEP_REACHED,
    STEP_UNKNOWN,
    build_operational_monitor,
)


def _fill(
    *,
    side: str,
    qty: float,
    price: float,
    cycle_id: str = "cyc-1",
    reference_mid: float | None = None,
) -> Any:
    return SimpleNamespace(
        side=side,
        quantity=qty,
        price=price,
        cycle_id=cycle_id,
        reference_mid=reference_mid,
        created_at="2026-01-02T00:00:00Z",
        strategy_version_id="sv-1",
    )


def _engine(**overrides: Any) -> Any:
    base: dict[str, Any] = {
        "engine_id": "auto-sim",
        "state": "RUNNING",
        "venue": "paper",
        "last_tick_at": "2026-01-02T10:00:00Z",
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _reservation(**overrides: Any) -> Any:
    base: dict[str, Any] = {
        "reservation_id": "res-1",
        "cycle_id": "cyc-1",
        "side": "buy",
        "quantity": 10.0,
        "remaining_qty": 0.0,
        "released_qty": 10.0,
        "status": "RELEASED_BY_FILL",
        "created_at": "2026-01-01T00:00:00Z",
        "reserved_risk": 50.0,
        "stop": 95.0,
        "entry": 100.0,
        "instrument_id": "AAPL",
        "strategy_version_id": "sv-1",
        "release_reason": "fill",
        "is_live": False,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _step(steps: list[dict[str, Any]], step_id: str) -> dict[str, Any]:
    return next(step for step in steps if step["id"] == step_id)


def _fact(step: dict[str, Any], key: str) -> dict[str, Any]:
    return next(fact for fact in step["facts"] if fact["key"] == key)


def test_step_order_is_canonical() -> None:
    dto = build_operational_monitor(account_id="acc-1", reservations=[_reservation()])
    cycle = dto["cycles"][0]
    assert [step["id"] for step in cycle["steps"]] == list(OPERATIONAL_STEPS)
    assert dto["readOnly"] is True
    assert dto["key"] == "auto_operational_monitor_v1"


def test_signal_top_n_risk_declared_unknown_without_durable_journal() -> None:
    dto = build_operational_monitor(
        account_id="acc-1", reservations=[_reservation()], fills=[_fill(side="buy", qty=10, price=100)]
    )
    steps = dto["cycles"][0]["steps"]
    for step_id in ("SIGNAL", "TOP_N", "RISK"):
        step = _step(steps, step_id)
        assert step["state"] == STEP_UNKNOWN
        assert step["measurement"] == "UNKNOWN"
        assert step["note"] is not None
    assert "decision_journal_not_durable" in dto["notes"]


def test_journal_entry_turns_signal_reached() -> None:
    entry = SimpleNamespace(
        decision_id="dec-1",
        event_type=AUTO_ENTRY_DECISION_EVENT,
        created_at="2026-01-01T12:00:00Z",
        session_id="sess-a",
        payload={
            "cycleId": "cyc-1",
            "instrumentId": "AAPL",
            "strategyVersion": "sv-1",
            "rank": 1,
            "opportunityScore": 0.9,
        },
    )
    dto = build_operational_monitor(
        account_id="acc-1", reservations=[_reservation()], journal=[entry]
    )
    steps = dto["cycles"][0]["steps"]
    assert _step(steps, "SIGNAL")["state"] == STEP_REACHED
    assert _step(steps, "TOP_N")["state"] == STEP_REACHED
    assert _fact(_step(steps, "TOP_N"), "rank")["value"] == 1


def test_reservation_step_reaches_and_carries_durable_risk() -> None:
    dto = build_operational_monitor(account_id="acc-1", reservations=[_reservation()])
    step = _step(dto["cycles"][0]["steps"], "RESERVATION")
    assert step["state"] == STEP_REACHED
    risk = _fact(step, "reservedRisk")
    assert risk["value"] == 50.0
    assert risk["measurement"] == "COMPLETE"


def test_cycle_without_reservation_declares_absent_not_fabricated() -> None:
    dto = build_operational_monitor(
        account_id="acc-1",
        fills=[_fill(side="buy", qty=10, price=100)],
        cycle_id="cyc-1",
    )
    step = _step(dto["cycles"][0]["steps"], "RESERVATION")
    assert step["state"] == STEP_ABSENT
    assert step["note"] == "no_reservation_for_cycle"


def test_order_step_unknown_without_durable_exit_intent() -> None:
    dto = build_operational_monitor(account_id="acc-1", reservations=[_reservation()])
    step = _step(dto["cycles"][0]["steps"], "ORDER")
    assert step["state"] == STEP_UNKNOWN
    assert step["note"] == "entry_order_not_durable"


def test_fill_friction_never_materializes_zero_without_reference() -> None:
    dto = build_operational_monitor(
        account_id="acc-1",
        reservations=[_reservation()],
        fills=[_fill(side="buy", qty=10, price=100)],
    )
    step = _step(dto["cycles"][0]["steps"], "FILL")
    friction = _fact(step, "appliedFriction")
    assert friction["value"] is None
    assert friction["measurement"] == "UNKNOWN"
    assert _fact(step, "buyVwap")["value"] == 100.0


def test_fill_friction_partial_when_some_references_missing() -> None:
    dto = build_operational_monitor(
        account_id="acc-1",
        reservations=[_reservation()],
        fills=[
            _fill(side="buy", qty=10, price=100, reference_mid=99.9),
            _fill(side="sell", qty=10, price=110),
        ],
    )
    friction = _fact(_step(dto["cycles"][0]["steps"], "FILL"), "appliedFriction")
    assert friction["value"] is not None
    assert friction["measurement"] == "PARTIAL"


def test_closed_cycle_reuses_cycles_from_fills_for_pnl() -> None:
    dto = build_operational_monitor(
        account_id="acc-1",
        reservations=[_reservation()],
        fills=[
            _fill(side="buy", qty=10, price=100),
            _fill(side="sell", qty=10, price=110),
        ],
    )
    cycle = dto["cycles"][0]
    assert cycle["closed"] is True
    assert cycle["result"]["pnl"] == 100
    assert _step(cycle["steps"], "CYCLE_CLOSED")["state"] == STEP_REACHED
    # Un ciclo cerrado (``cycles_from_fills``) NO demuestra settlement durable.
    settlement = _step(cycle["steps"], "SETTLEMENT")
    assert settlement["state"] == STEP_UNKNOWN
    assert settlement["measurement"] == "UNKNOWN"
    assert settlement["note"] == "settlement_not_durable"


def test_settlement_is_unknown_and_never_derived_from_cycle_closed() -> None:
    """``fill + PnL + ciclo cerrado`` NO es un settlement durable (regla de la casa).

    Con una costura durable explícita (``settlements``) el paso SÍ alcanza; sin ella se declara.
    """
    dto = build_operational_monitor(
        account_id="acc-1",
        reservations=[_reservation()],
        fills=[
            _fill(side="buy", qty=10, price=100),
            _fill(side="sell", qty=10, price=110),
        ],
    )
    cycle = dto["cycles"][0]
    assert cycle["closed"] is True
    settlement = _step(cycle["steps"], "SETTLEMENT")
    assert settlement["state"] == STEP_UNKNOWN
    assert settlement["note"] == "settlement_not_durable"
    assert settlement["facts"] == []
    assert "settlement_not_durable" in cycle["notes"]

    durable = build_operational_monitor(
        account_id="acc-1",
        reservations=[_reservation()],
        fills=[_fill(side="buy", qty=10, price=100)],
        settlements=[
            {
                "cycle_id": "cyc-1",
                "settlementId": "SET-1",
                "pnl": 100,
                "settledAt": "2026-01-02T00:00:00Z",
            }
        ],
    )
    reached = _step(durable["cycles"][0]["steps"], "SETTLEMENT")
    assert reached["state"] == STEP_REACHED
    assert _fact(reached, "settlementId")["value"] == "SET-1"


def test_open_cycle_settlement_pending_and_not_closed() -> None:
    dto = build_operational_monitor(
        account_id="acc-1",
        reservations=[_reservation(status="OPEN", remaining_qty=10.0, released_qty=0.0, is_live=True)],
        fills=[_fill(side="buy", qty=10, price=100)],
    )
    cycle = dto["cycles"][0]
    assert cycle["closed"] is False
    assert _step(cycle["steps"], "SETTLEMENT")["state"] == STEP_UNKNOWN
    assert _step(cycle["steps"], "CYCLE_CLOSED")["state"] == "pending"


def test_reservation_view_ownership_declared_not_measured() -> None:
    dto = build_operational_monitor(
        account_id="acc-1",
        reservations=[_reservation()],
        reconciliation_entries=(),
        grace_seconds=30.0,
    )
    view = dto["reservations"][0]
    assert view["ownerSession"] is None
    assert view["ownerMeasurement"] == "UNKNOWN"
    assert view["state"] == "RELEASED"
    assert view["fillProgress"]["filled"] == 10.0
    assert view["expires"] is not None


def test_concurrency_declares_unmeasured_when_no_audit() -> None:
    dto = build_operational_monitor(account_id="acc-1", reservations=[_reservation()])
    concurrency = dto["concurrency"]
    for key in ("claimAttempts", "successfulClaims", "lostClaims", "raceConflicts"):
        assert concurrency[key] is None
        assert concurrency[f"{key}Measurement"] == "UNKNOWN"
    assert concurrency["reconciliations"] is None
    assert concurrency["forcedReleases"] == 0


def test_concurrency_counts_audit_entries_when_present() -> None:
    reconciliation = SimpleNamespace(
        decision_id="dec-1",
        created_at="2026-01-03T00:00:00Z",
        session_id="sess-a",
        payload={
            "reservation_id": "res-1",
            "caller": "sess-a",
            "decision": "KEEP",
            "reason": "grace_window_keep",
            "aged": False,
            "graceWindowSeconds": 30,
        },
    )
    claim = SimpleNamespace(
        decision_id="dec-1",
        created_at="2026-01-03T00:00:00Z",
        session_id="sess-b",
        payload={"reservation_id": "res-1", "claimed": False, "conflict": True},
    )
    dto = build_operational_monitor(
        account_id="acc-1",
        reservations=[_reservation()],
        reconciliation_entries=[reconciliation],
        claim_entries=[claim],
    )
    view = dto["reservations"][0]
    assert view["reconciliations"][0]["decision"] == "KEEP"
    concurrency = dto["concurrency"]
    assert concurrency["claimAttempts"] == 1
    assert concurrency["successfulClaims"] == 0
    assert concurrency["lostClaims"] == 1
    assert concurrency["raceConflicts"] == 1
    assert concurrency["graceWindowKeeps"] == 1
    assert concurrency["reconciliations"] == 1
    assert concurrency["activeSessions"] == 2
    assert "reconciliation_not_durable" not in dto["notes"]


def test_concurrency_separates_lost_claims_from_declared_race_conflicts() -> None:
    """``claimed=False`` NO equivale a carrera: solo cuenta como tal si el productor la declara."""
    lost_but_not_race = SimpleNamespace(
        decision_id="dec-1",
        created_at="2026-01-03T00:00:00Z",
        session_id="sess-a",
        payload={"reservation_id": "res-1", "claimed": False, "conflict": False},
    )
    declared_race = SimpleNamespace(
        decision_id="dec-1",
        created_at="2026-01-03T00:01:00Z",
        session_id="sess-b",
        payload={
            "reservation_id": "res-1",
            "claimed": False,
            "conflict": True,
            "conflictReason": "duplicate_claim",
        },
    )
    dto = build_operational_monitor(
        account_id="acc-1",
        reservations=[_reservation()],
        claim_entries=[lost_but_not_race, declared_race],
    )
    concurrency = dto["concurrency"]
    assert concurrency["claimAttempts"] == 2
    assert concurrency["successfulClaims"] == 0
    assert concurrency["lostClaims"] == 2
    assert concurrency["raceConflicts"] == 1


def _claim(
    *,
    claimed: bool,
    session_id: str,
    reservation_id: str = "res-1",
    created_at: str = "2026-01-03T00:00:00Z",
) -> Any:
    return SimpleNamespace(
        decision_id="dec-1",
        created_at=created_at,
        session_id=session_id,
        payload={
            "reservation_id": reservation_id,
            "claimed": claimed,
            "caller": session_id,
        },
    )


def test_owner_session_comes_from_won_claim_on_the_spine() -> None:
    """(``M2``) el dueño durable es la sesión del claim GANADO; no se infiere del proceso."""
    dto = build_operational_monitor(
        account_id="acc-1",
        reservations=[_reservation()],
        claim_entries=[_claim(claimed=True, session_id="sess-owner")],
    )
    view = dto["reservations"][0]
    assert view["ownerSession"] == "sess-owner"
    assert view["ownerMeasurement"] == "COMPLETE"
    assert "owner_session_not_durable" not in dto["notes"]


def test_owner_session_stays_unmeasured_without_won_claim() -> None:
    """Un claim PERDIDO no es propiedad: el dueño se declara ``NO MEDIDO``, no se inventa."""
    dto = build_operational_monitor(
        account_id="acc-1",
        reservations=[_reservation()],
        claim_entries=[_claim(claimed=False, session_id="sess-loser")],
    )
    view = dto["reservations"][0]
    assert view["ownerSession"] is None
    assert view["ownerMeasurement"] == "UNKNOWN"
    assert "owner_session_not_durable" in dto["notes"]


def test_last_conflict_measured_from_lost_claim() -> None:
    """El último conflicto es la carrera perdida más reciente; con claims sin carrera, ``None``."""
    older = _claim(claimed=False, session_id="sess-a", created_at="2026-01-02T00:00:00Z")
    newer = _claim(claimed=False, session_id="sess-b", created_at="2026-01-04T00:00:00Z")
    dto = build_operational_monitor(
        account_id="acc-1",
        reservations=[_reservation()],
        claim_entries=[older, newer],
    )
    conflict = dto["concurrency"]["lastConflict"]
    assert conflict["reservationId"] == "res-1"
    assert conflict["loserSession"] == "sess-b"
    assert dto["concurrency"]["lastConflictMeasurement"] == "COMPLETE"

    won = build_operational_monitor(
        account_id="acc-1",
        reservations=[_reservation()],
        claim_entries=[_claim(claimed=True, session_id="sess-owner")],
    )
    assert won["concurrency"]["lastConflict"] is None
    assert won["concurrency"]["lastConflictMeasurement"] == "COMPLETE"

    unknown = build_operational_monitor(account_id="acc-1", reservations=[_reservation()])
    assert unknown["concurrency"]["lastConflict"] is None
    assert unknown["concurrency"]["lastConflictMeasurement"] == "UNKNOWN"


def test_header_separates_last_heartbeat_from_last_decision() -> None:
    """El heartbeat del motor NUNCA se publica como 'última decisión'."""
    dto = build_operational_monitor(account_id="acc-1", engine=_engine())
    header = dto["header"]
    assert header["lastHeartbeatAt"] == "2026-01-02T10:00:00Z"
    assert header["lastHeartbeatMeasurement"] == "COMPLETE"
    assert header["lastDecisionAt"] is None
    assert header["lastDecisionMeasurement"] == "UNKNOWN"
    assert header["nextDecisionAt"] is None

    entry = SimpleNamespace(
        decision_id="dec-1",
        event_type=AUTO_ENTRY_DECISION_EVENT,
        created_at="2026-01-01T22:00:00Z",
        session_id="sess-a",
        payload={"cycleId": "cyc-1", "instrumentId": "AAPL", "rank": 1},
    )
    dto2 = build_operational_monitor(
        account_id="acc-1",
        engine=_engine(),
        reservations=[_reservation()],
        journal=[entry],
        interval_seconds=3600.0,
    )
    header2 = dto2["header"]
    assert header2["lastDecisionAt"] == "2026-01-01T22:00:00Z"
    assert header2["lastDecisionMeasurement"] == "COMPLETE"
    assert header2["nextDecisionAt"] == "2026-01-01T23:00:00Z"
    assert header2["lastHeartbeatAt"] == "2026-01-02T10:00:00Z"


def test_header_heartbeats_persisted_is_not_an_operational_event_count() -> None:
    dto = build_operational_monitor(account_id="acc-1", engine=_engine(), engine_ticks=1234)
    assert dto["header"]["heartbeatsPersisted"] == 1234
    assert dto["concurrency"]["heartbeatsPersisted"] == 1234
