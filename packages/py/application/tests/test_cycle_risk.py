"""AUTO-9 — tests del productor de riesgo por ciclo (read-only) y de su costura.

Lo que se prueba es la DISCIPLINA, no la aritmética: que el denominador de R sea UNO y
declarado (el de la reserva de entrada más antigua), que una reserva liberada siga sirviendo
(un ciclo cerrado ya no tiene reserva viva), que la ausencia se declare en vez de rellenarse
con un ``0``, y que sin productor el informe siga siendo **byte-idéntico** al de ``AUTO-7``.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from bolsa_analytics.cognitive.auto_self_evaluation import (
    SELF_EVAL_COST_BASIS_APPLIED,
    SELF_EVAL_COST_BASIS_ESTIMATED,
    cycle_r,
)
from bolsa_analytics.cognitive.measurement import (
    MEASUREMENT_COMPLETE,
    MEASUREMENT_PARTIAL,
    MEASUREMENT_UNKNOWN,
)
from bolsa_analytics.cognitive.portfolio_reservation import (
    RESERVATION_OPEN,
    RESERVATION_RELEASED_BY_FILL,
    SIDE_BUY,
    SIDE_SELL,
    PortfolioReservation,
    TradingCost,
)
from bolsa_application.applied_cost import applied_cost_from_fills
from bolsa_application.auto_self_evaluation_feed import build_auto_self_evaluation
from bolsa_application.cycle_risk import (
    CYCLE_RISK_MULTIPLE_RESERVATIONS,
    CYCLE_RISK_REGIME_NOT_DURABLE,
    CYCLE_RISK_REGIME_NOT_FOUND,
    CYCLE_RISK_UNDATED_RESERVATION,
    CYCLE_RISK_WITHOUT_RISK,
    CycleRisk,
    apply_cycle_risk,
    attach_applied_cost,
    cycle_risk_from_reservations,
)
from bolsa_application.sim_durable_store import SimFillFinanceContext


def _reservation(
    *,
    reservation_id: str = "res-1",
    side: str = SIDE_BUY,
    risk: float | None = 250.0,
    cost: TradingCost | None = None,
    cycle_id: str | None = "cyc-1",
    created_at: str | None = "2026-09-22T08:00:00+00:00",
    status: str = RESERVATION_OPEN,
) -> PortfolioReservation:
    return PortfolioReservation(
        reservation_id=reservation_id,
        account_id="acc-1",
        instrument_id="AAA",
        side=side,
        quantity=10.0,
        entry=100.0,
        stop=95.0,
        reserved_cash=1000.0 if side == SIDE_BUY else 0.0,
        reserved_risk=risk,
        cost=cost,
        status=status,  # type: ignore[arg-type]
        created_at=created_at,
        cycle_id=cycle_id,
    )


def _cost(total: float = 12.5, *, measurement: str = MEASUREMENT_COMPLETE) -> TradingCost:
    return TradingCost(
        notional=1000.0,
        commission=5.0,
        spread=4.0,
        slippage=3.5,
        gap=0.0,
        total=total,
        measurement=measurement,  # type: ignore[arg-type]
    )


def _fill(
    side: str,
    qty: str,
    price: str,
    *,
    execution_id: str,
    cycle_id: str | None = "cyc-1",
    reference_mid: str | None = None,
) -> SimFillFinanceContext:
    return SimFillFinanceContext(
        execution_id=execution_id,
        instrument_id="AAA",
        side=side,
        quantity=Decimal(qty),
        price=Decimal(price),
        reference_mid=reference_mid,
        strategy_version_id="orb-1",
        cycle_id=cycle_id,
    )


# ── El denominador: uno, y declarado ────────────────────────────────────────────────


def test_the_entry_reservation_is_the_denominator() -> None:
    evidence = cycle_risk_from_reservations(
        ["cyc-1"],
        [
            _reservation(reservation_id="res-entry", risk=250.0, cost=_cost()),
            _reservation(
                reservation_id="res-exit",
                side=SIDE_SELL,
                risk=0.0,
                created_at="2026-09-22T09:00:00+00:00",
            ),
        ],
    )["cyc-1"]

    assert evidence.risk_amount == Decimal("250.0")
    assert evidence.reservation_id == "res-entry"
    assert evidence.entry_reservations == 1
    assert evidence.risk_measurement == MEASUREMENT_COMPLETE
    assert evidence.cost_measurement == MEASUREMENT_COMPLETE
    assert CYCLE_RISK_WITHOUT_RISK not in evidence.notes


def test_a_released_entry_reservation_still_provides_the_denominator() -> None:
    """Un ciclo CERRADO ya no tiene reserva viva: filtrar por viva dejaría R en ``None``."""
    evidence = cycle_risk_from_reservations(
        ["cyc-1"],
        [_reservation(reservation_id="res-entry", risk=250.0, status=RESERVATION_RELEASED_BY_FILL)],
    )["cyc-1"]

    assert evidence.risk_amount == Decimal("250.0")
    assert evidence.risk_measurement == MEASUREMENT_COMPLETE


def test_the_oldest_entry_reservation_wins_and_the_rest_are_declared() -> None:
    """Se prohíbe repartir el riesgo entre varias: el denominador es UNO y se declara."""
    evidence = cycle_risk_from_reservations(
        ["cyc-1"],
        [
            _reservation(
                reservation_id="res-new",
                risk=999.0,
                created_at="2026-09-22T10:00:00+00:00",
            ),
            _reservation(
                reservation_id="res-old",
                risk=250.0,
                created_at="2026-09-22T08:00:00+00:00",
            ),
        ],
    )["cyc-1"]

    assert evidence.reservation_id == "res-old"
    assert evidence.risk_amount == Decimal("250.0")
    assert evidence.entry_reservations == 2
    assert CYCLE_RISK_MULTIPLE_RESERVATIONS in evidence.notes


# ── AUTO-11: el desempate se mide en INSTANTES, no en texto ─────────────────────────


def test_the_oldest_entry_reservation_is_measured_in_instants_not_in_text() -> None:
    """Dos formatos ISO distintos: el texto miente, el instante no.

    ``"08:00+02:00"`` es ANTERIOR a ``"07:00+00:00"`` (06:00 vs 07:00 UTC) aunque como cadena
    ordene después. Con la clave de texto anterior ganaba la fila equivocada en cuanto un origen
    serializara con offset distinto.
    """
    evidence = cycle_risk_from_reservations(
        ["cyc-1"],
        [
            _reservation(
                reservation_id="res-offset",
                risk=250.0,
                created_at="2026-09-22T08:00:00+02:00",
            ),
            _reservation(
                reservation_id="res-utc",
                risk=999.0,
                created_at="2026-09-22T07:00:00+00:00",
            ),
        ],
    )["cyc-1"]

    assert evidence.reservation_id == "res-offset", "06:00Z es anterior a 07:00Z"
    assert evidence.risk_amount == Decimal("250.0")
    assert CYCLE_RISK_MULTIPLE_RESERVATIONS in evidence.notes
    assert CYCLE_RISK_UNDATED_RESERVATION not in evidence.notes, "las dos filas se fechan"


def test_a_candidate_without_a_readable_instant_is_declared_not_silently_ordered() -> None:
    """Sin instante legible la fila va AL FINAL y el desempate se declara sin probar."""
    evidence = cycle_risk_from_reservations(
        ["cyc-1"],
        [
            _reservation(reservation_id="res-undated", risk=999.0, created_at=None),
            _reservation(
                reservation_id="res-dated",
                risk=250.0,
                created_at="2026-09-22T10:00:00+00:00",
            ),
        ],
    )["cyc-1"]

    assert evidence.reservation_id == "res-dated", "una fila sin fecha no puede ser 'la más vieja'"
    assert CYCLE_RISK_UNDATED_RESERVATION in evidence.notes


def test_an_undated_candidate_alone_does_not_declare_a_tie_break() -> None:
    """Con UNA sola candidata no hubo desempate: una nota que no cambia nada sería ruido."""
    evidence = cycle_risk_from_reservations(
        ["cyc-1"],
        [_reservation(reservation_id="res-undated", risk=250.0, created_at=None)],
    )["cyc-1"]

    assert evidence.reservation_id == "res-undated"
    assert evidence.risk_amount == Decimal("250.0")
    assert CYCLE_RISK_UNDATED_RESERVATION not in evidence.notes


def test_a_cycle_without_entry_reservation_declares_the_gap() -> None:
    evidence = cycle_risk_from_reservations(
        ["cyc-1"],
        [_reservation(side=SIDE_SELL, risk=0.0)],
    )["cyc-1"]

    assert evidence.risk_amount is None
    assert evidence.reservation_id is None
    assert evidence.entry_reservations == 0
    assert evidence.risk_measurement == MEASUREMENT_UNKNOWN
    assert CYCLE_RISK_WITHOUT_RISK in evidence.notes


def test_a_zero_risk_is_not_a_denominator() -> None:
    """``reserved_risk = 0`` (lo que declara una venta) no es un denominador: es un hueco."""
    evidence = cycle_risk_from_reservations(["cyc-1"], [_reservation(risk=0.0)])["cyc-1"]

    assert evidence.risk_amount is None
    assert CYCLE_RISK_WITHOUT_RISK in evidence.notes


def test_every_requested_cycle_appears_even_without_reservations() -> None:
    """Una ausencia en el mapa sería "no lo miré"; el hueco se declara por ciclo."""
    evidence = cycle_risk_from_reservations(["cyc-1", "cyc-2"], [])

    assert set(evidence) == {"cyc-1", "cyc-2"}
    assert all(row.risk_amount is None for row in evidence.values())
    assert all(CYCLE_RISK_WITHOUT_RISK in row.notes for row in evidence.values())


def test_reservations_of_other_cycles_and_rows_without_cycle_are_ignored() -> None:
    evidence = cycle_risk_from_reservations(
        ["cyc-1"],
        [
            _reservation(reservation_id="other", cycle_id="cyc-9", risk=999.0),
            _reservation(reservation_id="legacy", cycle_id=None, risk=999.0),
        ],
    )["cyc-1"]

    assert evidence.reservation_id is None
    assert evidence.risk_amount is None


def test_a_repeated_cycle_id_is_asked_once_and_keeps_the_input_order() -> None:
    evidence = cycle_risk_from_reservations(["cyc-2", "cyc-1", "cyc-2"], [])

    assert list(evidence) == ["cyc-2", "cyc-1"]


# ── El régimen: hueco declarado, nunca inventado ────────────────────────────────────


def test_the_regime_is_declared_as_a_durable_gap() -> None:
    """Hoy ningún ciclo tiene régimen legible de una fuente durable: se declara, no se finge."""
    evidence = cycle_risk_from_reservations(["cyc-1"], [_reservation()])["cyc-1"]

    assert evidence.regime is None
    assert evidence.regime_measurement == MEASUREMENT_UNKNOWN
    assert CYCLE_RISK_REGIME_NOT_DURABLE in evidence.notes


def test_a_declared_regime_closes_the_gap() -> None:
    evidence = cycle_risk_from_reservations(
        ["cyc-1"],
        [_reservation()],
        regime_by_cycle={"cyc-1": "TREND_UP"},
    )["cyc-1"]

    assert evidence.regime == "TREND_UP"
    assert evidence.regime_measurement == MEASUREMENT_COMPLETE
    assert CYCLE_RISK_REGIME_NOT_DURABLE not in evidence.notes


def test_a_durable_source_that_lacks_the_cycle_declares_not_found() -> None:
    """AUTO-10 — "la fuente se leyó y no lo tiene" NO es "no hay fuente": son dos huecos."""
    evidence = cycle_risk_from_reservations(
        ["cyc-1"],
        [_reservation()],
        regime_source_durable=True,
    )["cyc-1"]

    assert evidence.regime is None
    assert CYCLE_RISK_REGIME_NOT_FOUND in evidence.notes
    assert CYCLE_RISK_REGIME_NOT_DURABLE not in evidence.notes


def test_the_durable_flag_does_not_touch_a_measured_regime() -> None:
    """El flag solo cambia el MOTIVO del hueco: un régimen medido no se toca."""
    evidence = cycle_risk_from_reservations(
        ["cyc-1"],
        [_reservation()],
        regime_by_cycle={"cyc-1": "TREND_UP"},
        regime_source_durable=True,
    )["cyc-1"]

    assert evidence.regime == "TREND_UP"
    assert evidence.regime_measurement == MEASUREMENT_COMPLETE
    assert evidence.notes == ()


def test_as_dict_publishes_every_dimension_with_its_own_status() -> None:
    row = cycle_risk_from_reservations(["cyc-1"], [_reservation(cost=_cost(total=12.5))])[
        "cyc-1"
    ].as_dict()

    assert row["cycleId"] == "cyc-1"
    assert row["riskAmount"] == "250.0"
    assert row["costEstimate"]["total"] == 12.5
    assert row["reservationId"] == "res-entry" or row["reservationId"] == "res-1"
    assert row["riskMeasurement"] == MEASUREMENT_COMPLETE
    assert row["costMeasurement"] == MEASUREMENT_COMPLETE
    assert row["regimeMeasurement"] == MEASUREMENT_UNKNOWN
    assert CYCLE_RISK_REGIME_NOT_DURABLE in row["notes"]


# ── La costura con el informe ───────────────────────────────────────────────────────


def test_apply_cycle_risk_is_the_identity_without_evidence() -> None:
    """Sin productor, la ruta queda EXACTAMENTE como estaba (byte-identidad de AUTO-7)."""
    cycles = ({"cycleId": "cyc-1", "strategyVersion": "orb-1", "pnl": Decimal("50")},)

    assert apply_cycle_risk(cycles, None) == cycles
    assert apply_cycle_risk(cycles, {}) == cycles


def test_apply_cycle_risk_never_writes_an_unmeasured_field() -> None:
    """Un dato no medido no se emite: su clave sería indistinguible de una medida."""
    evidence = cycle_risk_from_reservations(["cyc-1"], [])
    fields = evidence["cyc-1"].to_cycle_fields()

    assert fields == {}


def test_apply_cycle_risk_only_touches_the_cycles_it_has_evidence_for() -> None:
    evidence = cycle_risk_from_reservations(["cyc-1"], [_reservation(risk=250.0)])
    cycles = (
        {"cycleId": "cyc-1", "strategyVersion": "orb-1", "pnl": Decimal("50")},
        {"cycleId": "cyc-2", "strategyVersion": "orb-1", "pnl": Decimal("10")},
    )

    enriched = apply_cycle_risk(cycles, evidence)

    assert enriched[0]["riskAmount"] == Decimal("250.0")
    assert "riskAmount" not in enriched[1]
    assert enriched[1] == cycles[1]


def test_the_feed_measures_the_r_when_the_producer_gives_the_denominator() -> None:
    fills = [
        _fill("buy", "10", "100", execution_id="e1"),
        _fill("sell", "10", "125", execution_id="e2"),
    ]
    without = build_auto_self_evaluation(fills=fills, min_trades=1)
    assert without.by_strategy[0].expectancy_r is None, "sin productor, R no es medible"

    evidence = cycle_risk_from_reservations(
        ["cyc-1"], [_reservation(risk=250.0, cost=_cost(total=25.0))]
    )
    report = build_auto_self_evaluation(fills=fills, min_trades=1, cycle_risk=evidence)
    row = report.by_strategy[0]

    assert row.expectancy_r == pytest.approx(1.0)  # 250 / 250
    assert row.net_expectancy_r == pytest.approx(0.9)  # (250 − 25) / 250
    assert row.net_r_measurement == MEASUREMENT_COMPLETE
    assert row.risk_measurement == MEASUREMENT_COMPLETE


def test_the_feed_declares_the_net_unmeasured_when_the_cost_is_missing() -> None:
    fills = [
        _fill("buy", "10", "100", execution_id="e1"),
        _fill("sell", "10", "125", execution_id="e2"),
    ]
    evidence = cycle_risk_from_reservations(["cyc-1"], [_reservation(risk=250.0)])

    row = build_auto_self_evaluation(fills=fills, min_trades=1, cycle_risk=evidence).by_strategy[0]

    assert row.expectancy_r == pytest.approx(1.0), "el bruto sí está medido"
    assert row.net_expectancy_r is None, "sin coste no hay neto: se declara, no se asume 0"
    assert row.cycles_without_cost == 1


def test_the_feed_opens_the_regime_cross_when_the_regime_is_declared() -> None:
    """El cruce `strategy × regime` deja de ser un único cubo UNKNOWN si hay régimen."""
    fills = [
        _fill("buy", "10", "100", execution_id="e1"),
        _fill("sell", "10", "125", execution_id="e2"),
    ]
    evidence = cycle_risk_from_reservations(
        ["cyc-1"],
        [_reservation(risk=250.0)],
        regime_by_cycle={"cyc-1": "TREND_UP"},
    )

    report = build_auto_self_evaluation(fills=fills, min_trades=1, cycle_risk=evidence)

    assert [cell.regime for cell in report.by_regime] == ["TREND_UP"]
    assert report.by_regime[0].expectancy_r == pytest.approx(1.0)
    assert report.cycles_without_regime == 0


# ── Gate §7.4 / §7.6 — honestidad del hueco y reproducibilidad ──────────────────────


def _evidence_for_cycles(
    cycle_ids: list[str], rows: list[PortfolioReservation]
) -> dict[str, CycleRisk]:
    return cycle_risk_from_reservations(cycle_ids, rows)


def test_the_producer_is_invariant_to_the_order_of_the_reservations() -> None:
    """§7.6 — mismo material ⇒ misma evidencia: el orden de las filas no es un dato."""
    rows = [
        _reservation(
            reservation_id="res-old",
            cycle_id="cyc-1",
            risk=250.0,
            created_at="2026-09-22T08:00:00+00:00",
        ),
        _reservation(
            reservation_id="res-new",
            cycle_id="cyc-1",
            risk=999.0,
            created_at="2026-09-22T10:00:00+00:00",
        ),
        _reservation(reservation_id="res-2", cycle_id="cyc-2", risk=100.0),
    ]
    forward = _evidence_for_cycles(["cyc-1", "cyc-2"], rows)
    backward = _evidence_for_cycles(["cyc-1", "cyc-2"], list(reversed(rows)))

    assert {key: row.as_dict() for key, row in forward.items()} == {
        key: row.as_dict() for key, row in backward.items()
    }
    assert forward["cyc-1"].reservation_id == "res-old", "el denominador no depende del orden"


def test_the_report_is_reproducible_from_the_same_evidence() -> None:
    """§7.6 — dos corridas con los mismos fills y reservas dan el mismo payload."""
    fills = [
        _fill("buy", "10", "100", execution_id="e1"),
        _fill("sell", "10", "125", execution_id="e2"),
    ]
    evidence = _evidence_for_cycles(["cyc-1"], [_reservation(risk=250.0, cost=_cost(25.0))])

    first = build_auto_self_evaluation(fills=fills, min_trades=1, cycle_risk=evidence).as_dict()
    second = build_auto_self_evaluation(fills=fills, min_trades=1, cycle_risk=evidence).as_dict()

    assert first == second


def test_no_surface_publishes_a_zero_where_the_gap_is_declared() -> None:
    """§7.4 — el hueco es ``None`` + motivo en TODA la superficie, nunca un `0.0`."""
    fills = [
        _fill("buy", "10", "100", execution_id="e1"),
        _fill("sell", "10", "125", execution_id="e2"),
    ]
    evidence = _evidence_for_cycles(["cyc-1"], [_reservation(risk=250.0)])  # sin coste
    report = build_auto_self_evaluation(fills=fills, min_trades=1, cycle_risk=evidence)

    row = report.by_strategy[0]
    assert row.net_expectancy_r is None
    assert row.net_expectancy_r != 0.0, "un hueco nunca se publica como cero"
    assert report.by_regime[0].net_expectancy_r is None
    payload = report.as_dict()
    assert payload["byStrategy"][0]["netExpectancyR"] is None
    assert row.cycles_without_cost == 1, "el motivo viaja con el hueco"


def test_a_cycle_without_measurement_does_not_become_a_zero_r_in_the_report() -> None:
    """§7.4 — sin reserva no hay R: la fila lo declara en vez de rellenarlo."""
    fills = [
        _fill("buy", "10", "100", execution_id="e1"),
        _fill("sell", "10", "125", execution_id="e2"),
    ]
    report = build_auto_self_evaluation(fills=fills, min_trades=1, cycle_risk={})
    row = report.by_strategy[0]

    assert row.expectancy_r is None
    assert row.expectancy_currency is not None, "lo que sí se midió sigue publicado"


# ── AUTO-16 — la fricción APLICADA por el simulador ─────────────────────────────────


def _round_trip_with_reference(*, reference: str | None = "100") -> list[SimFillFinanceContext]:
    """Ida y vuelta de 10 unidades con (o sin) el mid de referencia persistido."""
    return [
        _fill("buy", "10", "100.15", execution_id="e1", reference_mid=reference),
        _fill("sell", "10", "99.90", execution_id="e2", reference_mid=reference),
    ]


def test_attach_applied_cost_is_the_identity_without_applied_evidence() -> None:
    """Sin evidencia aplicada, el mapa queda TAL CUAL (misma disciplina que ``AUTO-9``)."""
    evidence = cycle_risk_from_reservations(["cyc-1"], [_reservation(risk=250.0)])

    assert attach_applied_cost(evidence, None) == evidence
    assert attach_applied_cost(evidence, {}) == evidence


def test_only_a_complete_round_trip_is_attached_to_the_cycle() -> None:
    """Un ``PARTIAL`` es un SUELO: se declara su medición y NO se pega como número."""
    evidence = cycle_risk_from_reservations(["cyc-1"], [_reservation(risk=250.0)])
    half = applied_cost_from_fills(["cyc-1"], [_fill("buy", "10", "100.15", execution_id="e1",
                                                    reference_mid="100")])

    attached = attach_applied_cost(evidence, half)["cyc-1"]

    assert half["cyc-1"].measurement == MEASUREMENT_PARTIAL
    assert attached.cost_applied is None, "medio viaje no es el coste del ciclo"
    assert attached.cost_applied_measurement == MEASUREMENT_PARTIAL, "el hueco se declara"
    assert attached.to_cycle_fields() == {"riskAmount": Decimal("250.0")}


def test_a_leg_without_reference_leaves_the_applied_cost_unmeasured() -> None:
    """Sin referencia persistida no hay fricción que afirmar — jamás un ``0``."""
    evidence = cycle_risk_from_reservations(["cyc-1"], [_reservation(risk=250.0)])
    applied = applied_cost_from_fills(["cyc-1"], _round_trip_with_reference(reference=None))

    attached = attach_applied_cost(evidence, applied)["cyc-1"]

    assert applied["cyc-1"].friction is None
    assert attached.cost_applied is None
    assert attached.cost_applied_measurement == MEASUREMENT_UNKNOWN
    assert attached.cost_applied != 0, "una referencia ausente nunca vale fricción cero"


def test_the_cycle_row_carries_the_applied_friction_with_its_measurement() -> None:
    """La fila publica el número Y su medición: sin la segunda, un suelo pasaría por total."""
    evidence = cycle_risk_from_reservations(["cyc-1"], [_reservation(risk=250.0)])
    applied = applied_cost_from_fills(["cyc-1"], _round_trip_with_reference())
    attached = attach_applied_cost(evidence, applied)["cyc-1"]

    fields = attached.to_cycle_fields()

    assert attached.cost_applied == Decimal("2.500000")  # 1.5 de la compra + 1.0 de la venta
    assert fields["costApplied"] == {
        "friction": "2.500000",
        "measurement": MEASUREMENT_COMPLETE,
    }
    assert attached.as_dict()["costAppliedMeasurement"] == MEASUREMENT_COMPLETE


def test_an_applied_cost_of_another_cycle_is_ignored() -> None:
    """No se fabrica evidencia de un ciclo que no se pidió medir."""
    evidence = cycle_risk_from_reservations(["cyc-1"], [_reservation(risk=250.0)])
    applied = applied_cost_from_fills(["cyc-2"], _round_trip_with_reference())

    attached = attach_applied_cost(evidence, applied)

    assert attached["cyc-1"].cost_applied is None


def test_the_net_comes_from_the_applied_friction_and_declares_its_basis() -> None:
    """El neto deja de salir de la SUPOSICIÓN del decisor cuando hay fricción medida."""
    evidence = _evidence_for_cycles(["cyc-1"], [_reservation(risk=250.0, cost=_cost(total=25.0))])

    report = build_auto_self_evaluation(
        fills=_round_trip_with_reference(), min_trades=1, cycle_risk=evidence
    )
    row = report.by_strategy[0]

    # pnl = 10 × (99.90 − 100.15) = −2.5; aplicado = 2.5 + comisión del modelo 5.0 ⇒ −10 / 250
    assert row.net_expectancy_r == pytest.approx(-0.04)
    assert row.net_r_basis == SELF_EVAL_COST_BASIS_APPLIED
    assert report.by_regime[0].net_r_basis == SELF_EVAL_COST_BASIS_APPLIED
    assert report.as_dict()["byStrategy"][0]["netRBasis"] == SELF_EVAL_COST_BASIS_APPLIED


def test_without_reference_the_net_is_the_estimated_number_of_v2_56() -> None:
    """El camino sin aplicado publica el MISMO número que ``v2.56`` y lo DECLARA."""
    evidence = _evidence_for_cycles(["cyc-1"], [_reservation(risk=250.0, cost=_cost(total=25.0))])

    row = build_auto_self_evaluation(
        fills=_round_trip_with_reference(reference=None), min_trades=1, cycle_risk=evidence
    ).by_strategy[0]
    legacy = cycle_r(
        pnl=Decimal("-2.5"), risk_amount=Decimal("250.0"), cost=_cost(total=25.0)
    )

    assert row.net_expectancy_r == legacy.net_r_multiple, "byte a byte: el estimado de siempre"
    assert row.net_expectancy_r == pytest.approx(-0.11)
    assert row.net_r_basis == SELF_EVAL_COST_BASIS_ESTIMATED, "la base viaja en la lectura"
