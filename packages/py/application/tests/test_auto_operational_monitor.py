"""Tests puros de ``auto_operational_monitor`` (M1) — proyección read-only de la cadena AUTO.

No hay I/O: se pasan hechos durables ya leídos (objetos ligeros) y se comprueba la forma del
DTO, el orden de pasos, la declaración de huecos (``unknown``/``absent`` con nota) y la
honestidad de no materializar ``0`` cuando no hay medida.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from bolsa_application.auto_operational_monitor import (
    AUTO_CYCLE_SETTLEMENT_EVENT,
    AUTO_ENTRY_DECISION_EVENT,
    AUTO_ENTRY_ORDER_EVENT,
    AUTO_PROTECTION_EVENT,
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
    price_source: str | None = None,
) -> Any:
    return SimpleNamespace(
        side=side,
        quantity=qty,
        price=price,
        cycle_id=cycle_id,
        reference_mid=reference_mid,
        # v2.88.25 — la FUENTE de precio realmente usada (migración 047).
        price_source=price_source,
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
    conflict: bool | None = None,
) -> Any:
    payload: dict[str, Any] = {
        "reservation_id": reservation_id,
        "claimed": claimed,
        "caller": session_id,
    }
    # ``conflict`` sólo viaja si el productor lo DECLARÓ: ausente = NO DECLARADO (UNKNOWN).
    if conflict is not None:
        payload["conflict"] = conflict
    return SimpleNamespace(
        decision_id="dec-1",
        created_at=created_at,
        session_id=session_id,
        payload=payload,
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


def test_last_conflict_measured_from_declared_race_only() -> None:
    """El último conflicto es la carrera DECLARADA más reciente; un claim perdido no lo es."""
    older = _claim(
        claimed=False, session_id="sess-a", created_at="2026-01-02T00:00:00Z", conflict=True
    )
    newer = _claim(
        claimed=False, session_id="sess-b", created_at="2026-01-04T00:00:00Z", conflict=True
    )
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


def test_last_conflict_ignores_lost_claim_without_declared_conflict() -> None:
    """Un claim perdido sin ``conflict`` es ``lostClaims``, NO una carrera: ``lastConflict`` None."""
    dto = build_operational_monitor(
        account_id="acc-1",
        reservations=[_reservation()],
        claim_entries=[_claim(claimed=False, session_id="sess-loser")],
    )
    concurrency = dto["concurrency"]
    assert concurrency["lostClaims"] == 1
    assert concurrency["raceConflicts"] == 0
    assert concurrency["lastConflict"] is None
    # Los claims SÍ se midieron (hay filas): la afirmación "no hay carrera declarada" es completa.
    assert concurrency["lastConflictMeasurement"] == "COMPLETE"


def test_concurrency_uses_aggregate_counts_independent_from_row_window() -> None:
    """El agregado manda: contadores COMPLETE aunque la ventana de filas esté vacía/truncada."""
    dto = build_operational_monitor(
        account_id="acc-1",
        reservations=[_reservation()],
        claim_entries=[],
        concurrency_counts={
            "claimAttempts": 347,
            "successfulClaims": 100,
            "lostClaims": 247,
            "raceConflicts": 3,
            "lostClaimsUndeclaredConflict": 0,
            "reconciliations": 12,
            "graceWindowKeeps": 2,
        },
    )
    concurrency = dto["concurrency"]
    # 347 (no 100 por el ``limit``): el conteo sale de la base, no de las filas cargadas.
    assert concurrency["claimAttempts"] == 347
    assert concurrency["successfulClaims"] == 100
    assert concurrency["lostClaims"] == 247
    assert concurrency["raceConflicts"] == 3
    assert concurrency["raceConflictsMeasurement"] == "COMPLETE"
    assert concurrency["claimAttemptsMeasurement"] == "COMPLETE"
    assert concurrency["reconciliations"] == 12
    assert concurrency["graceWindowKeeps"] == 2


def test_concurrency_marks_race_partial_when_conflicts_are_undeclared() -> None:
    """Claims perdidos sin ``conflict`` declarado ⇒ ``raceConflicts`` no puede ser COMPLETE."""
    dto = build_operational_monitor(
        account_id="acc-1",
        reservations=[_reservation()],
        concurrency_counts={
            "claimAttempts": 5,
            "successfulClaims": 1,
            "lostClaims": 4,
            "raceConflicts": 1,
            "lostClaimsUndeclaredConflict": 2,
            "reconciliations": 0,
            "graceWindowKeeps": 0,
        },
    )
    concurrency = dto["concurrency"]
    assert concurrency["raceConflicts"] == 1
    assert concurrency["raceConflictsMeasurement"] == "PARTIAL"
    # El total y el desglose de claims SÍ son completos.
    assert concurrency["claimAttemptsMeasurement"] == "COMPLETE"
    assert concurrency["lostClaimsMeasurement"] == "COMPLETE"
    # El agregado SE EJECUTÓ y devolvió 0 reconciliaciones: es una medición COMPLETA
    # ("cero eventos"), no un hueco. Solo la ausencia de lectura sería UNKNOWN.
    assert concurrency["reconciliations"] == 0
    assert concurrency["reconciliationsMeasurement"] == "COMPLETE"


def test_concurrency_marks_partial_when_row_window_is_truncated() -> None:
    """Sin agregado: el ``total`` de ``list_entries`` acota el conteo y el desglose es PARTIAL."""
    dto = build_operational_monitor(
        account_id="acc-1",
        reservations=[_reservation()],
        claim_entries=[_claim(claimed=True, session_id="sess-a")],
        claims_total=250,
    )
    concurrency = dto["concurrency"]
    assert concurrency["claimAttempts"] == 250
    assert concurrency["claimAttemptsMeasurement"] == "COMPLETE"
    # El desglose por estado NO puede afirmarse sobre 1 fila de 250.
    assert concurrency["successfulClaimsMeasurement"] == "PARTIAL"
    assert concurrency["lostClaimsMeasurement"] == "PARTIAL"
    assert concurrency["raceConflictsMeasurement"] == "PARTIAL"


def test_concurrency_forced_releases_use_the_aggregate_when_available() -> None:
    """El agregado manda sobre la ventana: ``forcedReleases`` completo aunque la ventana se trunque."""
    dto = build_operational_monitor(
        account_id="acc-1",
        reservations=[_reservation()],
        limit=1,
        forced_releases_total=42,
    )
    concurrency = dto["concurrency"]
    assert concurrency["forcedReleases"] == 42
    assert concurrency["forcedReleasesMeasurement"] == "COMPLETE"


def test_concurrency_forced_releases_partial_when_the_reservation_window_is_full() -> None:
    """Sin agregado: con la ventana LLENA (``len == limit``) el conteo puede estar truncado."""
    dto = build_operational_monitor(
        account_id="acc-1",
        reservations=[
            _reservation(reservation_id="res-1", cycle_id="cyc-1"),
            _reservation(reservation_id="res-2", cycle_id="cyc-2"),
        ],
        limit=1,
    )
    concurrency = dto["concurrency"]
    # Ambas tienen ``release_reason='fill'``: no son retiradas forzadas, pero el conteo de la
    # ventana no puede afirmarse completo con la ventana llena.
    assert concurrency["forcedReleases"] == 0
    assert concurrency["forcedReleasesMeasurement"] == "PARTIAL"


def test_concurrency_forced_releases_complete_when_the_window_is_not_full() -> None:
    dto = build_operational_monitor(
        account_id="acc-1",
        reservations=[_reservation()],
        limit=20,
    )
    concurrency = dto["concurrency"]
    assert concurrency["forcedReleases"] == 0
    assert concurrency["forcedReleasesMeasurement"] == "COMPLETE"


def test_concurrency_forced_releases_counts_forced_reasons_in_the_window() -> None:
    dto = build_operational_monitor(
        account_id="acc-1",
        reservations=[_reservation(release_reason="cancel")],
        limit=20,
    )
    concurrency = dto["concurrency"]
    assert concurrency["forcedReleases"] == 1
    assert concurrency["forcedReleasesMeasurement"] == "COMPLETE"


def test_header_uses_global_decision_entries_over_visible_cycle_journal() -> None:
    """``lastDecisionAt`` sale de la lectura GLOBAL, no de los ciclos/reservas visibles."""
    entry = SimpleNamespace(
        decision_id="dec-global",
        event_type=AUTO_ENTRY_DECISION_EVENT,
        created_at="2026-01-05T09:00:00Z",
        session_id="sess-a",
        payload={"cycleId": "cyc-otro", "instrumentId": "AAPL"},
    )
    dto = build_operational_monitor(
        account_id="acc-1",
        engine=_engine(),
        reservations=[_reservation()],
        journal=[],
        header_decision_entries=[entry],
        interval_seconds=3600.0,
    )
    header = dto["header"]
    assert header["lastDecisionAt"] == "2026-01-05T09:00:00Z"
    assert header["lastDecisionMeasurement"] == "COMPLETE"
    assert header["nextDecisionAt"] == "2026-01-05T10:00:00Z"


def test_header_falls_back_to_cycle_journal_when_global_not_supplied() -> None:
    """Sin lectura global (``None``) el header conserva el journal del ciclo (compatibilidad)."""
    entry = SimpleNamespace(
        decision_id="dec-1",
        event_type=AUTO_ENTRY_DECISION_EVENT,
        created_at="2026-01-01T22:00:00Z",
        session_id="sess-a",
        payload={"cycleId": "cyc-1", "instrumentId": "AAPL"},
    )
    dto = build_operational_monitor(
        account_id="acc-1",
        engine=_engine(),
        reservations=[_reservation()],
        journal=[entry],
    )
    assert dto["header"]["lastDecisionAt"] == "2026-01-01T22:00:00Z"


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


def test_facts_without_value_are_never_declared_measured() -> None:
    """Un hecho SIN valor no puede viajar ``COMPLETE``: la UI lo rotularía ``MEDIDO``."""
    dto = build_operational_monitor(
        account_id="acc-1",
        reservations=[_reservation()],
        positions={
            "AAPL": {
                "positionState": {"cycleId": "cyc-1"},
                "stopPrice": None,
                "highWatermark": None,
                "t1State": None,
                "trailingState": None,
            }
        },
        # v2.88.26 — con el HECHO durable el paso se enciende; los facts proyectados SIN valor
        # siguen viajando ``UNKNOWN`` (no se rotulan medidos por el hecho).
        protection_events=[dict(_protection_event().payload)],
    )
    step = _step(dto["cycles"][0]["steps"], "PROTECTION")
    assert step["state"] == STEP_REACHED
    for key in ("stopPrice", "currentStop", "highWatermark", "t1State", "trailingState"):
        fact = _fact(step, key)
        assert fact["value"] is None
        assert fact["measurement"] == "UNKNOWN"


def test_fallback_marks_race_partial_on_undeclared_conflict() -> None:
    """Sin agregado, la ruta de filas debe degradar igual que el agregado ante conflicto no declarado."""
    dto = build_operational_monitor(
        account_id="acc-1",
        reservations=[_reservation()],
        claim_entries=[_claim(claimed=False, session_id="sess-loser")],
    )
    concurrency = dto["concurrency"]
    assert concurrency["lostClaims"] == 1
    assert concurrency["raceConflicts"] == 0
    assert concurrency["raceConflictsMeasurement"] == "PARTIAL"


def test_fill_with_unclassifiable_side_is_declared_partial_not_dropped() -> None:
    """Un ``side`` no clasificable no se descarta en silencio: el paso FILL se declara ``PARTIAL``."""
    dto = build_operational_monitor(
        account_id="acc-1",
        reservations=[_reservation()],
        fills=[
            _fill(side="buy", qty=10, price=100),
            _fill(side="", qty=5, price=101),
        ],
    )
    step = _step(dto["cycles"][0]["steps"], "FILL")
    assert step["measurement"] == "PARTIAL"
    assert step["note"] is not None and "fill_side_undeclared" in step["note"]
    # El bucket de compras SÍ se mide, pero es un suelo: la cantidad lo declara ``PARTIAL``.
    assert _fact(step, "buyQty")["measurement"] == "PARTIAL"
    assert _fact(step, "buyQty")["value"] == 10.0
    # Con un ``side`` no clasificable el neto está incompleto: tampoco se AFIRMA el cierre.
    assert dto["cycles"][0]["closed"] is None
    assert dto["cycles"][0]["closedMeasurement"] == "PARTIAL"


def test_fill_window_full_is_declared_partial() -> None:
    """Con la ventana de fills LLENA el paso FILL declara ``PARTIAL`` (pudo truncarse)."""
    dto = build_operational_monitor(
        account_id="acc-1",
        reservations=[_reservation()],
        fills=[_fill(side="buy", qty=10, price=100)],
        fills_window_full=True,
    )
    step = _step(dto["cycles"][0]["steps"], "FILL")
    assert step["measurement"] == "PARTIAL"
    assert step["note"] is not None and "fill_window_truncated" in step["note"]


def test_cycle_window_truncated_degrades_cycle_closed_and_pnl() -> None:
    """(A1) Ventana de fills truncada ⇒ NO se afirma CYCLE_CLOSED ni el PnL reconstruido.

    Con ``fills_total_by_cycle`` el ciclo declara 250 fills existentes frente a 2 cargados: el
    ``cycles_from_fills`` sobre el subconjunto puede reconstruir un cierre que la evidencia
    completa desmintiera, así que ``CYCLE_CLOSED`` pasa a ``unknown``/``PARTIAL`` y ``closed``/
    ``result`` dejan de afirmarse.
    """
    dto = build_operational_monitor(
        account_id="acc-1",
        reservations=[_reservation()],
        fills=[
            _fill(side="buy", qty=10, price=100),
            _fill(side="sell", qty=10, price=110),
        ],
        fills_total_by_cycle={"cyc-1": 250},
    )
    cycle = dto["cycles"][0]
    fill = _step(cycle["steps"], "FILL")
    assert fill["measurement"] == "PARTIAL"
    assert fill["note"] is not None and "fill_window_truncated" in fill["note"]
    closed_step = _step(cycle["steps"], "CYCLE_CLOSED")
    assert closed_step["state"] == STEP_UNKNOWN
    assert closed_step["measurement"] == "PARTIAL"
    assert closed_step["note"] == "cycle_closed_window_truncated"
    assert closed_step["facts"] == []
    assert cycle["closed"] is None
    assert cycle["closedMeasurement"] == "PARTIAL"
    assert cycle["result"] is None


def test_cycle_window_complete_keeps_cycle_closed_even_with_global_window_full() -> None:
    """(A1) La completitud es POR CICLO: un ciclo corto completo no se degrada por la ventana global.

    ``fills_window_full`` es solo el suelo cuando NO hay agregado. Con ``fills_total_by_cycle``
    que demuestra ``2/2``, el ciclo conserva su cierre y su PnL aunque la ventana global esté llena.
    """
    dto = build_operational_monitor(
        account_id="acc-1",
        reservations=[_reservation()],
        fills=[
            _fill(side="buy", qty=10, price=100),
            _fill(side="sell", qty=10, price=110),
        ],
        fills_window_full=True,
        fills_total_by_cycle={"cyc-1": 2},
    )
    cycle = dto["cycles"][0]
    assert _step(cycle["steps"], "FILL")["measurement"] == "COMPLETE"
    assert _step(cycle["steps"], "CYCLE_CLOSED")["state"] == STEP_REACHED
    assert cycle["closed"] is True
    assert cycle["closedMeasurement"] == "COMPLETE"
    assert cycle["result"]["pnl"] == 100


def test_cycle_window_full_without_aggregate_falls_back_to_global() -> None:
    """(A1) Sin agregado por ciclo el suelo GLOBAL vuelve a mandar (fail-closed)."""
    dto = build_operational_monitor(
        account_id="acc-1",
        reservations=[_reservation()],
        fills=[
            _fill(side="buy", qty=10, price=100),
            _fill(side="sell", qty=10, price=110),
        ],
        fills_window_full=True,
        fills_total_by_cycle=None,
    )
    cycle = dto["cycles"][0]
    assert _step(cycle["steps"], "CYCLE_CLOSED")["state"] == STEP_UNKNOWN
    assert cycle["closed"] is None
    assert cycle["result"] is None


def test_concurrency_aggregate_zero_is_measured_not_unknown() -> None:
    """(A2) El agregado EJECUTADO con COUNT=0 es evidencia COMPLETA, no un hueco ``UNKNOWN``."""
    dto = build_operational_monitor(
        account_id="acc-1",
        reservations=[_reservation()],
        concurrency_counts={
            "claimAttempts": 0,
            "successfulClaims": 0,
            "lostClaims": 0,
            "raceConflicts": 0,
            "lostClaimsUndeclaredConflict": 0,
            "reconciliations": 0,
            "graceWindowKeeps": 0,
        },
    )
    concurrency = dto["concurrency"]
    for key in (
        "claimAttempts",
        "successfulClaims",
        "lostClaims",
        "raceConflicts",
        "reconciliations",
        "graceWindowKeeps",
    ):
        assert concurrency[key] == 0
        assert concurrency[f"{key}Measurement"] == "COMPLETE"


# ── v2.88.25 — hechos durables: ENTRY_ORDER, SETTLEMENT y price_source por fill ──


def _entry_order_entry(**overrides: Any) -> Any:
    payload: dict[str, Any] = {
        "cycleId": "cyc-1",
        "orderId": "ORD-1",
        "instrumentId": "AAPL",
        "side": "buy",
        "requestedQty": 100.0,
        "appliedQty": 73.5,
        "partial": True,
        "priceSource": "MARKET_CLOSE",
    }
    payload.update(overrides)
    return SimpleNamespace(
        decision_id="dec-cyc-1",
        event_type=AUTO_ENTRY_ORDER_EVENT,
        created_at="2026-01-02T00:00:00Z",
        account_id="acc-1",
        payload=payload,
    )


def _settlement_event(**overrides: Any) -> Any:
    payload: dict[str, Any] = {
        "cycleId": "cyc-1",
        "settlementId": "SET-1",
        "closedQty": 10.0,
        "pnl": 100.0,
        "pnlMeasurement": "COMPLETE",
        "settledAt": "2026-01-02T03:00:00Z",
        "priceSource": "MARKET_CLOSE",
    }
    payload.update(overrides)
    return SimpleNamespace(
        decision_id="dec-cyc-1",
        event_type=AUTO_CYCLE_SETTLEMENT_EVENT,
        created_at="2026-01-02T03:00:00Z",
        account_id="acc-1",
        payload=payload,
    )


def test_order_step_reached_from_durable_entry_order_event() -> None:
    """La ORDEN DE ENTRADA durable enciende ``ORDER`` y expone pedido vs materializado."""
    dto = build_operational_monitor(
        account_id="acc-1",
        reservations=[_reservation()],
        journal=[_entry_order_entry()],
    )
    step = _step(dto["cycles"][0]["steps"], "ORDER")
    assert step["state"] == STEP_REACHED
    # Con hecho de entrada el hueco ya no se declara.
    assert step["note"] is None
    entry = _fact(step, "entryOrder")["value"]
    assert entry["orderId"] == "ORD-1"
    assert entry["requestedQty"] == 100.0
    assert entry["appliedQty"] == 73.5
    assert entry["partial"] is True
    assert entry["priceSource"] == "MARKET_CLOSE"


def test_order_step_declares_gap_when_only_exit_orders_are_durable() -> None:
    """Salida durable SIN hecho de entrada: el hueco se declara (no se esconde)."""
    order = SimpleNamespace(
        exit_order_id="EX-1",
        cycle_id="cyc-1",
        state="FILLED",
        requested_qty=10.0,
        filled_qty=10.0,
        remaining_qty=0.0,
        created_at="2026-01-02T01:00:00Z",
    )
    dto = build_operational_monitor(
        account_id="acc-1",
        reservations=[_reservation()],
        exit_orders=[order],
    )
    step = _step(dto["cycles"][0]["steps"], "ORDER")
    assert step["state"] == STEP_REACHED
    assert step["note"] == "entry_order_not_durable"
    assert _fact(step, "exitOrder")["value"]["exitOrderId"] == "EX-1"


def test_settlement_step_reached_from_durable_settlement_event() -> None:
    """Sólo el evento durable de liquidación enciende ``SETTLEMENT`` (no el ciclo cerrado)."""
    dto = build_operational_monitor(
        account_id="acc-1",
        reservations=[_reservation()],
        fills=[
            _fill(side="buy", qty=10, price=100, price_source="MARKET_CLOSE"),
            _fill(side="sell", qty=10, price=110, price_source="MARKET_CLOSE"),
        ],
        settlements=[dict(_settlement_event().payload)],
    )
    cycle = dto["cycles"][0]
    assert cycle["closed"] is True
    step = _step(cycle["steps"], "SETTLEMENT")
    assert step["state"] == STEP_REACHED
    assert _fact(step, "settlementId")["value"] == "SET-1"
    pnl = _fact(step, "pnl")
    assert pnl["value"] == 100.0
    assert pnl["measurement"] == "COMPLETE"


def test_settlement_partial_pnl_is_not_published_as_affirmed() -> None:
    """Un PnL marcado ``PARTIAL`` (evidencia truncada) viaja sin cifra y con su medición."""
    payload = dict(_settlement_event(pnl=None, pnlMeasurement="PARTIAL").payload)
    dto = build_operational_monitor(
        account_id="acc-1",
        reservations=[_reservation()],
        settlements=[payload],
    )
    step = _step(dto["cycles"][0]["steps"], "SETTLEMENT")
    assert step["state"] == STEP_REACHED
    pnl = _fact(step, "pnl")
    assert pnl["value"] is None
    assert pnl["measurement"] == "PARTIAL"


def test_fill_price_sources_measured_complete_when_every_fill_declares() -> None:
    dto = build_operational_monitor(
        account_id="acc-1",
        reservations=[_reservation()],
        fills=[
            _fill(side="buy", qty=10, price=100, price_source="MARKET_CLOSE"),
            _fill(side="sell", qty=10, price=110, price_source="MARKET_CLOSE"),
        ],
    )
    fact = _fact(_step(dto["cycles"][0]["steps"], "FILL"), "priceSources")
    assert fact["value"] == {"MARKET_CLOSE": 2}
    assert fact["measurement"] == "COMPLETE"


def test_fill_price_sources_partial_when_some_fills_lack_the_source() -> None:
    dto = build_operational_monitor(
        account_id="acc-1",
        reservations=[_reservation()],
        fills=[
            _fill(side="buy", qty=10, price=100, price_source="SYNTHETIC"),
            _fill(side="sell", qty=10, price=110),
        ],
    )
    fact = _fact(_step(dto["cycles"][0]["steps"], "FILL"), "priceSources")
    assert fact["value"] == {"SYNTHETIC": 1}
    assert fact["measurement"] == "PARTIAL"


def test_fill_price_sources_unknown_when_no_fill_declares_the_source() -> None:
    """Ninguna fuente declarada ⇒ ``None`` + ``UNKNOWN`` (nunca un ``{}`` que afirme "ninguna")."""
    dto = build_operational_monitor(
        account_id="acc-1",
        reservations=[_reservation()],
        fills=[_fill(side="buy", qty=10, price=100)],
    )
    fact = _fact(_step(dto["cycles"][0]["steps"], "FILL"), "priceSources")
    assert fact["value"] is None
    assert fact["measurement"] == "UNKNOWN"


# ── v2.88.26 — PROTECTION durable ──


def _protection_event(**overrides: Any) -> Any:
    payload: dict[str, Any] = {
        "cycleId": "cyc-1",
        "kind": "PROTECT_APPLIED",
        "instrumentId": "AAPL",
        "positionId": "pos-1",
        "lifecycleFrom": "OPEN",
        "lifecycleTo": "PROTECTED",
        "stopBefore": None,
        "stopAfter": 99.0,
        "target": None,
        "trailingStatus": None,
        "revisionId": "REV-1",
        "source": "plan",
        "at": "2026-01-02T00:30:00Z",
    }
    payload.update(overrides)
    return SimpleNamespace(
        decision_id="dec-cyc-1",
        event_type=AUTO_PROTECTION_EVENT,
        created_at="2026-01-02T00:30:00Z",
        account_id="acc-1",
        payload=payload,
    )


def test_protection_without_durable_event_is_declared_unknown_not_reached() -> None:
    """Sin hecho durable el paso NO se enciende con la proyección: ``protection_not_durable``."""
    dto = build_operational_monitor(
        account_id="acc-1",
        reservations=[_reservation()],
        positions={
            "AAPL": {
                "positionState": {"cycleId": "cyc-1", "currentStop": 99.0},
                "stopPrice": 99.0,
                "highWatermark": 101.0,
                "t1State": "pending",
                "trailingState": "off",
            }
        },
    )
    step = _step(dto["cycles"][0]["steps"], "PROTECTION")
    assert step["state"] == STEP_UNKNOWN
    assert step["measurement"] == "UNKNOWN"
    assert step["note"] == "protection_not_durable"
    # La proyección NO se presenta como medida: todos sus facts viajan ``UNKNOWN``.
    for key in ("stopPrice", "currentStop", "highWatermark", "t1State", "trailingState"):
        fact = _fact(step, key)
        assert fact["value"] is not None
        assert fact["measurement"] == "UNKNOWN"


def test_protection_reached_from_durable_event_and_exposes_the_transition() -> None:
    dto = build_operational_monitor(
        account_id="acc-1",
        reservations=[_reservation()],
        positions={
            "AAPL": {
                "positionState": {"cycleId": "cyc-1", "currentStop": 101.5},
                "stopPrice": 101.5,
                "highWatermark": 103.0,
                "t1State": "done",
                "trailingState": "armed",
            }
        },
        protection_events=[
            dict(
                _protection_event(
                    kind="TRAIL_ADVANCED",
                    lifecycleFrom="T1_REACHED",
                    lifecycleTo="TRAILING",
                    stopBefore=99.0,
                    stopAfter=101.5,
                    target=1,
                    trailingStatus="armed",
                ).payload
            )
        ],
    )
    step = _step(dto["cycles"][0]["steps"], "PROTECTION")
    assert step["state"] == STEP_REACHED
    assert step["measurement"] == "COMPLETE"
    assert step["note"] is None
    assert step["at"] == "2026-01-02T00:30:00Z"
    assert _fact(step, "protectionKind")["value"] == "TRAIL_ADVANCED"
    assert _fact(step, "lifecycleFrom")["value"] == "T1_REACHED"
    assert _fact(step, "lifecycleTo")["value"] == "TRAILING"
    assert _fact(step, "stopBefore")["value"] == 99.0
    assert _fact(step, "stopAfter")["value"] == 101.5
    assert _fact(step, "target")["value"] == 1
    assert _fact(step, "trailingStatus")["value"] == "armed"
    assert _fact(step, "revisionId")["value"] == "REV-1"
    # Con el hecho durable la proyección SÍ es medible.
    assert _fact(step, "currentStop")["value"] == 101.5
    assert _fact(step, "currentStop")["measurement"] == "COMPLETE"


def test_protection_keeps_the_latest_transition_of_the_cycle() -> None:
    dto = build_operational_monitor(
        account_id="acc-1",
        reservations=[_reservation()],
        protection_events=[
            dict(_protection_event(kind="PROTECT_APPLIED", at="2026-01-02T00:10:00Z").payload),
            dict(
                _protection_event(
                    kind="T2_HIT",
                    target=2,
                    at="2026-01-02T01:00:00Z",
                ).payload
            ),
            dict(
                _protection_event(
                    kind="T1_HIT",
                    target=1,
                    at="2026-01-02T00:40:00Z",
                ).payload
            ),
        ],
    )
    step = _step(dto["cycles"][0]["steps"], "PROTECTION")
    assert step["state"] == STEP_REACHED
    assert _fact(step, "protectionKind")["value"] == "T2_HIT"
    assert _fact(step, "target")["value"] == 2


def test_protection_exit_requested_without_materialization_is_declared() -> None:
    dto = build_operational_monitor(
        account_id="acc-1",
        reservations=[_reservation()],
        protection_events=[
            dict(_protection_event(kind="EXIT_REQUESTED", lifecycleTo="EXIT_PENDING").payload)
        ],
    )
    step = _step(dto["cycles"][0]["steps"], "PROTECTION")
    assert step["state"] == STEP_REACHED
    assert step["note"] == "protection_exit_requested_without_materialization"



