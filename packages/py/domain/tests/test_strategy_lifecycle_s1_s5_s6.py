"""S1/S5/S6 — la máquina de estados no promociona sin evidencia ni con evidencia ajena."""

from __future__ import annotations

from bolsa_domain.entities.strategy_lifecycle import (
    PROMOTION_GATES,
    CoachAssessment,
    GateResult,
    ShadowValidationResult,
    StrategyLifecycleState,
    StrategyValidation,
    can_transition,
)

_P = StrategyLifecycleState.PROMOCION


def _validation(finalist_id: str = "ver-1") -> StrategyValidation:
    return StrategyValidation(
        finalist_id=finalist_id,
        gates=tuple(GateResult.passed_gate(g) for g in PROMOTION_GATES),
    )


def _shadow(version_id: str = "ver-1", passed: bool = True) -> ShadowValidationResult:
    return ShadowValidationResult(version_id=version_id, trades=30, passed=passed)


def _coach(approved: bool = True) -> CoachAssessment:
    return CoachAssessment(
        candidate_id="c", approved=approved, contradictions=() if approved else ("x",)
    )


def test_s1_promocion_without_evidence_is_blocked() -> None:
    result = can_transition(state=_P)
    assert not result.allowed
    assert "validacion_ausente" in result.reasons


def test_s1_promocion_requires_coach_and_shadow() -> None:
    assert "coach_ausente" in can_transition(
        state=_P, validation=_validation(), shadow=_shadow()
    ).reasons
    assert "coach_veto" in can_transition(
        state=_P, validation=_validation(), shadow=_shadow(), coach=_coach(False)
    ).reasons
    assert "shadow_validation_requerida" in can_transition(
        state=_P, validation=_validation(), coach=_coach()
    ).reasons
    assert "shadow_validation_requerida" in can_transition(
        state=_P, validation=_validation(), coach=_coach(), shadow=_shadow(passed=False)
    ).reasons


def test_s1_promocion_with_full_evidence_is_allowed() -> None:
    result = can_transition(state=_P, validation=_validation(), shadow=_shadow(), coach=_coach())
    assert result.allowed
    assert result.to_state == StrategyLifecycleState.ACTIVE


def test_s6_evidence_from_other_version_is_blocked() -> None:
    result = can_transition(
        state=_P, validation=_validation(), shadow=_shadow("ver-OTRA"), coach=_coach()
    )
    assert not result.allowed
    assert "evidencia_shadow_otra_version" in result.reasons


def test_s5_required_gates_must_be_present() -> None:
    gates = (GateResult.passed_gate("backtest"),)
    blocked = can_transition(
        state=StrategyLifecycleState.LABORATORIO, gates=gates, required_gates=("backtest", "oos")
    )
    assert not blocked.allowed
    assert "oos" in blocked.reasons[0]
    ok = can_transition(
        state=StrategyLifecycleState.LABORATORIO, gates=gates, required_gates=("backtest",)
    )
    assert ok.allowed
