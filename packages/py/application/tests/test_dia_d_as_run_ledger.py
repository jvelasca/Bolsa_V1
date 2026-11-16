"""Tests del ledger por operación del DÍA-D as-run (Fase 3, ADR-050).

Cubren tres cosas que antes no se podían leer del artefacto:

* una fila por **posición** (no por fill) con entrada, salida y R neto;
* posiciones **abiertas** marcadas a mercado en un bloque aparte (``unrealizedR``), nunca
  sumadas al realizado;
* **calidad de la decisión** distinta del resultado: un ciclo perdedor ejecutado por regla es
  ``consistent``.
"""

from __future__ import annotations

from bolsa_application.dia_d_as_run import (
    ARM_AS_RUN,
    ARM_HOLD_STRUCTURAL,
    OUTCOME_LOSS,
    OUTCOME_UNMEASURED,
    OUTCOME_WIN,
    QUALITY_CONSISTENT,
    QUALITY_INCONSISTENT,
    AsRunExecutionModel,
    AsRunFill,
    AsRunLeg,
    AsRunRiskReference,
    build_as_run_artifact,
    mark_open_positions,
    run_as_run_arm,
    run_hold_arm,
)
from bolsa_domain.entities.ohlcv_bar import OhlcvBar

DAY = "2026-01-01"
FREE = AsRunExecutionModel(commission_bps=0.0)


def _bar(timestamp: str, *, open_: float, high: float, low: float, close: float) -> OhlcvBar:
    return OhlcvBar(timestamp=timestamp, open=open_, high=high, low=low, close=close, volume=10_000)


def _leg(**overrides: object) -> AsRunLeg:
    base: dict[str, object] = {
        "instrument_id": "AAA",
        "direction": "long",
        "quantity": 10.0,
        "entry": 100.0,
        "structural_stop": 95.0,
        "target1": 110.0,
    }
    base.update(overrides)
    return AsRunLeg(**base)  # type: ignore[arg-type]


def _buy(day: str, price: float = 100.0, qty: float = 10.0) -> AsRunFill:
    return AsRunFill(f"{day}T10:00:00", "AAA", "buy", qty, price)


def _sell(day: str, price: float, qty: float = 10.0) -> AsRunFill:
    return AsRunFill(f"{day}T16:00:00", "AAA", "sell", qty, price)


def test_as_run_ledger_has_one_row_per_position_not_per_fill() -> None:
    fills = [
        _buy("2026-01-02", 100.0, 5.0),
        _buy("2026-01-02", 100.0, 5.0),
        _sell("2026-01-05", 110.0, 5.0),
        _sell("2026-01-06", 110.0, 5.0),
    ]
    arm = run_as_run_arm(
        [_leg()],
        fills,
        execution=FREE,
        risk_references=[AsRunRiskReference("AAA", 100.0, 95.0)],
    )
    assert arm.cycles == 1
    assert len(arm.ledger) == 1
    row = arm.ledger[0]
    assert row.entry_price == 100.0
    assert row.exit_price == 110.0
    assert row.net_r == 2.0
    assert row.outcome == OUTCOME_WIN
    assert row.decision_quality == QUALITY_CONSISTENT
    assert row.exit_day == "2026-01-06"


def test_losing_trade_that_followed_the_rule_is_a_consistent_decision() -> None:
    arm = run_as_run_arm(
        [_leg()],
        [_buy("2026-01-02"), _sell("2026-01-03", 96.0)],
        execution=FREE,
        risk_references=[AsRunRiskReference("AAA", 100.0, 95.0)],
    )
    row = arm.ledger[0]
    assert row.outcome == OUTCOME_LOSS
    assert row.decision_quality == QUALITY_CONSISTENT
    assert row.net_r == -0.8


def test_unmatched_sell_is_declared_inconsistent() -> None:
    arm = run_as_run_arm([], [_sell("2026-01-03", 100.0)], execution=FREE)
    assert arm.measured is False
    assert arm.reason == "no_closed_cycles"
    assert len(arm.ledger) == 1
    assert arm.ledger[0].decision_quality == QUALITY_INCONSISTENT
    assert arm.ledger[0].outcome == OUTCOME_UNMEASURED


def test_open_position_is_marked_separately_and_never_added_to_realized() -> None:
    fills = [_buy("2026-01-02", 100.0)]
    bars = {"AAA": [_bar("2026-01-05", open_=104.0, high=108.0, low=103.0, close=107.0)]}
    arm = run_as_run_arm(
        [_leg()], fills, execution=FREE, risk_references=[AsRunRiskReference("AAA", 100.0, 95.0)]
    )
    assert arm.realized_r is None
    open_rows = mark_open_positions(
        [],
        fills,
        bars,
        risk_references=[AsRunRiskReference("AAA", 100.0, 95.0)],
        to_day="2026-01-31",
        execution=FREE,
    )
    assert len(open_rows) == 1
    assert open_rows[0].measured is True
    assert open_rows[0].unrealized_r == 1.4
    assert open_rows[0].mark_day == "2026-01-05"


def test_open_position_without_bars_declares_the_gap() -> None:
    rows = mark_open_positions([_leg()], [_buy("2026-01-02")], {}, execution=FREE)
    assert rows[0].measured is False
    assert rows[0].reason == "no_bars"
    assert rows[0].unrealized_r is None


def test_artifact_exposes_unrealized_r_without_touching_certification_fields() -> None:
    bars = {"AAA": [_bar("2026-01-05", open_=104.0, high=112.0, low=103.0, close=111.0)]}
    artifact = build_as_run_artifact(
        day=DAY,
        account_id="acct",
        legs=[],
        fills=[_buy("2026-01-02")],
        bars_by_instrument=bars,
        to_day="2026-01-31",
        execution=FREE,
        universe_instruments=["AAA"],
        risk_references=[AsRunRiskReference("AAA", 100.0, 95.0)],
    )
    as_run = next(arm for arm in artifact["arms"] if arm["arm"] == ARM_AS_RUN)
    assert as_run["realizedR"] is None
    assert as_run["unrealizedR"] == 2.2
    assert as_run["openPositions"][0]["measured"] is True
    assert as_run["ledger"] == []
    assert artifact["schemaVersion"]


def test_hold_arm_ledger_records_the_rule_that_fired() -> None:
    bars = {
        "AAA": [
            _bar("2026-01-02", open_=100.0, high=101.0, low=99.0, close=100.5),
            _bar("2026-01-03", open_=99.0, high=99.0, low=94.0, close=94.0),
        ]
    }
    arm = run_hold_arm([_leg()], bars, after=DAY, execution=FREE)
    assert arm.measured is True
    assert len(arm.ledger) == 1
    row = arm.ledger[0]
    assert row.arm == ARM_HOLD_STRUCTURAL
    assert row.exit_reason == "stop"
    assert row.exit_price == 95.0
    assert row.days_held == 2
    assert row.outcome == OUTCOME_LOSS
    assert row.decision_quality == QUALITY_CONSISTENT
    assert row.structural_stop == 95.0


def test_hold_arm_ledger_declares_missing_instrument() -> None:
    arm = run_hold_arm([_leg()], {}, after=DAY, execution=FREE)
    assert arm.measured is False
    assert arm.ledger[0].outcome == OUTCOME_UNMEASURED
    assert arm.ledger[0].reason_codes == ("no_bars",)
