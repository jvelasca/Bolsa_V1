"""AUTO-MATERIAL-1 — el gate de material PAPER mide, declara y NUNCA repara material.

Estos tests fijan las tres reglas duras del diagnóstico:

* el material legacy (fills sin ``cycle_id`` y sin reservas) se declara **BLOQUEADO** con sus
  motivos —faltan linaje, cierres y denominador—, no se «arregla»;
* el material del pipeline AUTO 2.0 (ciclos con reserva de entrada con riesgo positivo) es
  **READY** solo si alcanza el mínimo de ciclos medibles por estrategia;
* el gate jamás deriva ``cycle_id`` ni ``reserved_risk`` de la cantidad/precio de un fill.
"""

from __future__ import annotations

from decimal import Decimal

from bolsa_analytics.cognitive.portfolio_reservation import (
    RESERVATION_OPEN,
    RESERVATION_RELEASED_BY_FILL,
    SIDE_BUY,
    SIDE_SELL,
    PortfolioReservation,
)
from bolsa_application.paper_material_readiness import (
    BLOCKER_INSUFFICIENT_MEASURABLE_CYCLES,
    BLOCKER_NO_CLOSED_CYCLES,
    BLOCKER_NO_CYCLE_LINEAGE,
    BLOCKER_NO_EXIT_ORDERS,
    BLOCKER_NO_RESERVATIONS,
    BLOCKER_PRODUCER_PATH_NOT_EXERCISED,
    MATERIAL_READINESS_METHOD,
    READINESS_BLOCKED,
    READINESS_EVIDENCE_READY,
    READINESS_PRODUCER_READY,
    READINESS_READY,
    build_paper_material_readiness,
)
from bolsa_application.sim_durable_store import SimFillFinanceContext


def _fill(
    side: str,
    qty: str,
    price: str,
    *,
    execution_id: str,
    cycle_id: str | None,
    version: str = "orb-a",
) -> SimFillFinanceContext:
    return SimFillFinanceContext(
        execution_id=execution_id,
        instrument_id="AAA",
        side=side,
        quantity=Decimal(qty),
        price=Decimal(price),
        account_id="acc-1",
        strategy_version_id=version,
        cycle_id=cycle_id,
    )


def _round_trip(cycle_id: str, *, version: str = "orb-a") -> list[SimFillFinanceContext]:
    return [
        _fill("buy", "10", "100", execution_id=f"{cycle_id}-buy", cycle_id=cycle_id, version=version),
        _fill(
            "sell", "10", "110", execution_id=f"{cycle_id}-sell", cycle_id=cycle_id, version=version
        ),
    ]


def _reservation(
    cycle_id: str,
    *,
    reservation_id: str | None = None,
    risk: float | None = 250.0,
    side: str = SIDE_BUY,
) -> PortfolioReservation:
    return PortfolioReservation(
        reservation_id=reservation_id or f"RES-{cycle_id}",
        account_id="acc-1",
        instrument_id="AAA",
        side=side,
        quantity=10.0,
        entry=100.0,
        stop=95.0,
        reserved_cash=1000.0 if side == SIDE_BUY else 0.0,
        reserved_risk=risk,
        status=RESERVATION_OPEN,
        created_at="2026-09-26T08:00:00+00:00",
        remaining_qty=10.0,
        cycle_id=cycle_id,
    )


def test_legacy_material_is_blocked_and_declares_every_missing_link() -> None:
    """761-fills-like material: hay actividad, pero ni linaje, ni cierres, ni denominador."""
    fills = [
        _fill("buy", "10", "100", execution_id=f"legacy-{i}", cycle_id=None) for i in range(4)
    ]

    readiness = build_paper_material_readiness(
        account_id="acc-1",
        requested_versions=["orb-a"],
        fills=fills,
        reservations=[],
        min_cycles_per_strategy=3,
    )

    assert readiness.verdict == READINESS_BLOCKED
    assert readiness.ready is False
    assert readiness.facts["durableFills"] == 4
    assert readiness.facts["fillsWithCycle"] == 0
    assert readiness.facts["buys"] == 4
    assert readiness.facts["sells"] == 0
    assert readiness.facts["closedCycles"] == 0
    assert readiness.facts["measurableCycles"] == 0
    for blocker in (
        BLOCKER_NO_CYCLE_LINEAGE,
        BLOCKER_NO_RESERVATIONS,
        BLOCKER_NO_CLOSED_CYCLES,
        BLOCKER_INSUFFICIENT_MEASURABLE_CYCLES,
        BLOCKER_PRODUCER_PATH_NOT_EXERCISED,
    ):
        assert blocker in readiness.blockers


