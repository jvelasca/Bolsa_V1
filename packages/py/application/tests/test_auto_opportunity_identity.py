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

from bolsa_application.auto_operational_audit import build_position_materialized_entry
from bolsa_application.auto_operational_monitor import (
    STEP_REACHED,
    build_operational_monitor,
)
from bolsa_application.auto_v2_entry import (
    V2Signal,
    V2Tunables,
    auto_opportunity_id,
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


def test_opportunity_id_is_derived_from_signal_identity_and_exempt_from_rank() -> None:
    """La identidad de la oportunidad es ESTABLE y NO depende del ranking de la corrida.

    Es una identidad de PRIMERA CLASE derivada de la identidad de señal/barra, de modo que
    ``oportunidad → decisión`` es demostrable sin apoyarse en el ``rank`` (posicional y
    reasignado en cada corrida).
    """
    signal = _signal("AAA")
    opp = auto_opportunity_id(signal=signal)
    assert opp.startswith("opp-")
    # Determinista: dos invocaciones de la MISMA señal/barra convergen.
    assert opp == auto_opportunity_id(signal=_signal("AAA"))
    # Distinta señal/barra ⇒ distinta oportunidad (no colisiona por instrumento suelto).
    assert opp != auto_opportunity_id(signal=_signal("BBB"))
    # La identidad NO se acuña con ``rank`` ni con la cuenta: es del MERCADO (misma oportunidad
    # tomada por varias cuentas comparte ``opportunityId`` y se separa por ``cycle_id``).
    assert opp == auto_opportunity_id(signal=_signal("AAA", edge=0.1))


def test_approved_decision_seals_the_opportunity_id_and_the_cycle_exposes_it() -> None:
    """La decisión aprobada sella ``opportunityId`` y el monitor lo expone en el ciclo."""
    plan = plan_v2_tick(
        snapshot=_snapshot(),
        signals=[_signal("AAA")],
        regime="BULL_TREND",
        as_of="2026-09-15T09:00:00Z",
        tunables=V2Tunables(optimizer_enabled=False),
    )
    entry = _approved_entries(plan)[0]
    expected = auto_opportunity_id(signal=_signal("AAA"))
    assert entry.payload["opportunityId"] == expected
    cycle_id = entry.payload["cycleId"]

    dto = build_operational_monitor(
        account_id="acc-1",
        reservations=[_reservation(cycle_id=cycle_id, instrument_id="AAA")],
        journal=[entry],
    )
    cycle = dto["cycles"][0]
    # El vínculo ``oportunidad → ciclo → (reserva/orden/fill/protección/cierre/PnL)`` se cierra
    # por el ``opportunityId`` del ciclo + su ``cycleId``, sin depender del ranking.
    assert cycle["opportunityId"] == expected
    assert _fact(_step(cycle["steps"], "SIGNAL"), "opportunityId")["value"] == expected


def test_cycle_without_opportunity_fact_declares_absence_never_a_placeholder() -> None:
    """Sin hecho de decisión, el ciclo NO finge una ``opportunityId`` (``None``)."""
    dto = build_operational_monitor(
        account_id="acc-1",
        reservations=[_reservation(cycle_id="cyc-1", instrument_id="AAA")],
    )
    assert dto["cycles"][0]["opportunityId"] is None


def test_cycle_exposes_the_durable_portfolio_decision_and_the_position_trace() -> None:
    """F2-2/F2-1 — el ciclo EXPONE la decisión durable y la traza durable de posición.

    La decisión de cartera se lee del hecho ``auto_entry_decision`` (no del ranking) y la
    posición, de la fila durable ligada al ciclo: la escalera deja de ser un hueco cuando el
    hecho existe, sin saltar de un fill a «posición creada».
    """
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
        positions={
            "AAA": {
                "positionState": {
                    "cycleId": cycle_id,
                    "quantity": 10.0,
                    "lifecycleState": "OPEN",
                },
                "stopPrice": 95.0,
                "highWatermark": 101.0,
                "t1State": "pending",
                "trailingState": "off",
            }
        },
    )
    cycle = dto["cycles"][0]
    # F2-2 — la decisión es la MISMA que selló el productor (durable), no una reconstrucción.
    decision = cycle["decision"]
    assert decision is not None
    assert decision["decisionId"] == entry.decision_id
    assert decision["approved"] is True
    assert decision["opportunityId"] == entry.payload["opportunityId"]
    # F2-1 — la posición está TRAZADA por el ciclo; un fill sin traza no la habría creado.
    position = cycle["position"]
    assert position is not None
    assert position["state"] == STEP_REACHED
    assert _fact(position, "quantity")["value"] == 10.0
    assert _fact(position, "stopPrice")["value"] == 95.0


def test_cycle_without_decision_or_position_declares_absence() -> None:
    """Sin hechos, la decisión y la posición se declaran ausentes (``None``), no se fabrican."""
    dto = build_operational_monitor(
        account_id="acc-1",
        reservations=[_reservation(cycle_id="cyc-1", instrument_id="AAA")],
    )
    cycle = dto["cycles"][0]
    assert cycle["decision"] is None
    assert cycle["position"] is None


def test_position_trace_prefers_the_durable_materialization_event() -> None:
    """F2-1 — el hecho append-only ``auto_position_materialized`` da la traza por operación.

    A diferencia del espejo ``sim_auto_positions`` (por símbolo y reescribible), el hecho liga
    la posición a su ``cycle_id`` y sobrevive a la reutilización del símbolo.
    """
    entry = build_position_materialized_entry(
        instrument_id="AAA",
        quantity=10.0,
        entry_price=100.0,
        execution_id="exec-1",
        strategy_version="v42",
        cycle_id="cyc-1",
        actor="engine",
        as_of="2026-01-01T00:00:00Z",
        account_id="acc-1",
    )
    assert entry is not None
    dto = build_operational_monitor(
        account_id="acc-1",
        reservations=[_reservation(cycle_id="cyc-1", instrument_id="AAA")],
        journal=[entry],
    )
    position = dto["cycles"][0]["position"]
    assert position is not None
    assert position["state"] == STEP_REACHED
    assert _fact(position, "quantity")["value"] == 10.0
    assert _fact(position, "provenance")["value"] == "auto_position_materialized"


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
