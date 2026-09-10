"""V2.25 / A10 — Strategy Lifecycle: máquina de estados y Promotion Gate.

Tests herméticos/unitarios del dominio puro (sin DB, sin red): el embudo avanza solo
con gates en PASS, el COACH no puede saltarse los gates cuantitativos, y la promoción
exige evidencia + shadow (anti strategy-chasing).
"""

from __future__ import annotations

from bolsa_domain.entities.strategy_lifecycle import (
    PROMOTION_GATES,
    CoachAssessment,
    GateResult,
    GateStatus,
    StrategyCandidate,
    StrategyEvaluation,
    StrategyFinalist,
    StrategyHealth,
    StrategyLifecycleState,
    StrategyTop3,
    StrategyValidation,
    can_transition,
    evaluate_promotion,
    next_state,
)


def _all_gates_pass() -> tuple[GateResult, ...]:
    return tuple(GateResult.passed_gate(g) for g in PROMOTION_GATES)


def _finalist() -> StrategyFinalist:
    return StrategyFinalist(
        candidate_id="cand-1",
        version_id="ver-1",
        name="SMA-20/50",
        definition_hash="hash-1",
        definition={"family": "sma"},
    )


def _coach_approves() -> CoachAssessment:
    return CoachAssessment(candidate_id="cand-1", approved=True)


# ── Orden del embudo ────────────────────────────────────────────────────────────


def test_funnel_order_is_linear() -> None:
    assert next_state(StrategyLifecycleState.ESTUDIO) == StrategyLifecycleState.LABORATORIO
    assert next_state(StrategyLifecycleState.LABORATORIO) == StrategyLifecycleState.TOP3
    assert next_state(StrategyLifecycleState.TOP3) == StrategyLifecycleState.COACH
    assert next_state(StrategyLifecycleState.COACH) == StrategyLifecycleState.FINALISTA
    assert next_state(StrategyLifecycleState.FINALISTA) == StrategyLifecycleState.VALIDACION
    assert next_state(StrategyLifecycleState.VALIDACION) == StrategyLifecycleState.PROMOCION
    assert next_state(StrategyLifecycleState.PROMOCION) == StrategyLifecycleState.ACTIVE
    assert next_state(StrategyLifecycleState.ACTIVE) is None
    assert next_state(StrategyLifecycleState.REJECTED) is None


# ── Fail-closed de gates ────────────────────────────────────────────────────────


def test_gate_not_evaluated_is_not_pass() -> None:
    assert not GateResult(gate="oos", status=GateStatus.NOT_EVALUATED).passed


def test_evaluation_without_gates_does_not_pass() -> None:
    ev = StrategyEvaluation(candidate_id="cand-1", score=1.0)
    assert ev.gates_passed is False


def test_transition_blocked_by_failed_gate() -> None:
    result = can_transition(
        state=StrategyLifecycleState.LABORATORIO,
        gates=(GateResult.passed_gate("backtest"), GateResult.failed("oos")),
    )
    assert not result.allowed
    assert result.to_state == StrategyLifecycleState.TOP3
    assert "oos" in result.reasons[0]


def test_top3_rejects_more_than_three() -> None:
    import pytest

    with pytest.raises(ValueError):
        StrategyTop3(instrument_id="i", candidate_ids=("a", "b", "c", "d"))


# ── COACH advisory: veta, no aprueba por encima de gates ─────────────────────────


def test_coach_veto_blocks_even_with_quantitative_gates() -> None:
    result = can_transition(
        state=StrategyLifecycleState.COACH,
        gates=(GateResult.passed_gate("coach_quant"),),
        coach=CoachAssessment(candidate_id="cand-1", approved=False, contradictions=("regimen",)),
    )
    assert not result.allowed
    assert "coach_veto" in result.reasons


def test_coach_cannot_bypass_missing_quantitative_gates() -> None:
    """Aunque el COACH apruebe, la validación sin los 6 gates NO promociona."""
    validation = StrategyValidation(
        finalist_id="ver-1",
        gates=(GateResult.passed_gate("backtest"),),  # faltan 5
    )
    promo = evaluate_promotion(
        finalist=_finalist(),
        validation=validation,
        coach=_coach_approves(),
        shadow_validated=True,
    )
    assert not promo.promoted
    assert any("gates_no_superados" in r for r in promo.reasons)


# ── Promotion Gate ──────────────────────────────────────────────────────────────


def test_promotion_requires_shadow_validation() -> None:
    validation = StrategyValidation(finalist_id="ver-1", gates=_all_gates_pass())
    promo = evaluate_promotion(
        finalist=_finalist(),
        validation=validation,
        coach=_coach_approves(),
        shadow_validated=False,
    )
    assert not promo.promoted
    assert "shadow_validation_requerida" in promo.reasons


def test_promotion_blocked_by_coach_veto() -> None:
    validation = StrategyValidation(finalist_id="ver-1", gates=_all_gates_pass())
    promo = evaluate_promotion(
        finalist=_finalist(),
        validation=validation,
        coach=CoachAssessment(candidate_id="cand-1", approved=True, contradictions=("contradice T1",)),
        shadow_validated=True,
    )
    assert not promo.promoted
    assert "coach_veto" in promo.reasons


def test_promotion_happy_path_needs_all_conditions() -> None:
    validation = StrategyValidation(finalist_id="ver-1", gates=_all_gates_pass())
    promo = evaluate_promotion(
        finalist=_finalist(),
        validation=validation,
        coach=_coach_approves(),
        shadow_validated=True,
    )
    assert promo.promoted
    assert promo.reasons == ()
    assert promo.shadow_validated


def test_validation_missing_gates_are_reported() -> None:
    validation = StrategyValidation(
        finalist_id="ver-1",
        gates=(GateResult.passed_gate("backtest"), GateResult.passed_gate("risk")),
    )
    assert not validation.passed
    assert set(validation.missing_gates) == set(PROMOTION_GATES) - {"backtest", "risk"}


# ── Vigilancia: degradación vuelve al LAB, nunca swap directo ────────────────────


def test_health_degraded_below_threshold() -> None:
    healthy = StrategyHealth(
        version_id="ver-1",
        as_of="2026-09-10",
        edge=0.4,
        thresholds={"edge": 0.2},
    )
    assert not healthy.degraded
    unhealthy = StrategyHealth(
        version_id="ver-1",
        as_of="2026-09-10",
        edge=0.1,
        thresholds={"edge": 0.2},
    )
    assert unhealthy.degraded


def test_degraded_goes_back_to_lab_not_direct_swap() -> None:
    result = can_transition(state=StrategyLifecycleState.DEGRADED)
    assert result.allowed
    assert result.to_state == StrategyLifecycleState.LABORATORIO


def test_active_is_terminal_in_the_funnel() -> None:
    result = can_transition(state=StrategyLifecycleState.ACTIVE)
    assert not result.allowed
    assert result.to_state is None


def test_candidate_carries_data_snapshot_for_reproducibility() -> None:
    cand = StrategyCandidate(
        id="cand-1",
        instrument_id="inst-1",
        strategy_family="sma",
        params={"fast": 20, "slow": 50},
        data_snapshot_id="snap-2026-09-10",
    )
    assert cand.data_snapshot_id == "snap-2026-09-10"