def test_a_strategy_with_enough_measured_cycles_is_ready() -> None:
    fills = [fill for cycle in ("cyc-a", "cyc-b", "cyc-c") for fill in _round_trip(cycle)]
    reservations = [_reservation(cycle) for cycle in ("cyc-a", "cyc-b", "cyc-c")]

    readiness = build_paper_material_readiness(
        account_id="acc-1",
        requested_versions=["orb-a"],
        fills=fills,
        reservations=reservations,
        min_cycles_per_strategy=3,
    )

    assert readiness.verdict == READINESS_READY
    assert readiness.blockers == ()
    assert readiness.facts["closedCycles"] == 3
    assert readiness.facts["measurableCycles"] == 3
    assert readiness.facts["maxMeasurableCyclesPerVersion"] == 3
    assert readiness.facts["versionsMeetingMinimum"] == ["orb-a"]
    assert readiness.lineage["closure"]["closedCyclesWithRisk"] == 3


def test_below_the_minimum_is_producer_ready_but_not_evidence_ready() -> None:
    """Estructura completa pero corta de muestra: "bien formado" ≠ "suficiente"."""
    fills = [fill for cycle in ("cyc-a", "cyc-b") for fill in _round_trip(cycle)]
    reservations = [_reservation(cycle) for cycle in ("cyc-a", "cyc-b")]

    readiness = build_paper_material_readiness(
        account_id="acc-1",
        requested_versions=["orb-a"],
        fills=fills,
        reservations=reservations,
        min_cycles_per_strategy=3,
    )

    assert readiness.verdict == READINESS_PRODUCER_READY
    assert readiness.producer_ready is True
    assert readiness.evidence_ready is False
    assert readiness.ready is False
    assert readiness.producer_blockers == ()
    assert readiness.facts["measurableCycles"] == 2
    assert BLOCKER_INSUFFICIENT_MEASURABLE_CYCLES in readiness.blockers
    assert BLOCKER_NO_CLOSED_CYCLES not in readiness.blockers


def test_measured_cycles_reach_evidence_ready_and_achieved_levels() -> None:
    """El nivel alcanzado distingue producer/evidence en el propio veredicto."""
    fills = [fill for cycle in ("cyc-a", "cyc-b", "cyc-c") for fill in _round_trip(cycle)]
    reservations = [_reservation(cycle) for cycle in ("cyc-a", "cyc-b", "cyc-c")]

    readiness = build_paper_material_readiness(
        account_id="acc-1",
        requested_versions=["orb-a"],
        fills=fills,
        reservations=reservations,
        min_cycles_per_strategy=3,
    )

    assert readiness.verdict == READINESS_EVIDENCE_READY
    assert readiness.achieved("producer") is True
    assert readiness.achieved("evidence") is True
    assert readiness.lineage["readiness"]["level"] == "evidence"


def test_a_complete_structure_without_exit_orders_is_blocked_when_measured() -> None:
    """Medir las salidas y no ver ninguna con ``cycle_id`` deja el productor incompleto."""
    fills = [fill for cycle in ("cyc-a", "cyc-b", "cyc-c") for fill in _round_trip(cycle)]
    reservations = [_reservation(cycle) for cycle in ("cyc-a", "cyc-b", "cyc-c")]

    readiness = build_paper_material_readiness(
        account_id="acc-1",
        requested_versions=["orb-a"],
        fills=fills,
        reservations=reservations,
        exit_orders=[{"cycle_id": None}, {"cycle_id": None}],
        min_cycles_per_strategy=3,
    )

    assert readiness.verdict == READINESS_BLOCKED
    assert BLOCKER_NO_EXIT_ORDERS in readiness.producer_blockers
    assert readiness.lineage["cycle"]["exitOrders"] == 2
    assert readiness.lineage["cycle"]["exitOrdersWithCycle"] == 0


