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
    SIDE_BUY,
    SIDE_SELL,
    PortfolioReservation,
)
from bolsa_application.paper_material_readiness import (
    BLOCKER_INSUFFICIENT_MEASURABLE_CYCLES,
    BLOCKER_NO_CLOSED_CYCLES,
    BLOCKER_NO_CYCLE_LINEAGE,
    BLOCKER_NO_RESERVATIONS,
    BLOCKER_PRODUCER_PATH_NOT_EXERCISED,
    MATERIAL_READINESS_METHOD,
    READINESS_BLOCKED,
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


def test_below_the_minimum_is_blocked_even_with_measured_cycles() -> None:
    fills = [fill for cycle in ("cyc-a", "cyc-b") for fill in _round_trip(cycle)]
    reservations = [_reservation(cycle) for cycle in ("cyc-a", "cyc-b")]

    readiness = build_paper_material_readiness(
        account_id="acc-1",
        requested_versions=["orb-a"],
        fills=fills,
        reservations=reservations,
        min_cycles_per_strategy=3,
    )

    assert readiness.verdict == READINESS_BLOCKED
    assert readiness.facts["measurableCycles"] == 2
    assert BLOCKER_INSUFFICIENT_MEASURABLE_CYCLES in readiness.blockers
    assert BLOCKER_NO_CLOSED_CYCLES not in readiness.blockers


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
