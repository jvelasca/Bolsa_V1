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
    PaperForwardPolicy,
    ShadowPolicy,
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
        coach=CoachAssessment(
            candidate_id="cand-1", approved=True, contradictions=("contradice T1",)
        ),
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


def test_transition_without_gates_is_fail_closed() -> None:
    """V2.32.1 (auditoría): ``gates=()`` (el default de la firma) NO autoriza el salto.

    El mismo tipo de bug que OR-6: un default permisivo. Cero gates evaluados es un
    caso más extremo que NOT_EVALUATED y debe bloquear, no aprobar.
    """
    for state in (
        StrategyLifecycleState.ESTUDIO,
        StrategyLifecycleState.LABORATORIO,
        StrategyLifecycleState.TOP3,
        StrategyLifecycleState.COACH,
        StrategyLifecycleState.FINALISTA,
    ):
        result = can_transition(state=state)
        assert not result.allowed, f"{state} no debe avanzar sin gates"
        assert "gates_no_evaluados" in result.reasons


def test_transition_with_not_evaluated_gate_is_fail_closed() -> None:
    result = can_transition(
        state=StrategyLifecycleState.LABORATORIO,
        gates=(GateResult(gate="backtest", status=GateStatus.NOT_EVALUATED),),
    )
    assert not result.allowed
    assert "backtest" in result.reasons[0]


def test_candidate_carries_data_snapshot_for_reproducibility() -> None:
    cand = StrategyCandidate(
        id="cand-1",
        instrument_id="inst-1",
        strategy_family="sma",
        params={"fast": 20, "slow": 50},
        data_snapshot_id="snap-2026-09-10",
    )
    assert cand.data_snapshot_id == "snap-2026-09-10"


# ── V2.32/A12: Promotion Gate por EVIDENCIA shadow (no por flag) ─────────────────


def test_shadow_policy_passes_with_evidence() -> None:
    policy = ShadowPolicy(min_trades=5, min_return_pct=0.0, max_drawdown_pct=20.0)
    result = policy.evaluate(
        version_id="ver-1",
        trades=8,
        return_pct=3.5,
        max_drawdown_pct=7.0,
        win_rate=0.6,
        bars_used=200,
    )
    assert result.passed
    assert result.reasons == ()
    assert result.bars_used == 200


def test_shadow_policy_fails_closed_without_sample() -> None:
    policy = ShadowPolicy(min_trades=10)
    result = policy.evaluate(version_id="ver-1", trades=2, return_pct=5.0, max_drawdown_pct=1.0)
    assert not result.passed
    assert "shadow_muestra_insuficiente" in result.reasons


def test_shadow_policy_fails_closed_when_drawdown_missing() -> None:
    """V2.32.1 (P2-01): con techo configurado, métrica ausente NO es "sin riesgo"."""
    policy = ShadowPolicy(min_closed_round_trips=1, max_drawdown_pct=15.0)
    result = policy.evaluate(
        version_id="ver-1", trades=4, round_trips=2, return_pct=5.0, max_drawdown_pct=None
    )
    assert not result.passed
    assert "shadow_drawdown_ausente" in result.reasons


def test_shadow_policy_round_trips_is_the_sample_guard() -> None:
    """V2.32.1 (P2-04): la guarda de muestra cuenta round-trips cerrados, no piernas."""
    policy = ShadowPolicy(min_closed_round_trips=3, min_return_pct=-100.0)
    # 8 piernas ejecutadas pero solo 2 operaciones cerradas ⇒ muestra insuficiente.
    result = policy.evaluate(
        version_id="ver-1", trades=8, round_trips=2, return_pct=1.0, max_drawdown_pct=1.0
    )
    assert not result.passed
    assert "shadow_muestra_insuficiente" in result.reasons
    assert result.round_trips == 2


def test_promotion_requires_shadow_evidence_not_flag() -> None:
    """Sin evidencia shadow (``shadow=None``, flag None) NO promociona."""
    validation = StrategyValidation(finalist_id="ver-1", gates=_all_gates_pass())
    promo = evaluate_promotion(
        finalist=_finalist(),
        validation=validation,
        coach=_coach_approves(),
        shadow=None,
        shadow_validated=None,
    )
    assert not promo.promoted
    assert "shadow_validation_requerida" in promo.reasons


def test_promotion_with_failed_evidence_does_not_promote() -> None:
    validation = StrategyValidation(finalist_id="ver-1", gates=_all_gates_pass())
    failed = ShadowPolicy(min_trades=10).evaluate(
        version_id="ver-1", trades=1, return_pct=-2.0, max_drawdown_pct=9.0
    )
    promo = evaluate_promotion(
        finalist=_finalist(),
        validation=validation,
        coach=_coach_approves(),
        shadow=failed,
    )
    assert not promo.promoted
    assert "shadow_validation_requerida" in promo.reasons


