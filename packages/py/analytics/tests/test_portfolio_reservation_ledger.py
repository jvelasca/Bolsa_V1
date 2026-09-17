"""PortfolioReservation / ReservationLedger / PortfolioRiskState / TradingCost (AUTO-1).

Gate hermético de la fase: el libro de reservas es **cuadrado** (``reserved_cash`` == Σ
reservas vivas), **reproducible** (``replay`` de los eventos devuelve el mismo libro) y
**no se puede doblar** (dos altas con la misma identidad no reservan el mismo capital dos
veces). El coste real es fail-closed: sin stop no hay pérdida esperada, y "no la sé" nunca
vale 0.
"""

import pytest

from bolsa_analytics.cognitive.auto_portfolio_snapshot import PortfolioPosition
from bolsa_analytics.cognitive.measurement import (
    MEASUREMENT_COMPLETE,
    MEASUREMENT_PARTIAL,
    MEASUREMENT_UNKNOWN,
)
from bolsa_analytics.cognitive.portfolio_reservation import (
    RESERVATION_OPEN,
    RESERVATION_RELEASED_BY_CANCEL,
    RESERVATION_RELEASED_BY_FILL,
    RESERVATION_RELEASED_BY_RESTART,
    RESERVATION_RELEASED_BY_ROLLBACK,
    PortfolioReservation,
    ReservationLedger,
    TradingCostModel,
    build_portfolio_risk_state,
    build_reservation,
    coerce_reservation_status,
    coerce_trading_cost,
    estimate_trading_cost,
    replay,
    sector_risk_from_positions,
    stop_distance,
)
from bolsa_analytics.cognitive.risk_allocator import (
    CAP_COST_UNMEASURED,
    CAP_TRADING_COST,
    RiskAllocatorConfig,
    compute_allocation,
)
from bolsa_domain.account_settings import default_account_settings

# ── Alta de una reserva ───────────────────────────────────────────────────────────


def _reservation(
    reservation_id: str = "R1",
    *,
    instrument_id: str = "AAA",
    quantity: float = 100.0,
    entry: float = 50.0,
    risk: float | None = 500.0,
    sector: str | None = "tech",
    side: str = "buy",
    strategy: str | None = "v42",
    tick_id: str = "2026-09-17T09:00:00Z",
) -> PortfolioReservation:
    return build_reservation(
        reservation_id=reservation_id,
        instrument_id=instrument_id,
        quantity=quantity,
        side=side,
        entry=entry,
        sector=sector,
        strategy_version_id=strategy,
        reserved_risk=risk,
        tick_id=tick_id,
        created_at=tick_id,
    )


def test_build_reservation_derives_cash_and_exposures() -> None:
    reservation = _reservation()
    # 100 × 50 = 5.000 de notional comprometido.
    assert reservation.reserved_cash == pytest.approx(5000.0)
    assert reservation.asset_exposure == pytest.approx(5000.0)
    assert reservation.sector_exposure == pytest.approx(5000.0)
    assert reservation.remaining_qty == pytest.approx(100.0)
    assert reservation.status == RESERVATION_OPEN
    assert reservation.is_live is True
    assert reservation.is_quantified is True


def test_build_reservation_without_sector_leaves_exposure_unknown() -> None:
    """Sin sector la exposición NO es 0: es desconocida (y el libro lo declara)."""
    reservation = _reservation(sector=None)
    assert reservation.sector_exposure is None
    assert reservation.is_quantified is False


def test_build_reservation_sell_reserves_no_cash() -> None:
    """Vender no compromete capital: libera o cierra (mismo criterio que ``open_order``)."""
    reservation = _reservation(side="sell", risk=0.0)
    assert reservation.reserved_cash == 0.0
    assert reservation.asset_exposure == 0.0


def test_reservation_requires_identity() -> None:
    with pytest.raises(ValueError):
        _reservation(reservation_id="  ")


def test_coerce_reservation_status() -> None:
    assert coerce_reservation_status("open") == RESERVATION_OPEN
    assert coerce_reservation_status("released_by_fill") == RESERVATION_RELEASED_BY_FILL
    assert coerce_reservation_status("inventado") is None
    assert coerce_reservation_status(None) is None


