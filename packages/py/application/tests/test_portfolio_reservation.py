"""AUTO-1 — el tick reserva, y la reserva es la única fuente del compromiso.

Gate de la fase, medido sobre ``plan_v2_tick``:

1. **No existe aprobación sin reserva** — cada aprobación del tick tiene su reserva viva
   con identidad, y el número de reservas coincide con el de aprobaciones.
2. **Dos aprobaciones concurrentes no pueden reservar el mismo capital** — el notional
   reservado por el tick es el que se comprometió de verdad, no la suma de deseos.
3. **El libro cuadra y se reproduce** — ``reserved_cash`` == Σ reservas vivas, y
   ``replay`` de los eventos del tick devuelve el mismo libro.
4. **Toda reserva se puede liberar** — el rollback del tick devuelve el presupuesto a 0.
"""

import pytest

from bolsa_analytics.cognitive.measurement import MEASUREMENT_COMPLETE
from bolsa_analytics.cognitive.portfolio_reservation import ReservationLedger, replay
from bolsa_application.auto_v2_entry import (
    V2Signal,
    V2Tunables,
    build_worker_snapshot,
    plan_v2_tick,
    tunables_from_env,
)

# ── Helpers ───────────────────────────────────────────────────────────────────────


def _snapshot(*, risk_budget_pct: float | None = 6.0, cash: float = 80_000.0):
    return build_worker_snapshot(
        account_id="acc-1",
        equity=100_000.0,
        cash=cash,
        open_positions={},
        entry_prices={},
        regime="BULL_TREND",
        risk_budget_pct=risk_budget_pct,
    )


def _signal(symbol: str, *, price: float = 100.0, atr: float = 2.0, sector: str = "tech"):
    return V2Signal(
        symbol,
        "BUY",
        price=price,
        atr=atr,
        edge=0.9,
        sector=sector,
        liquidity_notional=1_000_000.0,
        strategy_version="v42",
        signal_id=f"sig-{symbol}",
        bar_timestamp="2026-09-17T08:00:00Z",
        valid_until="2026-09-18T00:00:00Z",
    )


def _tick(*, snapshot, signals, tunables=None, as_of="2026-09-17T09:00:00Z"):
    return plan_v2_tick(
        snapshot=snapshot,
        signals=signals,
        regime="BULL_TREND",
        as_of=as_of,
        tunables=tunables,
    )


def _ledger_from_plan(plan) -> ReservationLedger:
    ledger = ReservationLedger(tick_id=plan.as_of)
    for reservation in plan.reservations:
        ledger.reserve(reservation)
    return ledger


# ── Gate 1: no existe aprobación sin reserva ──────────────────────────────────────


def test_every_approved_entry_has_a_live_reservation() -> None:
    plan = _tick(snapshot=_snapshot(), signals=[_signal("AAA"), _signal("BBB", price=200.0)])
    approved = [d for d in plan.decisions if d.approved]

    assert len(approved) == 2
    assert len(plan.reservations) == len(approved)
    assert plan.approved_symbols == ("AAA", "BBB")

    by_symbol = {r.instrument_id: r for r in plan.reservations}
    for decision in approved:
        reservation = by_symbol[decision.instrument_id]
        assert reservation.is_live is True
        assert reservation.reservation_id == f"RES-{decision.decision_id}"
        assert reservation.reserved_cash == pytest.approx(
            float(decision.allocation["positionValue"])
        )
        assert reservation.reserved_risk == pytest.approx(
            float(decision.allocation["riskAmount"])
        )
        assert reservation.sector is not None
        assert reservation.strategy_version_id == "v42"


def test_reservation_carries_the_real_cost_of_the_trade() -> None:
    """El compromiso incluye la pérdida esperada real (stop + fricciones), no solo el stop."""
    plan = _tick(snapshot=_snapshot(), signals=[_signal("AAA")])
    reservation = plan.reservations[0]
    assert reservation.cost is not None
    assert reservation.cost.expected_loss is not None
    assert reservation.cost.total is not None and reservation.cost.total > 0
    # El presupuesto reservado cubre el riesgo real (el sizing ya lo ajustó).
    assert reservation.cost.expected_loss <= (reservation.reserved_risk or 0.0) + 1e-6


def test_vetoed_entries_leave_no_reservation() -> None:
    plan = _tick(
        snapshot=_snapshot(risk_budget_pct=0.5),
        signals=[_signal(f"S{i}", sector=f"sector-{i}") for i in range(4)],
        tunables=V2Tunables(top_n=10, risk_budget_pct=0.5),
    )
    rejected = [d for d in plan.decisions if not d.approved]
    assert rejected, "el presupuesto minúsculo debe vetar alguna entrada"
    assert len(plan.reservations) == len([d for d in plan.decisions if d.approved])


# ── Gate 2: dos aprobaciones no reservan el mismo capital ─────────────────────────


def test_two_entries_cannot_reserve_the_same_cash() -> None:
    """``cash = 25k`` ⇒ el tick solo puede comprometer 25k, no 20k por candidata."""
    plan = _tick(
        snapshot=_snapshot(cash=25_000.0, risk_budget_pct=100.0),
        signals=[_signal(f"S{i}", sector=f"sector-{i}") for i in range(4)],
        tunables=V2Tunables(top_n=10, risk_budget_pct=100.0),
    )
    assert plan.approved_symbols == ("S0", "S1")
    committed = sum(r.reserved_cash or 0.0 for r in plan.reservations)
    assert committed == pytest.approx(25_000.0)
    # Y la tercera candidata queda vetada: su capital ya no está disponible.
    vetoed = [d for d in plan.decisions if not d.approved]
    assert len(vetoed) == 2
    assert all(d.reason_codes == ("risk_budget_exceeded",) for d in vetoed)