def test_thresholds_are_declared_and_never_lowered_by_the_gate() -> None:
    """El gate no reduce el mínimo para forzar un READY: el hueco se declara."""
    fills = [fill for cycle in ("cyc-a", "cyc-b") for fill in _round_trip(cycle)]
    reservations = [_reservation(cycle) for cycle in ("cyc-a", "cyc-b")]

    readiness = build_paper_material_readiness(
        account_id="acc-1",
        requested_versions=["orb-a"],
        fills=fills,
        reservations=reservations,
        min_cycles_per_strategy=32,
    )

    assert readiness.verdict == READINESS_PRODUCER_READY
    assert readiness.facts["minCyclesPerStrategy"] == 32
    assert BLOCKER_INSUFFICIENT_MEASURABLE_CYCLES in readiness.blockers


def test_database_totals_are_declared_and_never_change_the_verdict() -> None:
    """La población TOTAL es informativa: separa "toda la tabla" del universo del instrumento."""
    fills = [fill for cycle in ("cyc-a", "cyc-b") for fill in _round_trip(cycle)]
    reservations = [_reservation(cycle) for cycle in ("cyc-a", "cyc-b")]

    without = build_paper_material_readiness(
        account_id="acc-1",
        requested_versions=["orb-a"],
        fills=fills,
        reservations=reservations,
        min_cycles_per_strategy=3,
    )
    with_totals = build_paper_material_readiness(
        account_id="acc-1",
        requested_versions=["orb-a"],
        fills=fills,
        reservations=reservations,
        min_cycles_per_strategy=3,
        database_totals={"fills": 761, "reservations": 0, "exitOrders": 0},
    )

    assert with_totals.verdict == without.verdict
    assert with_totals.facts["durableFills"] == 4
    assert with_totals.facts["databaseTotals"]["fills"] == 761
    assert "databaseTotals" not in without.facts


def test_closures_without_reservations_leave_r_unmeasurable() -> None:
    """Cerrar ciclos NO basta: sin ``reserved_risk`` no hay R medible (no se inventa capital)."""
    fills = [fill for cycle in ("cyc-a", "cyc-b", "cyc-c") for fill in _round_trip(cycle)]

    readiness = build_paper_material_readiness(
        account_id="acc-1",
        requested_versions=["orb-a"],
        fills=fills,
        reservations=[],
        min_cycles_per_strategy=3,
    )

    assert readiness.facts["closedCycles"] == 3
    assert readiness.facts["measurableCycles"] == 0
    assert BLOCKER_NO_CLOSED_CYCLES not in readiness.blockers
    assert BLOCKER_NO_RESERVATIONS in readiness.blockers
    assert BLOCKER_INSUFFICIENT_MEASURABLE_CYCLES in readiness.blockers


def test_a_sell_reservation_does_not_become_the_denominator() -> None:
    """Una reserva de venta (``reserved_risk = 0``) no es el denominador de R: hueco declarado."""
    fills = [fill for cycle in ("cyc-a", "cyc-b", "cyc-c") for fill in _round_trip(cycle)]
    reservations = [_reservation(cycle, risk=0.0, side=SIDE_SELL) for cycle in ("cyc-a", "cyc-b", "cyc-c")]

    readiness = build_paper_material_readiness(
        account_id="acc-1",
        requested_versions=["orb-a"],
        fills=fills,
        reservations=reservations,
        min_cycles_per_strategy=1,
    )

    assert readiness.facts["reservations"] == 3
    assert readiness.facts["measurableCycles"] == 0
    assert readiness.verdict == READINESS_BLOCKED