# ── Gate 1: el libro no se puede doblar ───────────────────────────────────────────


def test_ledger_refuses_a_second_reservation_with_the_same_identity() -> None:
    """Dos aprobaciones no pueden reservar el MISMO capital: el alta es por identidad."""
    ledger = ReservationLedger(tick_id="t1")
    first = _reservation("R1", quantity=100.0, risk=500.0)
    duplicate = _reservation("R1", quantity=100.0, risk=500.0)

    assert ledger.reserve(first) is not None
    assert ledger.reserve(duplicate) is None
    assert ledger.reserved_cash == pytest.approx(5000.0)
    assert len(ledger.live()) == 1


def test_ledger_refuses_a_reservation_without_live_quantity() -> None:
    ledger = ReservationLedger()
    assert ledger.reserve(_reservation("R1", quantity=0.0)) is None
    assert ledger.live() == ()


# ── Gate 2: el libro cuadra ───────────────────────────────────────────────────────


def test_reserved_cash_and_risk_are_the_sum_of_live_reservations() -> None:
    """``reserved_cash == Σ reservas vivas`` y ``reserved_risk == Σ reservas vivas``."""
    ledger = ReservationLedger()
    ledger.reserve(_reservation("R1", quantity=100.0, risk=500.0))
    ledger.reserve(_reservation("R2", instrument_id="BBB", quantity=40.0, risk=200.0))

    live = ledger.live()
    assert ledger.reserved_cash == pytest.approx(sum(r.reserved_cash or 0.0 for r in live))
    assert ledger.reserved_risk == pytest.approx(sum(r.reserved_risk or 0.0 for r in live))
    assert ledger.reserved_cash == pytest.approx(5000.0 + 2000.0)
    assert ledger.reserved_risk == pytest.approx(700.0)


def test_released_reservation_contributes_zero_to_the_book() -> None:
    ledger = ReservationLedger()
    ledger.reserve(_reservation("R1"))
    ledger.release_by_cancel("R1")
    assert ledger.reserved_cash == 0.0
    assert ledger.reserved_risk == 0.0
    assert ledger.live() == ()
    # El libro no pierde la traza: la reserva sigue en ``all()`` con su motivo.
    stored = ledger.get("R1")
    assert stored is not None
    assert stored.status == RESERVATION_RELEASED_BY_CANCEL
    assert stored.released_qty == pytest.approx(100.0)
    assert stored.remaining_qty == 0.0


def test_released_reservation_keeps_the_original_amount_in_the_event_history() -> None:
    """Lo reservado originalmente vive en el evento de alta, no en el estado del libro."""
    ledger = ReservationLedger()
    ledger.reserve(_reservation("R1", quantity=100.0, risk=500.0))
    ledger.release_by_cancel("R1")

    reserve_event = ledger.events()[0]
    assert reserve_event.kind == "reserve"
    assert reserve_event.reservation is not None
    assert reserve_event.reservation.reserved_cash == pytest.approx(5000.0)
    assert reserve_event.reservation.reserved_risk == pytest.approx(500.0)


# ── Liberación: fill parcial, cancelación, reinicio, rollback ──────────────────────


def test_release_by_fill_partial_scales_and_keeps_the_tail_reserved() -> None:
    """Caso AUTO-1A: llenado 40 de 100 ⇒ 60 siguen siendo capital comprometido."""
    ledger = ReservationLedger()
    ledger.reserve(_reservation("R1", quantity=100.0, risk=500.0))

    updated = ledger.release_by_fill("R1", filled_qty=40.0)
    assert updated is not None
    assert updated.status == RESERVATION_OPEN
    assert updated.is_live is True
    assert updated.released_qty == pytest.approx(40.0)
    assert updated.remaining_qty == pytest.approx(60.0)
    assert updated.quantity == pytest.approx(updated.released_qty + updated.remaining_qty)
    # Dimensiones escaladas a lo vivo (60%): lo llenado ya no es reserva.
    assert updated.reserved_cash == pytest.approx(3000.0)
    assert updated.reserved_risk == pytest.approx(300.0)
    assert ledger.reserved_cash == pytest.approx(3000.0)
    assert ledger.reserved_risk == pytest.approx(300.0)


