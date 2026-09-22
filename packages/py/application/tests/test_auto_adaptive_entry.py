"""AUTO-8 — gates del roadmap §10 para la capa de entrada (``plan_v2_tick`` + Adaptive).

Tres gates + el estrechamiento de asignación:

1. **flag OFF** ⇒ el payload del tick es byte-idéntico a AUTO-7 (``adaptive is None``, sin
   claves ``adaptive`` en el journal ni filas de embudo de pausa).
2. **ninguna recomendación Adaptive se salta los gates duros**: con ``halted=True`` (kill
   switch) o régimen ``UNKNOWN`` (exit-only) el motor sigue vetando aunque Adaptive marque
   ACTIVE y multiplicador 1.0.
3. **rotación con régimen sintético**: la misma estrategia se pausa en ``TREND_DOWN`` y se
   activa en ``TREND_UP``, y el tick filtra/emite en consecuencia.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from bolsa_analytics.cognitive.auto_adaptive import (
    AdaptivePlan,
    AllocationPlan,
    RotationDecision,
    RotationPlan,
    build_adaptive_plan,
)
from bolsa_analytics.cognitive.auto_self_evaluation import StrategySelfEvaluation
from bolsa_analytics.cognitive.measurement import (
    MEASUREMENT_COMPLETE,
    MEASUREMENT_UNKNOWN,
)
from bolsa_application.auto_reason_codes import ADAPTIVE_STRATEGY_PAUSED
from bolsa_application.auto_v2_entry import (
    V2Signal,
    build_worker_snapshot,
    plan_v2_tick,
    signal_identity_for_bar,
)

AS_OF = "2026-09-15T09:00:00Z"


def _row(
    version: str,
    *,
    decisive: bool = False,
    expectancy: str | None = None,
    win_rate: float | None = None,
) -> StrategySelfEvaluation:
    """Fila de self-evaluation mínima con SOLO lo que Adaptive lee (el resto, ausente)."""
    return StrategySelfEvaluation(
        strategy_version=version,
        trades=0,
        wins=0,
        losses=0,
        realized_pnl=Decimal("0"),
        expectancy_currency=Decimal(expectancy) if expectancy is not None else None,
        expectancy_r=None,
        net_expectancy_r=None,
        win_rate=win_rate,
        profit_factor=None,
        avg_win_currency=None,
        avg_loss_currency=None,
        mfe_r=None,
        mae_r=None,
        slippage_currency=None,
        rejection_cost_return=None,
        drawdown_currency=Decimal("0"),
        drawdown_share=None,
        traded=0,
        rejected=0,
        expired=0,
        missed=0,
        sample_quality="",
        results_measurement=MEASUREMENT_COMPLETE if decisive else MEASUREMENT_UNKNOWN,
        risk_measurement=MEASUREMENT_UNKNOWN,
        net_r_measurement=MEASUREMENT_UNKNOWN,
        cycles_without_cost=0,
        excursions_measurement=MEASUREMENT_UNKNOWN,
        slippage_measurement=MEASUREMENT_UNKNOWN,
        rejection_cost_measurement=MEASUREMENT_UNKNOWN,
        drawdown_measurement=MEASUREMENT_UNKNOWN,
        decisive=decisive,
        notes=(),
    )


def _snapshot():
    return build_worker_snapshot(
        account_id="acc-1",
        equity=100_000.0,
        cash=80_000.0,
        open_positions={},
        entry_prices={},
        regime="BULL_TREND",
        risk_budget_pct=6.0,
    )


def _signal(symbol: str = "AAA", *, strategy_version: str = "v42") -> V2Signal:
    identity = signal_identity_for_bar(
        instrument_id=symbol,
        action="BUY",
        strategy_version=strategy_version,
        timeframe="1d",
        moment=datetime(2026, 9, 15, 9, 0, tzinfo=UTC),
    )
    assert identity is not None
    return V2Signal(
        symbol,
        "BUY",
        price=100.0,
        atr=2.0,
        edge=0.9,
        sector="tech",
        liquidity_notional=1_000_000.0,
        strategy_version=strategy_version,
        signal_id=identity.signal_id,
        bar_timestamp=identity.bar_timestamp,
        valid_until=identity.valid_until,
    )


def _payloads(plan) -> list[dict]:
    return [dict(entry.payload) for entry in plan.journal_entries]


# ── Gate 1: flag OFF ⇒ byte-idéntico a AUTO-7 ────────────────────────────────────


def test_flag_off_payload_is_byte_identical_to_v47() -> None:
    plan = plan_v2_tick(
        snapshot=_snapshot(),
        signals=[_signal("AAA")],
        regime="BULL_TREND",
        as_of=AS_OF,
    )
    assert plan.adaptive is None
    # Ninguna clave ``adaptive`` se filtra en el journal (ni en la decisión, ni en
    # el rechazo), y ninguna fila del embudo es una pausa adaptativa.
    for payload in _payloads(plan):
        assert "adaptive" not in payload
    assert all(row.reason != ADAPTIVE_STRATEGY_PAUSED for row in plan.opportunities)

    # Pasar ``adaptive=None`` explícitamente es el MISMO camino: payloads idénticos.
    explicit = plan_v2_tick(
        snapshot=_snapshot(),
        signals=[_signal("AAA")],
        regime="BULL_TREND",
        as_of=AS_OF,
        adaptive=None,
    )
    assert explicit.adaptive is None
    assert _payloads(explicit) == _payloads(plan)


# ── Gate 2: Adaptive no se salta los gates duros ────────────────────────────────


def test_adaptive_cannot_bypass_kill_switch() -> None:
    """Adaptive marca ACTIVE y multiplicador 1.0, pero el kill switch sigue vetando."""
    adaptive = build_adaptive_plan((_row("v42", decisive=False),), "TREND_UP")
    assert not adaptive.is_paused("v42")
    assert adaptive.risk_multiplier_for("v42") == pytest.approx(1.0)

    plan = plan_v2_tick(
        snapshot=_snapshot(),
        signals=[_signal("AAA")],
        regime="BULL_TREND",
        as_of=AS_OF,
        halted=True,
        adaptive=adaptive,
    )
    assert plan.approved_symbols == ()
    assert "governor_halted" in plan.journal_entries[0].payload["reasonCodes"]


def test_adaptive_cannot_bypass_unknown_regime() -> None:
    """Adaptive ACTIVE no convierte un régimen UNKNOWN (exit-only) en operable."""
    adaptive = build_adaptive_plan((_row("v42", decisive=False),), "TREND_UP")
    plan = plan_v2_tick(
        snapshot=_snapshot(),
        signals=[_signal("AAA")],
        regime="",  # UNKNOWN ⇒ exit-only
        as_of=AS_OF,
        adaptive=adaptive,
    )
    assert plan.approved_symbols == ()
    assert "regime_invalid" in plan.journal_entries[0].payload["reasonCodes"]


# ── Gate 3: rotación con régimen sintético ──────────────────────────────────────


def test_rotation_synthetic_regime_pauses_then_activates() -> None:
    rows = (_row("v42", decisive=False, win_rate=0.2),)

    paused = plan_v2_tick(
        snapshot=_snapshot(),
        signals=[_signal("AAA")],
        regime="BULL_TREND",
        as_of=AS_OF,
        adaptive=build_adaptive_plan(rows, "TREND_DOWN"),
    )
    assert paused.approved_symbols == ()
    assert paused.journal_entries[0].payload["reasonCodes"] == [ADAPTIVE_STRATEGY_PAUSED]
    assert any(row.reason == ADAPTIVE_STRATEGY_PAUSED for row in paused.opportunities)

    active = plan_v2_tick(
        snapshot=_snapshot(),
        signals=[_signal("AAA")],
        regime="BULL_TREND",
        as_of=AS_OF,
        adaptive=build_adaptive_plan(rows, "TREND_UP"),
    )
    assert active.approved_symbols == ("AAA",)


# ── Estrechamiento de asignación (min con el techo del gobernador) ───────────────


def test_allocation_narrows_risk_cap() -> None:
    """Un multiplicador 0.5 reduce a la MITAD el presupuesto de riesgo de la operación."""
    baseline = plan_v2_tick(
        snapshot=_snapshot(),
        signals=[_signal("AAA")],
        regime="BULL_TREND",
        as_of=AS_OF,
    )
    full_risk = baseline.decisions[0].allocation["riskAmount"]
    assert full_risk > 0

    adaptive = AdaptivePlan(
        rotation=RotationPlan((RotationDecision(strategy_version="v42", active=True),)),
        allocation=AllocationPlan({"v42": 0.5}),
    )
    narrowed = plan_v2_tick(
        snapshot=_snapshot(),
        signals=[_signal("AAA")],
        regime="BULL_TREND",
        as_of=AS_OF,
        adaptive=adaptive,
    )
    half_risk = narrowed.decisions[0].allocation["riskAmount"]
    assert half_risk == pytest.approx(full_risk * 0.5)


# ── AUTO-8.1: neutralidad, invariante de gates y trazabilidad ────────────────────


def test_adaptive_on_neutral_is_byte_identical_to_off() -> None:
    """Sin rotación y con multiplicadores 1.0, AUTO-8 neutral debe ser == AUTO-7.

    Es la prueba de que la capa Adaptive no introduce efectos laterales cuando no tiene
    nada que recomendar: solo el flag OFF estaba cubierto antes.
    """
    neutral = build_adaptive_plan((_row("v42", decisive=False),), "TREND_UP")
    assert not neutral.is_paused("v42")
    assert neutral.risk_multiplier_for("v42") == pytest.approx(1.0)

    off = plan_v2_tick(
        snapshot=_snapshot(), signals=[_signal("AAA")], regime="BULL_TREND", as_of=AS_OF
    )
    on = plan_v2_tick(
        snapshot=_snapshot(),
        signals=[_signal("AAA")],
        regime="BULL_TREND",
        as_of=AS_OF,
        adaptive=neutral,
    )
    assert on.adaptive is neutral
    assert _payloads(on) == _payloads(off)
    assert on.approved_symbols == off.approved_symbols


def test_adaptive_only_changes_candidates_and_risk_cap_not_hard_gates() -> None:
    """Invariante: Adaptive NO toca gobernador, kill, régimen ni gates duros.

    Al estrechar la asignación (0.5) el gobernador, el conjunto aprobado y las candidatas
    vistas deben ser IDÉNTICOS al baseline; lo único que cambia es el techo de riesgo.
    """
    off = plan_v2_tick(
        snapshot=_snapshot(), signals=[_signal("AAA")], regime="BULL_TREND", as_of=AS_OF
    )
    adaptive = AdaptivePlan(
        rotation=RotationPlan((RotationDecision(strategy_version="v42", active=True),)),
        allocation=AllocationPlan({"v42": 0.5}),
    )
    on = plan_v2_tick(
        snapshot=_snapshot(),
        signals=[_signal("AAA")],
        regime="BULL_TREND",
        as_of=AS_OF,
        adaptive=adaptive,
    )
    assert on.governor_states == off.governor_states
    assert on.approved_symbols == off.approved_symbols
    assert on.seen_signals == off.seen_signals
    assert on.decisions[0].reason_codes == off.decisions[0].reason_codes
    assert on.decisions[0].allocation["riskAmount"] == pytest.approx(
        off.decisions[0].allocation["riskAmount"] * 0.5
    )


def test_narrowing_journal_carries_policy_version_and_evidence() -> None:
    """El journal declara la política y la evidencia que justificó el estrechamiento."""
    rows = (
        _row("v42", decisive=True, expectancy="3"),
        _row("v99", decisive=True, expectancy="1"),
    )
    adaptive = build_adaptive_plan(rows, "TREND_UP")
    assert adaptive.risk_multiplier_for("v99") == pytest.approx(0.5)

    plan = plan_v2_tick(
        snapshot=_snapshot(),
        signals=[_signal("AAA", strategy_version="v99")],
        regime="BULL_TREND",
        as_of=AS_OF,
        adaptive=adaptive,
    )
    entry = plan.journal_entries[0].payload
    assert entry["adaptive"]["riskMultiplier"] == pytest.approx(0.5)
    assert entry["adaptive"]["policyVersion"] == adaptive.policy_version
    evidence = entry["adaptive"]["evidence"]
    assert evidence["decisive"] is True
    assert evidence["expectancyCurrency"] == "1"
    assert evidence["netExpectancyR"] is None  # sin productor: declarado, no inventado
    assert evidence["regime"] == "UNKNOWN"


def test_pause_journal_carries_evidence_and_policy_version() -> None:
    rows = (_row("v42", decisive=True, expectancy="-2"),)
    adaptive = build_adaptive_plan(rows, "TREND_UP")
    plan = plan_v2_tick(
        snapshot=_snapshot(),
        signals=[_signal("AAA")],
        regime="BULL_TREND",
        as_of=AS_OF,
        adaptive=adaptive,
    )
    entry = plan.journal_entries[0].payload
    assert entry["reasonCodes"] == [ADAPTIVE_STRATEGY_PAUSED]
    assert entry["adaptive"]["policyVersion"] == adaptive.policy_version
    evidence = entry["adaptiveEvidence"]
    assert evidence["decisive"] is True
    assert evidence["expectancyCurrency"] == "-2"