def test_a_released_entry_reservation_still_supplies_the_denominator() -> None:
    """Las reservas LIBERADAS cuentan (AUTO-9 + V2.74): al cerrar el ciclo la de ENTRADA ya no
    está viva, pero su ``reserved_risk`` (comprometido en el alta y conservado en la fila
    durable) es el único denominador de R del ciclo. Filtrar por ``is_live`` dejaría sin R
    justo los ciclos con resultado."""
    fills = [fill for cycle in ("cyc-a", "cyc-b", "cyc-c") for fill in _round_trip(cycle)]
    reservations = [
        _reservation(cycle, risk=250.0) for cycle in ("cyc-a", "cyc-b", "cyc-c")
    ]
    released = [
        PortfolioReservation(
            reservation_id=row.reservation_id,
            account_id="acc-1",
            instrument_id="AAA",
            side=SIDE_BUY,
            quantity=10.0,
            entry=100.0,
            stop=95.0,
            reserved_cash=0.0,
            reserved_risk=row.reserved_risk,
            status=RESERVATION_RELEASED_BY_FILL,
            created_at="2026-09-26T08:00:00+00:00",
            remaining_qty=0.0,
            cycle_id=row.cycle_id,
        )
        for row in reservations
    ]

    readiness = build_paper_material_readiness(
        account_id="acc-1",
        requested_versions=["orb-a"],
        fills=fills,
        reservations=released,
        min_cycles_per_strategy=3,
    )

    assert readiness.facts["reservationsLive"] == 0
    assert readiness.facts["measurableCycles"] == 3
    assert readiness.verdict == READINESS_EVIDENCE_READY


def test_a_released_entry_without_a_preserved_risk_stays_unmeasured() -> None:
    """Sin denominador no se inventa: liberar la reserva y perder el riesgo ⇒ R no medible."""
    fills = [fill for cycle in ("cyc-a", "cyc-b", "cyc-c") for fill in _round_trip(cycle)]
    released = [
        PortfolioReservation(
            reservation_id=f"RES-{cycle}",
            account_id="acc-1",
            instrument_id="AAA",
            side=SIDE_BUY,
            quantity=10.0,
            entry=100.0,
            stop=95.0,
            reserved_cash=0.0,
            reserved_risk=0.0,
            status=RESERVATION_RELEASED_BY_FILL,
            created_at="2026-09-26T08:00:00+00:00",
            remaining_qty=0.0,
            cycle_id=cycle,
        )
        for cycle in ("cyc-a", "cyc-b", "cyc-c")
    ]

    readiness = build_paper_material_readiness(
        account_id="acc-1",
        requested_versions=["orb-a"],
        fills=fills,
        reservations=released,
        min_cycles_per_strategy=1,
    )

    assert readiness.facts["closedCycles"] == 3
    assert readiness.facts["measurableCycles"] == 0
    assert readiness.verdict == READINESS_BLOCKED


def test_exit_order_lineage_is_declared_and_never_invented() -> None:
    fills = [fill for cycle in ("cyc-a", "cyc-b", "cyc-c") for fill in _round_trip(cycle)]
    reservations = [_reservation(cycle) for cycle in ("cyc-a", "cyc-b", "cyc-c")]

    measured = build_paper_material_readiness(
        account_id="acc-1",
        requested_versions=["orb-a"],
        fills=fills,
        reservations=reservations,
        exit_orders=[{"cycle_id": "cyc-a"}, {"cycle_id": "cyc-b"}, {"cycle_id": None}],
        min_cycles_per_strategy=3,
    )
    assert measured.lineage["cycle"]["exitOrders"] == 3
    assert measured.lineage["cycle"]["exitOrdersWithCycle"] == 2

    not_measured = build_paper_material_readiness(
        account_id="acc-1",
        requested_versions=["orb-a"],
        fills=fills,
        reservations=reservations,
        exit_orders=None,
        min_cycles_per_strategy=3,
    )
    # No medido es ``None``, nunca un cero que diría "no hay ninguno".
    assert not_measured.lineage["cycle"]["exitOrders"] is None
    assert not_measured.lineage["cycle"]["exitOrdersWithCycle"] is None


def test_the_payload_declares_its_seal_and_the_declared_minimum() -> None:
    readiness = build_paper_material_readiness(
        account_id="acc-1",
        requested_versions=["orb-a"],
        fills=[],
        reservations=[],
    )

    payload = readiness.as_dict()
    assert payload["schema"] == MATERIAL_READINESS_METHOD
    assert payload["verdict"] == READINESS_BLOCKED
    assert payload["ready"] is False
    assert payload["facts"]["minCyclesPerStrategy"] == 32
    assert payload["facts"]["executionReality"] == "VIRTUAL — NO REAL MONEY"