def test_release_by_fill_full_closes_the_reservation_and_frees_the_budget() -> None:
    ledger = ReservationLedger()
    ledger.reserve(_reservation("R1", quantity=100.0, risk=500.0))
    updated = ledger.release_by_fill("R1", filled_qty=100.0)
    assert updated is not None
    assert updated.status == RESERVATION_RELEASED_BY_FILL
    assert updated.is_live is False
    assert updated.remaining_qty == 0.0
    assert updated.reserved_cash == 0.0
    assert updated.reserved_risk == 0.0
    assert ledger.reserved_cash == 0.0


def test_release_is_idempotent() -> None:
    """Liberar dos veces nunca libera dos veces (la segunda es un no-op)."""
    ledger = ReservationLedger()
    ledger.reserve(_reservation("R1"))
    first = ledger.release_by_cancel("R1")
    second = ledger.release_by_cancel("R1")
    assert first is not None
    assert second is None
    assert len(ledger.events()) == 2
    assert ledger.reserved_cash == 0.0


def test_release_unknown_reservation_is_a_noop() -> None:
    ledger = ReservationLedger()
    assert ledger.release_by_fill("NO-EXISTE", filled_qty=10.0) is None
    assert ledger.reserved_cash == 0.0


def test_release_by_restart_is_recorded_with_its_own_status() -> None:
    ledger = ReservationLedger()
    ledger.reserve(_reservation("R1"))
    updated = ledger.release_by_restart("R1", reason="no reconciliable")
    assert updated is not None
    assert updated.status == RESERVATION_RELEASED_BY_RESTART
    assert updated.release_reason == "no reconciliable"


def test_rollback_releases_only_the_requested_tick() -> None:
    """Un tick abortado devuelve su presupuesto; el de otro tick no se toca."""
    ledger = ReservationLedger()
    ledger.reserve(_reservation("R1", tick_id="t1"))
    ledger.reserve(_reservation("R2", instrument_id="BBB", tick_id="t2"))

    released = ledger.rollback(tick_id="t1")
    assert [r.reservation_id for r in released] == ["R1"]
    assert ledger.reserved_cash == pytest.approx(5000.0)
    rolled = ledger.get("R1")
    untouched = ledger.get("R2")
    assert rolled is not None and rolled.status == RESERVATION_RELEASED_BY_ROLLBACK
    assert untouched is not None and untouched.status == RESERVATION_OPEN


# ── Gate 3: reproducibilidad ──────────────────────────────────────────────────────


def test_replay_reproduces_the_ledger_exactly() -> None:
    """Mismos eventos ⇒ mismo libro, mismo capital y mismo riesgo reservados."""
    ledger = ReservationLedger(account_id="acc-1", tick_id="t1")
    ledger.reserve(_reservation("R1", quantity=100.0, risk=500.0))
    ledger.reserve(_reservation("R2", instrument_id="BBB", quantity=40.0, risk=200.0))
    ledger.release_by_fill("R2", filled_qty=15.0)

    rebuilt = replay(ledger.events(), account_id="acc-1", tick_id="t1")
    assert rebuilt.reserved_cash == pytest.approx(ledger.reserved_cash)
    assert rebuilt.reserved_risk == pytest.approx(ledger.reserved_risk)
    assert rebuilt.to_dict() == ledger.to_dict()
    assert len(rebuilt.events()) == len(ledger.events())


def test_replay_is_order_deterministic_and_survives_a_full_release() -> None:
    ledger = ReservationLedger()
    ledger.reserve(_reservation("R1"))
    ledger.release_by_fill("R1", filled_qty=30.0)
    ledger.release_by_cancel("R1")

    rebuilt = replay(ledger.events())
    assert rebuilt.to_dict() == ledger.to_dict()
    assert rebuilt.reserved_cash == 0.0


# ── Medición y proyección ─────────────────────────────────────────────────────────