def test_two_entries_cannot_reserve_the_same_risk() -> None:
    """``risk_budget = 6%`` ⇒ el riesgo reservado por el tick no puede pasar de 6%."""
    plan = _tick(
        snapshot=_snapshot(risk_budget_pct=6.0, cash=1_000_000.0),
        signals=[_signal(f"S{i}", sector=f"sector-{i}") for i in range(7)],
        tunables=V2Tunables(top_n=10, risk_budget_pct=6.0),
    )
    assert len(plan.approved_symbols) == 6
    reserved = sum(r.reserved_risk or 0.0 for r in plan.reservations)
    assert reserved == pytest.approx(6000.0)
    assert reserved == pytest.approx(plan.risk_state.reserved_risk)  # type: ignore[union-attr]


# ── Gate 3: el libro cuadra y se reproduce ────────────────────────────────────────


def test_tick_reserved_cash_equals_the_sum_of_live_reservations() -> None:
    plan = _tick(snapshot=_snapshot(), signals=[_signal("AAA"), _signal("BBB", price=200.0)])
    ledger = _ledger_from_plan(plan)

    assert ledger.reserved_cash == pytest.approx(
        sum(r.reserved_cash or 0.0 for r in ledger.live())
    )
    assert ledger.reserved_cash == pytest.approx(
        sum(r.reserved_cash or 0.0 for r in plan.reservations)
    )
    assert ledger.live_measurement() == MEASUREMENT_COMPLETE


def test_replay_of_the_tick_reproduces_its_reservations() -> None:
    plan = _tick(
        snapshot=_snapshot(cash=25_000.0, risk_budget_pct=100.0),
        signals=[_signal(f"S{i}", sector=f"sector-{i}") for i in range(4)],
        tunables=V2Tunables(top_n=10, risk_budget_pct=100.0),
    )
    ledger = _ledger_from_plan(plan)
    rebuilt = replay(ledger.events(), tick_id=plan.as_of)

    assert rebuilt.to_dict() == ledger.to_dict()
    assert rebuilt.reserved_cash == pytest.approx(ledger.reserved_cash)
    assert rebuilt.reserved_risk == pytest.approx(ledger.reserved_risk)


def test_tick_publishes_a_risk_state_consistent_with_its_reservations() -> None:
    plan = _tick(snapshot=_snapshot(), signals=[_signal("AAA"), _signal("BBB", price=200.0)])
    state = plan.risk_state
    assert state is not None
    assert state.measurement == MEASUREMENT_COMPLETE
    base = sum(r.reserved_risk or 0.0 for r in plan.reservations)
    assert state.reserved_risk == pytest.approx(base)
    assert state.gross_risk == pytest.approx((_snapshot().risk_used or 0.0) + base)
    assert state.net_risk == state.gross_risk
    assert state.sector_risk  # el desglose sectorial de las reservas está publicado.


# ── Gate 4: toda reserva se puede liberar ─────────────────────────────────────────


def test_rollback_of_the_tick_returns_the_budget() -> None:
    plan = _tick(snapshot=_snapshot(), signals=[_signal("AAA"), _signal("BBB", price=200.0)])
    ledger = _ledger_from_plan(plan)
    assert ledger.reserved_cash > 0

    released = ledger.rollback(tick_id=plan.as_of)
    assert len(released) == len(plan.reservations)
    assert ledger.reserved_cash == 0.0
    assert ledger.reserved_risk == 0.0
    assert ledger.live() == ()


def test_release_by_fill_of_a_tick_reservation_keeps_the_tail_reserved() -> None:
    """Un fill parcial del tick libera lo llenado y deja la cola como capital reservado."""
    plan = _tick(snapshot=_snapshot(), signals=[_signal("AAA")])
    ledger = _ledger_from_plan(plan)
    reservation = plan.reservations[0]

    updated = ledger.release_by_fill(
        reservation.reservation_id, filled_qty=reservation.remaining_qty / 2.0
    )
    assert updated is not None
    assert updated.is_live is True
    assert updated.remaining_qty == pytest.approx(reservation.remaining_qty / 2.0)
    assert ledger.reserved_cash == pytest.approx((reservation.reserved_cash or 0.0) / 2.0)


# ── Coste real: activo por defecto y desactivable ─────────────────────────────────


def test_cost_model_is_on_by_default_and_can_be_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("AUTO_ENGINE_SIM_V2_COST_MODEL", raising=False)
    cfg = tunables_from_env()
    assert cfg.cost_model is not None
    assert cfg.decision_config().cost_model is not None

    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_COST_MODEL", "0")
    assert tunables_from_env().cost_model is None
    assert tunables_from_env().decision_config().cost_model is None


def test_cost_model_bps_are_env_calibrated(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AUTO_ENGINE_SIM_V2_COST_MODEL", raising=False)
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_SLIPPAGE_BPS", "12")
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_GAP_BPS", "50")
    model = tunables_from_env().cost_model
    assert model is not None
    assert model.slippage_bps == pytest.approx(12.0)
    assert model.gap_bps == pytest.approx(50.0)