def test_promotion_with_passing_evidence_links_validation_id() -> None:
    validation = StrategyValidation(finalist_id="ver-1", gates=_all_gates_pass())
    evidence = ShadowPolicy(min_trades=1, min_return_pct=-100.0).evaluate(
        version_id="ver-1", trades=6, return_pct=4.0, max_drawdown_pct=3.0
    )
    promo = evaluate_promotion(
        finalist=_finalist(),
        validation=validation,
        coach=_coach_approves(),
        shadow=evidence,
    )
    assert promo.promoted
    assert promo.shadow_validated is True
    assert promo.shadow_validation_id == "ver-1"


# ── V2.33/A13: validación FORWARD (paper, mercado nuevo post-promoción) ──────────


def test_paper_forward_policy_passes_with_evidence() -> None:
    policy = PaperForwardPolicy(min_closed_round_trips=3, min_bars=10, min_return_pct=0.0)
    result = policy.evaluate(
        version_id="ver-1",
        trades=8,
        round_trips=4,
        return_pct=2.5,
        max_drawdown_pct=4.0,
        bars_used=60,
        fills=4,
    )
    assert result.passed
    assert result.reasons == ()
    assert result.round_trips == 4
    assert result.fills == 4


def test_paper_forward_fails_closed_without_bars() -> None:
    """Sin ventana forward suficiente no hay evidencia interpretable."""
    policy = PaperForwardPolicy(min_closed_round_trips=1, min_bars=20, min_return_pct=-100.0)
    result = policy.evaluate(
        version_id="ver-1",
        trades=5,
        round_trips=3,
        return_pct=9.0,
        max_drawdown_pct=1.0,
        bars_used=5,
    )
    assert not result.passed
    assert "forward_barras_insuficientes" in result.reasons


def test_paper_forward_fails_closed_without_sample() -> None:
    policy = PaperForwardPolicy(min_closed_round_trips=10, min_bars=5, min_return_pct=-100.0)
    result = policy.evaluate(
        version_id="ver-1",
        trades=4,
        round_trips=2,
        return_pct=5.0,
        max_drawdown_pct=1.0,
        bars_used=40,
    )
    assert not result.passed
    assert "forward_muestra_insuficiente" in result.reasons


def test_paper_forward_fails_closed_when_drawdown_missing() -> None:
    """Con techo de DD configurado, métrica ausente NO es 'sin riesgo'."""
    policy = PaperForwardPolicy(
        min_closed_round_trips=1, min_bars=5, min_return_pct=-100.0, max_drawdown_pct=15.0
    )
    result = policy.evaluate(
        version_id="ver-1",
        trades=4,
        round_trips=2,
        return_pct=5.0,
        max_drawdown_pct=None,
        bars_used=40,
    )
    assert not result.passed
    assert "forward_drawdown_ausente" in result.reasons


def test_paper_forward_result_carries_reproducible_fingerprint() -> None:
    """La evidencia forward debe poder reproducirse: barras, hash y versión de motor."""
    policy = PaperForwardPolicy(min_closed_round_trips=1, min_bars=1, min_return_pct=-100.0)
    result = policy.evaluate(
        version_id="ver-1",
        trades=4,
        round_trips=2,
        return_pct=3.0,
        max_drawdown_pct=2.0,
        bars_used=30,
        forward_start="2026-09-12T00:00:00",
        forward_end="2026-09-30T00:00:00",
        bars_hash="abc123",
        strategy_definition_hash="hash-1",
        engine_version="paper-forward/2.33.0",
        config_hash="cfg-1",
        data_snapshot_id="snap-1",
        promoted_at="2026-09-11T00:00:00",
    )
    assert result.passed
    assert result.forward_start == "2026-09-12T00:00:00"
    assert result.forward_end == "2026-09-30T00:00:00"
    assert result.bars_hash == "abc123"
    assert result.engine_version == "paper-forward/2.33.0"
    assert result.promoted_at == "2026-09-11T00:00:00"


def test_paper_forward_result_records_vetoes() -> None:
    """Un veto del gate no es un fallo de la política, pero queda auditado."""
    policy = PaperForwardPolicy(min_closed_round_trips=0, min_bars=1, min_return_pct=None)
    result = policy.evaluate(
        version_id="ver-1",
        trades=0,
        round_trips=0,
        return_pct=None,
        max_drawdown_pct=None,
        bars_used=5,
        vetoes=("risk_gate:concentracion",),
    )
    assert result.passed
    assert result.vetoes == ("risk_gate:concentracion",)