def test_live_measurement_degrades_when_a_dimension_is_missing() -> None:
    ledger = ReservationLedger()
    assert ledger.live_measurement() == MEASUREMENT_COMPLETE  # nada que medir = exacto.
    ledger.reserve(_reservation("R1"))
    assert ledger.live_measurement() == MEASUREMENT_COMPLETE
    ledger.reserve(_reservation("R2", instrument_id="BBB", risk=None))
    assert ledger.live_measurement() == MEASUREMENT_PARTIAL


def test_risk_by_sector_and_strategy_use_an_unknown_bucket() -> None:
    ledger = ReservationLedger()
    ledger.reserve(_reservation("R1", sector="tech", risk=500.0, strategy="v42"))
    ledger.reserve(
        _reservation("R2", instrument_id="BBB", sector=None, risk=200.0, strategy=None)
    )
    assert ledger.risk_by_sector() == {"tech": 500.0, "<unknown>": 200.0}
    assert ledger.risk_by_strategy() == {"v42": 500.0, "<unknown>": 200.0}
    assert ledger.cash_by_sector() == {"tech": 5000.0, "<unknown>": 5000.0}


def test_committed_positions_projects_live_buys_only() -> None:
    ledger = ReservationLedger()
    ledger.reserve(_reservation("R1", quantity=100.0, risk=500.0))
    ledger.reserve(_reservation("R2", instrument_id="BBB", side="sell", risk=0.0))
    ledger.reserve(_reservation("R3", instrument_id="CCC"))
    ledger.release_by_cancel("R3")

    projected = ledger.committed_positions()
    assert len(projected) == 1
    assert projected[0].instrument_id == "AAA"
    assert projected[0].quantity == pytest.approx(100.0)
    assert projected[0].market_value == pytest.approx(5000.0)
    assert projected[0].risk_amount == pytest.approx(500.0)
    assert projected[0].sector == "tech"


# ── Coste real de negociación ─────────────────────────────────────────────────────


def test_stop_distance_requires_the_stop_on_the_correct_side() -> None:
    assert stop_distance(entry=100.0, stop=97.0) == pytest.approx(3.0)
    assert stop_distance(entry=100.0, stop=103.0) is None
    assert stop_distance(entry=100.0, stop=103.0, direction="short") == pytest.approx(3.0)


def test_estimate_trading_cost_is_round_trip_and_includes_the_stop() -> None:
    """``risk_real = stop loss + comisión + spread + slippage`` de ida y vuelta."""
    cost = estimate_trading_cost(quantity=200.0, entry=100.0, stop=97.0)
    assert cost.notional == pytest.approx(20000.0)
    assert cost.stop_loss == pytest.approx(600.0)
    # 10 bps × 2 lados = 40; spread 2 bps = 4; slippage 5 bps × 2 lados = 20.
    assert cost.commission == pytest.approx(40.0)
    assert cost.spread == pytest.approx(4.0)
    assert cost.slippage == pytest.approx(20.0)
    assert cost.total == pytest.approx(64.0)
    assert cost.expected_loss == pytest.approx(664.0)
    assert cost.gap == pytest.approx(0.0)
    assert cost.measurement == MEASUREMENT_COMPLETE
    assert cost.is_complete is True


def test_estimate_trading_cost_without_stop_is_partial_and_not_zero() -> None:
    """Sin stop no hay pérdida esperada: el coste queda INCOMPLETO, nunca gratis."""
    cost = estimate_trading_cost(quantity=200.0, entry=100.0, stop=110.0)
    assert cost.stop_loss is None
    assert cost.expected_loss is None
    assert cost.gap_adjusted_loss is None
    assert cost.worst_case_loss is None
    assert cost.total == pytest.approx(64.0)  # las fricciones sí se conocen.
    assert cost.measurement == MEASUREMENT_PARTIAL
    assert cost.is_complete is False


def test_estimate_trading_cost_without_entry_is_unknown() -> None:
    cost = estimate_trading_cost(quantity=200.0, entry=0.0, stop=97.0)
    assert cost.notional is None
    assert cost.total is None
    assert cost.measurement == MEASUREMENT_UNKNOWN


