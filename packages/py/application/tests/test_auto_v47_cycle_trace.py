"""V2.47 — ``cycle_id`` híbrido: acuñado determinista y propagación por toda la cadena.

El ``cycle_id`` es la identidad financiera del **ciclo completo** (señal → decisión →
reserva → orden → fill → posición → salida → PnL). Estos tests certifican las dos mitades
del contrato híbrido:

* **Acuñado determinista** por ``(cuenta, signal_id)``: dos workers que evalúan la misma
  señal convergen al MISMO ciclo (si fuera aleatorio, un reintento tras crash partiría el
  ciclo en dos y la trazabilidad mentiría).
* **Propagación sin migración** por donde ya hay JSONB/identidad (plan del tick, journal,
  reserva, ``position_state``) y por las columnas de la migración ``044`` (reserva, exit
  order, fill context) — con ``None`` = "desconocido", nunca un ciclo inventado.
* **Lectura por ciclo** (``AUTO-9``, paso 2 del plan ``v2.50``): ``list_by_cycle_ids`` recupera el
  material completo de un ciclo desde la única costura que ya existe (``cycle_id``), declarando que
  ``NULL`` **no** es un ciclo — el hueco lo contará quien lo consuma, no se rellena aquí.

Módulo puro + stores in-memory: sin I/O, sin reloj real, sin PostgreSQL.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from bolsa_analytics.cognitive.exit_order import build_exit_order
from bolsa_analytics.cognitive.portfolio_reservation import (
    PortfolioReservation,
    build_reservation,
)
from bolsa_analytics.cognitive.position_state import (
    CYCLE_ID_KEY,
    PositionState,
    build_position_state_from_fill,
    position_state_from_dict,
)
from bolsa_application.auto_v2_entry import (
    V2Signal,
    auto_cycle_id,
    build_worker_snapshot,
    plan_v2_tick,
    signal_identity_for_bar,
)
from bolsa_application.exit_order_store import InMemoryExitOrderStore
from bolsa_application.reservation_store import (
    InMemoryReservationStore,
    _reservation_values,
)

_MOMENT = datetime(2026, 9, 15, 9, 0, tzinfo=UTC)


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


def _signal(
    symbol: str,
    *,
    edge: float | None = 0.9,
    price: float = 100.0,
    atr: float | None = 2.0,
    action: str = "BUY",
    signal_id: str | None = None,
) -> V2Signal:
    identity = signal_identity_for_bar(
        instrument_id=symbol,
        action=action,
        strategy_version="v42",
        timeframe="1d",
        moment=_MOMENT,
    )
    assert identity is not None
    return V2Signal(
        symbol,
        action,
        price=price,
        atr=atr,
        edge=edge,
        sector="tech",
        liquidity_notional=1_000_000.0,
        strategy_version="v42",
        signal_id=signal_id if signal_id is not None else identity.signal_id,
        bar_timestamp=identity.bar_timestamp,
        valid_until=identity.valid_until,
    )


# ── Acuñado determinista ──────────────────────────────────────────────────────


def test_cycle_is_deterministic_by_account_and_signal() -> None:
    """Misma (cuenta, señal) ⇒ MISMO ciclo; cambia cuenta o señal ⇒ cambia el ciclo."""
    first = auto_cycle_id(account_id="acc-1", signal=_signal("AAA"))
    again = auto_cycle_id(account_id="acc-1", signal=_signal("AAA"))
    other_account = auto_cycle_id(account_id="acc-2", signal=_signal("AAA"))
    other_signal = auto_cycle_id(account_id="acc-1", signal=_signal("BBB"))

    assert first == again
    assert first.startswith("cyc-")
    assert first != other_account
    assert first != other_signal
    assert not first.startswith("dec-") and not first.startswith("RES-")


def test_cycle_without_signal_id_falls_back_to_a_fresh_identity() -> None:
    """Sin identidad de barra no hay clave estable: dos acuñados NO pueden coincidir."""
    blank = _signal("AAA", signal_id="")
    first = auto_cycle_id(account_id="acc-1", signal=blank)
    second = auto_cycle_id(account_id="acc-1", signal=blank)

    assert first.startswith("cyc-")
    assert first != second


# ── Propagación por el plan del tick (JSONB, sin migración) ────────────────────


def test_the_tick_plan_publishes_one_deterministic_cycle_per_candidate() -> None:
    signals = [_signal("AAA"), _signal("BBB", price=200.0, atr=4.0, edge=0.8)]
    plan = plan_v2_tick(
        snapshot=_snapshot(),
        signals=signals,
        regime="BULL_TREND",
        as_of="2026-09-15T09:00:00Z",
    )

    assert set(plan.cycle_for(s) for s in ("AAA", "BBB")) == {
        auto_cycle_id(account_id="acc-1", signal=signals[0]),
        auto_cycle_id(account_id="acc-1", signal=signals[1]),
    }
    assert plan.cycle_for("ZZZ") is None


def test_an_approved_decision_carries_its_cycle_in_the_journal_and_reservation() -> None:
    signal = _signal("AAA")
    plan = plan_v2_tick(
        snapshot=_snapshot(),
        signals=[signal],
        regime="BULL_TREND",
        as_of="2026-09-15T09:00:00Z",
    )
    cycle_id = auto_cycle_id(account_id="acc-1", signal=signal)

    assert plan.cycle_for("AAA") == cycle_id
    payloads = [entry.payload or {} for entry in plan.journal_entries]
    assert any(payload.get("cycleId") == cycle_id for payload in payloads)

    live = [row for row in plan.reservations if row.is_live]
    assert len(live) == 1
    assert live[0].cycle_id == cycle_id


# ── Propagación dúradera por la reserva y el intent de salida ─────────────────


def test_a_reservation_persists_its_cycle_through_the_store() -> None:
    reservation = build_reservation(
        reservation_id="RES-1",
        account_id="acc-1",
        tick_id="2026-09-15T09:00:00Z",
        instrument_id="AAA",
        side="buy",
        quantity=10.0,
        entry=100.0,
        stop=98.0,
        cycle_id="cyc-abc",
    )
    assert reservation is not None
    assert _reservation_values(reservation)["cycle_id"] == "cyc-abc"

    store = InMemoryReservationStore()
    import asyncio

    asyncio.run(store.save(reservation))
    assert asyncio.run(store.list_live("acc-1"))[0].cycle_id == "cyc-abc"


# ── AUTO-9 — lectura por ciclo (paso 2 del plan `v2.50`) ─────────────────────────


def test_a_cycle_returns_all_its_reservations_not_just_the_entry() -> None:
    """AUTO-9 — el lector por ciclo devuelve el material COMPLETO del ciclo.

    Un ciclo tiene una reserva de ENTRADA y, si hubo salida, una de SALIDA. El store no
    elige: devuelve las dos y deja la elección del denominador de R al llamante.
    """
    import asyncio

    entry = build_reservation(
        reservation_id="RES-entry",
        account_id="acc-1",
        tick_id="2026-09-15T09:00:00Z",
        instrument_id="AAA",
        side="buy",
        quantity=10.0,
        entry=100.0,
        stop=98.0,
        reserved_risk=200.0,
        cycle_id="cyc-abc",
        created_at="2026-09-15T09:00:00Z",
    )
    exit_row = build_reservation(
        reservation_id="RES-exit",
        account_id="acc-1",
        tick_id="2026-09-15T10:00:00Z",
        instrument_id="AAA",
        side="sell",
        quantity=10.0,
        entry=104.0,
        cycle_id="cyc-abc",
        created_at="2026-09-15T10:00:00Z",
    )
    store = InMemoryReservationStore([entry, exit_row])

    rows = asyncio.run(store.list_by_cycle_ids("acc-1", ["cyc-abc"]))

    assert [row.reservation_id for row in rows] == ["RES-entry", "RES-exit"]
    assert {row.side for row in rows} == {"buy", "sell"}
    assert rows[0].reserved_risk == pytest.approx(200.0)


def test_a_reservation_without_cycle_never_matches_a_cycle_query() -> None:
    """``NULL`` no es un ciclo: "anterior a 2.47" no puede colarse en un informe de R."""
    import asyncio

    historic = build_reservation(
        reservation_id="RES-historic",
        account_id="acc-1",
        tick_id="2026-09-15T09:00:00Z",
        instrument_id="AAA",
        side="buy",
        quantity=10.0,
        entry=100.0,
        stop=98.0,
    )
    assert historic.cycle_id is None
    store = InMemoryReservationStore([historic])

    assert asyncio.run(store.list_by_cycle_ids("acc-1", ["cyc-abc"])) == []
    # Un conjunto vacío o en blanco tampoco es un ciclo: se corta sin devolver la histórica.
    assert asyncio.run(store.list_by_cycle_ids("acc-1", ["", "   "])) == []
    assert asyncio.run(store.list_by_cycle_ids("acc-1", [])) == []


def test_a_cycle_query_filters_by_account_and_stays_deterministic() -> None:
    import asyncio

    def _row(reservation_id: str, account_id: str, moment: str) -> PortfolioReservation:
        return build_reservation(
            reservation_id=reservation_id,
            account_id=account_id,
            tick_id=moment,
            instrument_id="AAA",
            side="buy",
            quantity=10.0,
            entry=100.0,
            stop=98.0,
            cycle_id="cyc-abc",
            created_at=moment,
        )

    store = InMemoryReservationStore(
        [
            _row("RES-late", "acc-1", "2026-09-15T11:00:00Z"),
            _row("RES-early", "acc-1", "2026-09-15T09:00:00Z"),
            _row("RES-other-account", "acc-2", "2026-09-15T09:00:00Z"),
        ]
    )

    scoped = asyncio.run(store.list_by_cycle_ids("acc-1", ["cyc-abc"]))
    assert [row.reservation_id for row in scoped] == ["RES-early", "RES-late"]

    # ``account_id=None`` es "sin filtro de cuenta" (el fail-closed del llamante que no pudo
    # determinarla): prefiere ver todo antes que asumir que no hay nada.
    every_account = asyncio.run(store.list_by_cycle_ids(None, ["cyc-abc"]))
    assert [row.reservation_id for row in every_account] == [
        "RES-early",
        "RES-other-account",
        "RES-late",
    ]

    # Pedir el mismo ciclo dos veces no duplica filas.
    twice = asyncio.run(store.list_by_cycle_ids("acc-1", ["cyc-abc", "cyc-abc"]))
    assert [row.reservation_id for row in twice] == ["RES-early", "RES-late"]


def test_a_cycle_query_respects_the_limit_it_declares() -> None:
    """``limit <= 0`` no es "sin límite": es "no leo nada" (suelo declarado del store)."""
    import asyncio

    reservation = build_reservation(
        reservation_id="RES-1",
        account_id="acc-1",
        tick_id="2026-09-15T09:00:00Z",
        instrument_id="AAA",
        side="buy",
        quantity=10.0,
        entry=100.0,
        stop=98.0,
        cycle_id="cyc-abc",
        created_at="2026-09-15T09:00:00Z",
    )
    store = InMemoryReservationStore([reservation])

    assert asyncio.run(store.list_by_cycle_ids("acc-1", ["cyc-abc"], limit=0)) == []
    assert len(asyncio.run(store.list_by_cycle_ids("acc-1", ["cyc-abc"], limit=1))) == 1


def test_an_exit_order_persists_and_round_trips_its_cycle() -> None:
    order = build_exit_order(
        exit_order_id="exi-1",
        instrument_id="AAA",
        side="sell",
        requested_qty=10.0,
        account_id="acc-1",
        engine_id="auto",
        cycle_id="cyc-abc",
    )
    assert order is not None
    assert order.cycle_id == "cyc-abc"
    assert order.to_dict()["cycleId"] == "cyc-abc"

    store = InMemoryExitOrderStore()
    import asyncio

    asyncio.run(store.save(order))
    assert asyncio.run(store.get("exi-1")).cycle_id == "cyc-abc"


# ── Propagación por ``position_state`` (JSONB, sin migración) ─────────────────


def _trade_plan() -> dict[str, object]:
    return {
        "decisionId": "dec-1",
        "tradePlanId": "tp-1",
        "instrumentId": "AAA",
        "direction": "long",
        "status": "TRIGGERED",
        "entry": 100.0,
        "structuralStop": 98.0,
        "target1": 104.0,
        "target2": 108.0,
    }


def test_the_position_freezes_the_cycle_and_round_trips_it() -> None:
    position = build_position_state_from_fill(
        _trade_plan(),
        fill_price=100.0,
        fill_quantity=10.0,
        filled_at="2026-09-15T09:00:00Z",
        cycle_id="cyc-abc",
    )
    assert position is not None
    assert position.cycle_id == "cyc-abc"
    assert position.to_dict()[CYCLE_ID_KEY] == "cyc-abc"

    restored = position_state_from_dict(position.to_dict())
    assert restored is not None
    assert restored.cycle_id == "cyc-abc"


def test_a_position_without_a_cycle_does_not_invent_one() -> None:
    position = build_position_state_from_fill(
        _trade_plan(),
        fill_price=100.0,
        fill_quantity=10.0,
        filled_at="2026-09-15T09:00:00Z",
    )
    assert position is not None
    assert position.cycle_id is None
    # Ausente = "no persistido" (posiciones previas a 2.47), nunca "None" fabricado.
    assert CYCLE_ID_KEY not in position.to_dict()
    restored = position_state_from_dict(position.to_dict())
    assert restored is not None
    assert restored.cycle_id is None


def test_the_cycle_can_be_inherited_from_the_trade_plan_dict() -> None:
    plan = {**_trade_plan(), CYCLE_ID_KEY: "cyc-from-plan"}
    position = build_position_state_from_fill(
        plan,
        fill_price=100.0,
        fill_quantity=10.0,
        filled_at="2026-09-15T09:00:00Z",
    )
    assert position is not None
    assert position.cycle_id == "cyc-from-plan"


def test_an_explicit_cycle_wins_over_the_one_declared_in_the_plan() -> None:
    plan = {**_trade_plan(), CYCLE_ID_KEY: "cyc-from-plan"}
    position = build_position_state_from_fill(
        plan,
        fill_price=100.0,
        fill_quantity=10.0,
        filled_at="2026-09-15T09:00:00Z",
        cycle_id="cyc-explicit",
    )
    assert position is not None
    assert position.cycle_id == "cyc-explicit"


def test_a_position_state_stays_constructible_without_a_cycle() -> None:
    """``cycle_id`` es aditivo: el dataclass conserva su valor por defecto ``None``."""
    position = PositionState(
        position_id="p-1",
        trade_plan_id="tp-1",
        instrument_id="AAA",
        direction="long",
        status="OPEN",
        planned_entry=100.0,
        actual_entry=100.0,
        initial_stop=98.0,
        current_stop=98.0,
        target1=104.0,
        target2=108.0,
        quantity=10.0,
        remaining_quantity=10.0,
        initial_risk=2.0,
        realized_r=0.0,
        unrealized_r=None,
        mfe_mae={},
        thesis_health=None,
        protection_state=None,
        trailing=None,
        exit_status="none",
        created_at="2026-09-15T09:00:00Z",
        updated_at="2026-09-15T09:00:00Z",
    )
    assert position.cycle_id is None
