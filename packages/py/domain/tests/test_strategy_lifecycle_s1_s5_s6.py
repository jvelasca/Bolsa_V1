"""S1/S5/S6 — la máquina de estados no promociona sin evidencia ni con evidencia ajena."""

from __future__ import annotations

from bolsa_domain.entities.strategy_lifecycle import (
    PROMOTION_GATES,
    CoachAssessment,
    GateResult,
    GateStatus,
    ShadowValidationResult,
    StrategyFinalist,
    StrategyLifecycleState,
    StrategyValidation,
    can_advance_to,
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


def _finalist(
    definition_hash: str = "sha256:abc",
    snapshot: str | None = "snap-1",
) -> StrategyFinalist:
    definition: dict[str, object] = {"family": "sma"}
    if snapshot is not None:
        definition["data_snapshot_id"] = snapshot
    return StrategyFinalist(
        candidate_id="c",
        version_id="ver-1",
        name="n",
        definition_hash=definition_hash,
        definition=definition,
    )


def test_s6_validation_of_another_definition_is_blocked() -> None:
    validation = StrategyValidation(
        finalist_id="ver-1",
        gates=tuple(GateResult.passed_gate(g) for g in PROMOTION_GATES),
        strategy_definition_hash="sha256:OTRA",
    )
    result = can_transition(
        state=_P, validation=validation, shadow=_shadow(), coach=_coach(), finalist=_finalist()
    )
    assert not result.allowed
    assert "evidencia_validacion_otra_definicion" in result.reasons


def test_s6_shadow_of_another_definition_is_blocked() -> None:
    shadow = ShadowValidationResult(
        version_id="ver-1",
        trades=30,
        passed=True,
        strategy_definition_hash="sha256:OTRA",
    )
    result = can_transition(
        state=_P, validation=_validation(), shadow=shadow, coach=_coach(), finalist=_finalist()
    )
    assert not result.allowed
    assert "evidencia_shadow_otra_definicion" in result.reasons


def test_s6_shadow_from_other_dataset_snapshot_is_blocked() -> None:
    validation = StrategyValidation(
        finalist_id="ver-1",
        gates=tuple(GateResult.passed_gate(g) for g in PROMOTION_GATES),
        data_snapshot_id="snap-1",
    )
    shadow = ShadowValidationResult(
        version_id="ver-1", trades=30, passed=True, data_snapshot_id="snap-OTRO"
    )
    result = can_transition(
        state=_P, validation=validation, shadow=shadow, coach=_coach(), finalist=_finalist()
    )
    assert not result.allowed
    assert "evidencia_shadow_otro_dataset" in result.reasons


def test_s6_shadow_replaying_the_lab_bars_is_blocked() -> None:
    """Si el `bars_hash` del shadow es el del tramo LAB, el "hold-out" no era hold-out."""
    validation = StrategyValidation(
        finalist_id="ver-1",
        gates=tuple(GateResult.passed_gate(g) for g in PROMOTION_GATES),
        bars_hash="hash-lab",
    )
    shadow = ShadowValidationResult(
        version_id="ver-1", trades=30, passed=True, bars_hash="hash-lab"
    )
    result = can_transition(
        state=_P, validation=validation, shadow=shadow, coach=_coach(), finalist=_finalist()
    )
    assert not result.allowed
    assert "evidencia_shadow_mismo_dataset" in result.reasons


def test_s6_missing_fingerprints_are_not_invented() -> None:
    """Sin fingerprints declarados no se inventa una contradicción (límite declarado).

    Los finalistas históricos y el override administrativo no los llevan: la ausencia es
    un hueco, no una prueba de que la evidencia sea ajena.
    """
    result = can_transition(
        state=_P, validation=_validation(), shadow=_shadow(), coach=_coach(), finalist=_finalist()
    )
    assert result.allowed


def test_s5_required_gates_must_be_present() -> None:
    gates = (GateResult.passed_gate("backtest"),)
    blocked = can_transition(
        state=StrategyLifecycleState.LABORATORIO, gates=gates, required_gates=("backtest", "oos")
    )
    assert not blocked.allowed
    assert "oos" in blocked.reasons[0]
    # S5: `required_gates` solo AÑADE. La tabla del dominio ya exige `robustness` para
    # entrar en TOP3, así que un llamador no puede rebajar la exigencia a "backtest".
    ok = can_transition(
        state=StrategyLifecycleState.LABORATORIO, gates=gates, required_gates=("backtest",)
    )
    assert not ok.allowed
    assert "robustness" in ok.reasons[0]


def test_s5_state_table_cannot_be_lowered_by_the_caller() -> None:
    """La fase exige los gates de `REQUIRED_GATES_BY_STATE`, no los que elija el llamador."""
    only_backtest = (GateResult.passed_gate("backtest"),)
    for state, needed in (
        (StrategyLifecycleState.TOP3, "robustness"),
        (StrategyLifecycleState.COACH, "robustness"),
        (StrategyLifecycleState.FINALISTA, "oos"),
    ):
        result = can_transition(state=state, gates=only_backtest)
        assert not result.allowed, f"{state} no debe cruzar solo con backtest"
        assert needed in result.reasons[0], result.reasons


def test_s5_not_evaluated_gate_blocks_the_phase() -> None:
    """`NOT_EVALUATED` no es PASS: un gate requerido sin evaluar bloquea la fase."""
    result = can_transition(
        state=StrategyLifecycleState.LABORATORIO,
        gates=(
            GateResult.passed_gate("backtest"),
            GateResult(gate="robustness", status=GateStatus.NOT_EVALUATED),
        ),
    )
    assert not result.allowed
    assert "robustness" in result.reasons[0]


def test_s5_can_advance_to_walks_the_whole_funnel() -> None:
    """Un ciclo real cruza varias fases: se exige la evidencia de TODAS, no de la última."""
    full = tuple(
        GateResult.passed_gate(g) for g in ("backtest", "robustness", "walk_forward", "oos")
    )
    ok = can_advance_to(
        current=StrategyLifecycleState.ESTUDIO,
        target=StrategyLifecycleState.FINALISTA,
        gates=full,
    )
    assert ok.allowed
    assert ok.to_state == StrategyLifecycleState.FINALISTA

    short = tuple(GateResult.passed_gate(g) for g in ("backtest", "robustness"))
    blocked = can_advance_to(
        current=StrategyLifecycleState.ESTUDIO,
        target=StrategyLifecycleState.FINALISTA,
        gates=short,
    )
    assert not blocked.allowed
    assert "walk_forward" in blocked.reasons[0]


def test_s5_can_advance_to_ignores_failures_outside_the_phase_requirement() -> None:
    """Un FAIL en un gate que la fase NO exige no bloquea el avance (alcance declarado).

    ``dsr`` es obligatorio para entrar en PROMOCION, no en FINALISTA: si falla, el
    Promotion Gate no promocionará, pero la fase puede materializar el finalista y correr
    su evidencia shadow. Así el corte de S5 no se confunde con el veredicto completo.
    """
    gates = (
        *(GateResult.passed_gate(g) for g in ("backtest", "robustness", "walk_forward", "oos")),
        GateResult.failed("dsr"),
        GateResult.failed("risk"),
    )
    result = can_advance_to(
        current=StrategyLifecycleState.ESTUDIO,
        target=StrategyLifecycleState.FINALISTA,
        gates=gates,
    )
    assert result.allowed


def test_s5_can_advance_to_refuses_to_decide_the_promotion() -> None:
    """VALIDACION/PROMOCION/ACTIVE los decide `evaluate_promotion`, no esta función."""
    result = can_advance_to(
        current=StrategyLifecycleState.ESTUDIO,
        target=StrategyLifecycleState.ACTIVE,
        gates=tuple(GateResult.passed_gate(g) for g in PROMOTION_GATES),
    )
    assert not result.allowed
    assert "validacion_ausente" in result.reasons