def test_gap_bounds_the_loss_when_the_stop_does_not_hold() -> None:
    """El hueco adverso manda sobre el stop y se declara en su propia cota."""
    model = TradingCostModel(gap_bps=500.0)
    cost = estimate_trading_cost(quantity=200.0, entry=100.0, stop=97.0, model=model)
    assert cost.gap == pytest.approx(1000.0)
    # max(stop 600, hueco 1000) + fricciones 64.
    assert cost.gap_adjusted_loss == pytest.approx(1064.0)
    # Cota aditiva declarada: stop + hueco + fricciones.
    assert cost.worst_case_loss == pytest.approx(1664.0)


def test_commission_uses_the_real_account_fee_schedule() -> None:
    """Con ``settings`` la comisión sale de la tarifa real (comisión + IVA + stamp duty)."""
    model = TradingCostModel(settings=default_account_settings("standard_es"))
    cost = estimate_trading_cost(quantity=200.0, entry=100.0, stop=97.0, model=model)
    # Alta (buy): 20 de comisión + 4,2 de IVA + 40 de stamp duty = 64,2.
    # Salida (sell a 97): 19,4 + 4,074 = 23,474. Total ida y vuelta ≈ 87,674.
    assert cost.commission == pytest.approx(87.674, abs=1e-3)
    assert cost.expected_loss == pytest.approx(600.0 + 87.674 + 4.0 + 20.0, abs=1e-3)


def test_coerce_trading_cost_round_trips_its_dict() -> None:
    original = estimate_trading_cost(quantity=200.0, entry=100.0, stop=97.0)
    rebuilt = coerce_trading_cost(original.to_dict())
    assert rebuilt == original
    assert coerce_trading_cost(None) is None
    assert coerce_trading_cost("no soy un coste") is None


# ── Estado de riesgo de cartera ───────────────────────────────────────────────────


def test_sector_risk_from_positions_counts_unmeasured_instead_of_zero() -> None:
    positions = (
        PortfolioPosition("AAA", 100.0, sector="tech", risk_amount=600.0),
        PortfolioPosition("BBB", 50.0, sector="tech", risk_amount=None),
        PortfolioPosition("CCC", 0.0, sector="energy", risk_amount=999.0),
    )
    by_sector, unmeasured = sector_risk_from_positions(positions)
    assert by_sector == {"tech": 600.0}
    assert unmeasured == 1


def test_portfolio_risk_state_adds_positions_and_reservations() -> None:
    ledger = ReservationLedger()
    ledger.reserve(_reservation("R1", risk=500.0, strategy="v42"))

    state = build_portfolio_risk_state(
        ledger=ledger,
        position_risk_total=600.0,
        position_risk_by_sector={"energy": 600.0},
        pending_risk=0.0,
    )
    assert state.gross_risk == pytest.approx(1100.0)
    assert state.net_risk == pytest.approx(1100.0)
    assert state.reserved_risk == pytest.approx(500.0)
    assert state.pending_risk == pytest.approx(0.0)
    assert state.sector_risk == {"energy": 600.0, "tech": 500.0}
    assert state.strategy_risk == {"v42": 500.0}
    assert state.correlation_adjusted_risk == pytest.approx(500.0)
    assert state.measurement == MEASUREMENT_COMPLETE


def test_correlation_adjusted_risk_never_discounts_unknown_or_negative() -> None:
    """Sin correlación declarada no se descuenta (Σ stop risk); negativa tampoco."""
    unknown = ReservationLedger()
    unknown.reserve(_reservation("R1", risk=500.0))
    assert build_portfolio_risk_state(
        ledger=unknown
    ).correlation_adjusted_risk == pytest.approx(500.0)

    negative = ReservationLedger()
    negative.reserve(_reservation("R1", risk=500.0))
    negative.reserve(_reservation("R2", instrument_id="BBB", risk=500.0))
    correlated = build_reservation(
        reservation_id="R3",
        instrument_id="CCC",
        quantity=100.0,
        entry=50.0,
        sector="tech",
        reserved_risk=500.0,
        correlation=-0.8,
    )
    negative.reserve(correlated)
    # La correlación negativa no reduce la cota: no se asume diversificación no medida.
    assert build_portfolio_risk_state(
        ledger=negative
    ).correlation_adjusted_risk == pytest.approx(1500.0)


