"""R1 — el hueco decisión→ejecución se veta y la geometría se ancla al precio de ejecución."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from bolsa_application.auto_v2_entry import (
    V2Signal,
    V2Tunables,
    build_worker_snapshot,
    plan_v2_tick,
    signal_identity_for_bar,
)

_MOMENT = datetime(2026, 10, 5, 9, 0, tzinfo=UTC)


def _plan(*, price: float, execution_price: float | None, tunables: V2Tunables | None = None) -> Any:
    identity = signal_identity_for_bar(
        instrument_id="AAA",
        action="BUY",
        strategy_version="v42",
        timeframe="1d",
        moment=_MOMENT,
    )
    assert identity is not None
    signal = V2Signal(
        "AAA",
        "BUY",
        price=price,
        atr=2.0,
        edge=0.9,
        sector="tech",
        liquidity_notional=1_000_000.0,
        strategy_version="v42",
        signal_id=identity.signal_id,
        bar_timestamp=identity.bar_timestamp,
        valid_until=identity.valid_until,
        p_win=0.5,
        avg_loss_r=-1.0,
        execution_price=execution_price,
    )
    snapshot = build_worker_snapshot(
        account_id="acc-1",
        equity=100_000.0,
        cash=80_000.0,
        open_positions={},
        entry_prices={},
        regime="BULL_TREND",
        risk_budget_pct=6.0,
    )
    return plan_v2_tick(
        snapshot=snapshot,
        signals=[signal],
        regime="BULL_TREND",
        as_of="2026-10-05T09:00:00Z",
        tunables=tunables or V2Tunables(optimizer_enabled=False),
    )


def _decision(plan: Any) -> dict[str, Any]:
    return next(
        e.payload
        for e in plan.journal_entries
        if (e.payload or {}).get("event") == "auto_entry_decision"
    )


def test_gap_above_tolerance_vetoes_the_entry() -> None:
    plan = _plan(price=100.0, execution_price=103.0)  # 1,5 ATR > 1 ATR
    payload = _decision(plan)
    assert payload["approved"] is False
    assert "entry_gap_exceeded" in str(payload)
    assert not plan.entry_packages


def test_gap_down_above_tolerance_also_vetoes() -> None:
    plan = _plan(price=100.0, execution_price=97.0)
    assert _decision(plan)["approved"] is False
    assert not plan.entry_packages


def test_gap_within_tolerance_anchors_geometry_to_execution_price() -> None:
    plan = _plan(price=100.0, execution_price=101.0)
    assert _decision(plan)["approved"] is True
    package = plan.entry_packages["AAA"]
    assert package is not None
    # stop = ejecución − 1,5·ATR = 98 ⇒ riesgo por acción 3 sobre el precio de ejecución.
    decision = next(d for d in plan.decisions if d.instrument_id == "AAA")
    assert decision.trade_plan is not None
    assert decision.trade_plan.entry == 101.0
    assert decision.trade_plan.structural_stop == 98.0


def test_without_execution_price_the_tick_is_historical() -> None:
    plan = _plan(price=100.0, execution_price=None)
    decision = next(d for d in plan.decisions if d.instrument_id == "AAA")
    assert decision.trade_plan is not None
    assert decision.trade_plan.entry == 100.0


def test_tolerance_is_configurable() -> None:
    plan = _plan(
        price=100.0,
        execution_price=103.0,
        tunables=V2Tunables(optimizer_enabled=False, max_entry_gap_atr=2.0),
    )
    assert _decision(plan)["approved"] is True


def test_synthetic_atr_cannot_veto_the_entry() -> None:
    """Sin ATR MEDIDO no hay tolerancia: el sintético (2 % del precio) no es una medición.

    Con ``atr=None`` el motor sigue derivando la geometría del fallback (R5 declarada), pero
    el hueco NO se veta: un umbral calculado sobre un ATR inventado sería un umbral
    disfrazado (un 2 % de hueco vetaría siempre). El anclaje a la ejecución SÍ se aplica.
    """
    identity = signal_identity_for_bar(
        instrument_id="AAA",
        action="BUY",
        strategy_version="v42",
        timeframe="1d",
        moment=_MOMENT,
    )
    assert identity is not None
    signal = V2Signal(
        "AAA",
        "BUY",
        price=100.0,
        atr=None,
        edge=0.9,
        sector="tech",
        liquidity_notional=1_000_000.0,
        strategy_version="v42",
        signal_id=identity.signal_id,
        bar_timestamp=identity.bar_timestamp,
        valid_until=identity.valid_until,
        p_win=0.5,
        avg_loss_r=-1.0,
        execution_price=104.0,  # 2 ATR sintéticos (2 % de 100) — vetaría si se midiera así.
    )
    snapshot = build_worker_snapshot(
        account_id="acc-1",
        equity=100_000.0,
        cash=80_000.0,
        open_positions={},
        entry_prices={},
        regime="BULL_TREND",
        risk_budget_pct=6.0,
    )
    plan = plan_v2_tick(
        snapshot=snapshot,
        signals=[signal],
        regime="BULL_TREND",
        as_of="2026-10-05T09:00:00Z",
        tunables=V2Tunables(optimizer_enabled=False),
    )
    assert _decision(plan)["approved"] is True
    decision = next(d for d in plan.decisions if d.instrument_id == "AAA")
    assert decision.trade_plan is not None
    # El anclaje a la ejecución NO depende de que el ATR esté medido.
    assert decision.trade_plan.entry == 104.0
