"""V2.88.99 — la identidad de la OPORTUNIDAD se sella en la decisión APROBADA.

Cierra la etapa ``oportunidad → decisión`` del recorrido AUTO. Hasta aquí: los candidatos
RECHAZADOS ya publicaban ``opportunityScore``/``rank``, pero su ``decision_id`` (``REJ-…``)
no enlaza con el ciclo; la decisión APROBADA enlazaba por ``cycle_id`` pero **no** sellaba
``signalId``/``opportunityScore``/``rank``, de modo que ``TOP_N`` (y ``RISK``) quedaban
estructuralmente indemostrables para toda operación TOMADA.

Estos tests certifican (y una mutación debe poder romper):

* La decisión APROBADA sella ``signalId``, ``opportunityScore`` y ``rank``.
* El monitor enciende ``SIGNAL``/``TOP_N``/``RISK`` desde esa MISMA entrada durable (no desde
  una etapa anterior ni desde una foto paralela).
* DOS settlements del mismo ciclo se DECLARAN (``duplicate_settlement_cycle``), no se pisan en
  silencio.

Módulo puro: sin I/O, sin reloj real, sin PostgreSQL.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

from bolsa_application.auto_operational_monitor import (
    STEP_REACHED,
    build_operational_monitor,
)
from bolsa_application.auto_v2_entry import (
    V2Signal,
    V2Tunables,
    build_worker_snapshot,
    plan_v2_tick,
    signal_identity_for_bar,
)

_MOMENT = datetime(2026, 9, 15, 9, 0, tzinfo=UTC)


def _snapshot(*, cash: float = 80_000.0) -> Any:
    return build_worker_snapshot(
        account_id="acc-1",
        equity=100_000.0,
        cash=cash,
        open_positions={},
        entry_prices={},
        regime="BULL_TREND",
        risk_budget_pct=6.0,
    )


def _signal(symbol: str, *, edge: float = 0.9) -> V2Signal:
    identity = signal_identity_for_bar(
        instrument_id=symbol,
        action="BUY",
        strategy_version="v42",
        timeframe="1d",
        moment=_MOMENT,
    )
    assert identity is not None
    return V2Signal(
        symbol,
        "BUY",
        price=100.0,
        atr=2.0,
        edge=edge,
        sector="tech",
        liquidity_notional=1_000_000.0,
        strategy_version="v42",
        signal_id=identity.signal_id,
        bar_timestamp=identity.bar_timestamp,
        valid_until=identity.valid_until,
        p_win=0.5,
        avg_loss_r=-1.0,
        target_price=110.0,
    )


def _approved_entries(plan: Any) -> list[Any]:
    return [
        entry
        for entry in plan.journal_entries
        if (entry.payload or {}).get("event") == "auto_entry_decision"
        and (entry.payload or {}).get("approved") is True
    ]


def _reservation(*, cycle_id: str, instrument_id: str) -> Any:
    return SimpleNamespace(
        reservation_id="res-1",
        cycle_id=cycle_id,
        side="buy",
        quantity=10.0,
        remaining_qty=0.0,
        released_qty=10.0,
        status="RELEASED_BY_FILL",
        created_at="2026-01-01T00:00:00Z",
        reserved_risk=50.0,
        stop=95.0,
        entry=100.0,
        instrument_id=instrument_id,
        strategy_version_id="v42",
        release_reason="fill",
        is_live=False,
    )


def _step(steps: list[dict[str, Any]], step_id: str) -> dict[str, Any]:
    return next(step for step in steps if step["id"] == step_id)


def _fact(step: dict[str, Any], key: str) -> dict[str, Any]:
    return next(fact for fact in step["facts"] if fact["key"] == key)


def test_approved_decision_seals_the_opportunity_identity() -> None:
    """La decisión aprobada publica ``signalId``, ``opportunityScore`` y ``rank``."""
    plan = plan_v2_tick(
        snapshot=_snapshot(),
        signals=[_signal("AAA")],
        regime="BULL_TREND",
        as_of="2026-09-15T09:00:00Z",
        tunables=V2Tunables(optimizer_enabled=False),
    )

    entries = _approved_entries(plan)
    assert len(entries) == 1
    payload = entries[0].payload
    # La señal que originó la operación: sin ella el enlace es un hash de un solo sentido.
    assert payload["signalId"] == _signal("AAA").signal_id
    # El score y el rank REALES del ranking (no un relleno).
    assert payload["opportunityScore"] is not None
    assert payload["rank"] == 1


def test_monitor_reaches_top_n_and_risk_from_the_sealed_decision() -> None:
    """``SIGNAL``/``TOP_N``/``RISK`` se encienden desde la MISMA entrada durable aprobada."""
    plan = plan_v2_tick(
        snapshot=_snapshot(),
        signals=[_signal("AAA")],
        regime="BULL_TREND",
        as_of="2026-09-15T09:00:00Z",
        tunables=V2Tunables(optimizer_enabled=False),
    )
    entry = _approved_entries(plan)[0]
    cycle_id = entry.payload["cycleId"]

    dto = build_operational_monitor(
        account_id="acc-1",
        reservations=[_reservation(cycle_id=cycle_id, instrument_id="AAA")],
        journal=[entry],
    )
    steps = dto["cycles"][0]["steps"]
    assert _step(steps, "SIGNAL")["state"] == STEP_REACHED
    assert _step(steps, "TOP_N")["state"] == STEP_REACHED
    assert _step(steps, "RISK")["state"] == STEP_REACHED
    # El hecho expuesto es el REAL sellado por el productor.
    assert _fact(_step(steps, "TOP_N"), "rank")["value"] == entry.payload["rank"]
    assert _fact(_step(steps, "SIGNAL"), "score")["value"] == entry.payload["opportunityScore"]
    # El envoltorio de riesgo sale de la asignación durable (``quantity``) y el plan (``stop``).
    assert _fact(_step(steps, "RISK"), "quantity")["value"] == entry.payload["risk"]["quantity"]
    assert _fact(_step(steps, "RISK"), "stop")["value"] == entry.payload["tradePlan"]["structuralStop"]


def test_duplicate_settlements_are_declared_not_silently_overwritten() -> None:
    """Dos settlements del mismo ciclo se declaran contradictorios; se conserva el primero."""
    reservation = _reservation(cycle_id="cyc-1", instrument_id="AAA")
    first = {
        "cycleId": "cyc-1",
        "settlementId": "settle-1",
        "pnl": 5.0,
        "pnlMeasurement": "COMPLETE",
        "settledAt": "2026-01-03T00:00:00Z",
    }
    second = {
        "cycleId": "cyc-1",
        "settlementId": "settle-2",
        "pnl": 7.0,
        "pnlMeasurement": "COMPLETE",
        "settledAt": "2026-01-04T00:00:00Z",
    }
    dto = build_operational_monitor(
        account_id="acc-1", reservations=[reservation], settlements=[first, second]
    )
    cycle = dto["cycles"][0]
    step = _step(cycle["steps"], "SETTLEMENT")
    assert step["state"] == STEP_REACHED
    assert step["note"] == "duplicate_settlement_cycle"
    assert step["measurement"] == "PARTIAL"
    assert "duplicate_settlement_cycle" in cycle["notes"]
    # Determinista: se conserva el PRIMERO (el más reciente, según el orden de lectura).
    assert _fact(step, "pnl")["value"] == 5.0