def test_correlation_adjusted_risk_rises_with_declared_positive_correlation() -> None:
    ledger = ReservationLedger()
    ledger.reserve(_reservation("R1", risk=500.0))
    correlated = build_reservation(
        reservation_id="R2",
        instrument_id="BBB",
        quantity=40.0,
        entry=50.0,
        sector="tech",
        reserved_risk=200.0,
        correlation=0.5,
    )
    ledger.reserve(correlated)
    state = build_portfolio_risk_state(ledger=ledger)
    assert state.correlation_adjusted_risk == pytest.approx(500.0 + 200.0 * 1.5)


def test_correlation_adjusted_risk_is_unknown_when_a_reservation_lacks_risk() -> None:
    ledger = ReservationLedger()
    ledger.reserve(_reservation("R1", risk=None))
    state = build_portfolio_risk_state(ledger=ledger, unmeasured_positions=1)
    assert state.correlation_adjusted_risk is None
    assert state.measurement == MEASUREMENT_PARTIAL


def test_portfolio_risk_state_without_ledger_is_measured_at_zero_reserved() -> None:
    state = build_portfolio_risk_state(position_risk_total=600.0, pending_risk=10.0)
    assert state.reserved_risk == 0.0
    assert state.gross_risk == pytest.approx(600.0)
    assert state.correlation_adjusted_risk == 0.0
    assert state.measurement == MEASUREMENT_COMPLETE


def test_portfolio_risk_state_degrades_when_positions_are_unmeasured() -> None:
    state = build_portfolio_risk_state(position_risk_total=600.0, unmeasured_positions=2)
    assert state.measurement == MEASUREMENT_PARTIAL
    assert state.is_complete is False


# ── Coste real en el sizing (allocator) ───────────────────────────────────────────


def test_allocator_shrinks_the_size_so_real_risk_fits_the_budget() -> None:
    """``risk_real = stop + fricciones``: el presupuesto cubre los dos sumandos."""
    config = RiskAllocatorConfig(max_risk_per_trade_pct=1.0, max_position_pct=100.0)
    kwargs = {
        "equity": 100_000.0,
        "entry": 100.0,
        "stop": 97.0,
        "risk_budget": 1000.0,
        "config": config,
    }
    without = compute_allocation(**kwargs)
    with_cost = compute_allocation(**kwargs, cost_model=TradingCostModel())

    # Sin modelo, todo el presupuesto se va en pérdida de stop: contrato histórico intacto.
    assert without.quantity == pytest.approx(1000.0 / 3.0, abs=1e-3)
    assert without.risk_real is None
    assert without.trading_cost is None

    assert with_cost.quantity < without.quantity
    assert CAP_TRADING_COST in with_cost.capped_reasons
    # El presupuesto COMPROMETIDO no cambia; lo que cambia es que ahora cubre el coste.
    assert with_cost.risk_amount == pytest.approx(1000.0)
    assert with_cost.risk_real == pytest.approx(1000.0, rel=1e-3)
    assert with_cost.trading_cost is not None
    assert with_cost.trading_cost.total == pytest.approx(96.4, rel=0.05)


def test_allocator_declares_an_unmeasurable_cost_instead_of_assuming_zero() -> None:
    """Coste ilegible: se degrada al sizing por stop, pero se DECLARA (nunca coste 0)."""
    result = compute_allocation(
        equity=100_000.0,
        entry=100.0,
        stop=97.0,
        risk_budget=1000.0,
        config=RiskAllocatorConfig(max_risk_per_trade_pct=1.0, max_position_pct=100.0),
        cost_model=TradingCostModel(commission_bps=-1.0),
    )
    assert CAP_COST_UNMEASURED in result.capped_reasons
    assert result.risk_real is None
    assert result.trading_cost is not None
    assert result.trading_cost.is_complete is False
    # La operación sigue siendo aprobable con el sizing histórico: lo que NO se permite es
    # fingir que el coste es 0.
    assert result.approved is True
