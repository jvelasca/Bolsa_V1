"""V2.25 / A10 — fase FINALISTA + Promotion Gate (tests herméticos).

Certifica la inmutabilidad de la versión (hash estable) y la regla anti
strategy-chasing: sin evidencia shadow o con un gate FAIL, la activa NO se sustituye.

V2.35.1 (auditoría P2-01): la compuerta AUTOMÁTICA (``decide_promotion``) no acepta
override humano; la ADMIN (``decide_admin_promotion``) es la única vía con
``shadow_validated``.
"""

from __future__ import annotations

import inspect

from bolsa_application.strategy_promotion_phase import (
    ActiveStrategyRef,
    build_strategy_version,
    decide_admin_promotion,
    decide_promotion,
    definition_hash,
)
from bolsa_domain.entities.strategy_lifecycle import (
    PROMOTION_GATES,
    CoachAssessment,
    GateResult,
    ShadowPolicy,
    StrategyCandidate,
)


def _candidate() -> StrategyCandidate:
    return StrategyCandidate(
        id="cand-1",
        instrument_id="AAA",
        strategy_family="sma_crossover",
        params={"fast": 20, "slow": 50},
        data_snapshot_id="snap-1",
    )


def _all_pass() -> tuple[GateResult, ...]:
    return tuple(GateResult.passed_gate(g) for g in PROMOTION_GATES)


def _coach_ok() -> CoachAssessment:
    return CoachAssessment(candidate_id="cand-1", approved=True)


def _passing_shadow(version_id: str = "ver-cand-1") -> object:
    """Evidencia shadow ejecutada que pasa la política (fail-closed satisfecho)."""
    return ShadowPolicy(min_closed_round_trips=1, min_return_pct=-100.0).evaluate(
        version_id=version_id,
        trades=4,
        round_trips=2,
        return_pct=3.0,
        max_drawdown_pct=2.0,
    )


# ── Inmutabilidad de la versión ──────────────────────────────────────────────────


def test_definition_hash_is_order_insensitive_and_stable() -> None:
    a = definition_hash({"a": 1, "b": [2, 3]})
    b = definition_hash({"b": [2, 3], "a": 1})
    assert a == b


def test_version_id_is_deterministic_and_carries_snapshot() -> None:
    v1 = build_strategy_version(candidate=_candidate(), name="SMA-20/50")
    v2 = build_strategy_version(candidate=_candidate(), name="SMA-20/50")
    assert v1.version_id == v2.version_id
    assert v1.definition_hash == v2.definition_hash
    assert v1.definition["data_snapshot_id"] == "snap-1"


def test_version_id_changes_with_definition() -> None:
    v1 = build_strategy_version(candidate=_candidate(), name="x")
    other = StrategyCandidate(
        id="cand-1",
        instrument_id="AAA",
        strategy_family="sma_crossover",
        params={"fast": 10, "slow": 30},
    )
    v2 = build_strategy_version(candidate=other, name="x")
    assert v1.version_id != v2.version_id


# ── Promotion Gate ──────────────────────────────────────────────────────────────


def test_automatic_gate_has_no_override_parameter() -> None:
    """V2.35.1 (P2-01): la compuerta AUTOMÁTICA no acepta override humano."""
    params = inspect.signature(decide_promotion).parameters
    assert "shadow_validated" not in params
    assert "shadow_override" not in params


def test_admin_gate_is_the_only_one_with_override() -> None:
    """La compuerta ADMIN es la única con ``shadow_validated``."""
    assert "shadow_validated" in inspect.signature(decide_admin_promotion).parameters


def test_promotion_happy_path_with_shadow() -> None:
    finalist = build_strategy_version(candidate=_candidate(), name="SMA-20/50")
    decision = decide_promotion(
        finalist=finalist,
        gates=_all_pass(),
        coach=_coach_ok(),
        shadow=_passing_shadow(finalist.version_id),
    )
    assert decision.promoted
    assert decision.reasons == ()


def test_automatic_gate_cannot_promote_without_evidence() -> None:
    """Fail-closed: sin evidencia ejecutada, la compuerta automática NO promociona."""
    finalist = build_strategy_version(candidate=_candidate(), name="SMA-20/50")
    decision = decide_promotion(
        finalist=finalist,
        gates=_all_pass(),
        coach=_coach_ok(),
        shadow=None,
    )
    assert not decision.promoted
    assert "shadow_validation_requerida" in decision.reasons


def test_admin_gate_promotes_via_explicit_override() -> None:
    """La compuerta ADMIN puede promocionar con el override explícito (única vía)."""
    finalist = build_strategy_version(candidate=_candidate(), name="SMA-20/50")
    decision = decide_admin_promotion(
        finalist=finalist,
        gates=_all_pass(),
        coach=_coach_ok(),
        shadow_validated=True,
    )
    assert decision.promoted
    assert decision.promotion.shadow_validated is True
    assert decision.promotion.shadow_validation_id == finalist.version_id


def test_admin_gate_denied_override_does_not_promote() -> None:
    """Un override explícito ``False`` es fail-closed: no promociona."""
    finalist = build_strategy_version(candidate=_candidate(), name="SMA-20/50")
    decision = decide_admin_promotion(
        finalist=finalist,
        gates=_all_pass(),
        coach=_coach_ok(),
        shadow_validated=False,
    )
    assert not decision.promoted
    assert "shadow_validation_requerida" in decision.reasons


def test_promotion_without_shadow_is_blocked() -> None:
    finalist = build_strategy_version(candidate=_candidate(), name="SMA-20/50")
    decision = decide_admin_promotion(
        finalist=finalist,
        gates=_all_pass(),
        coach=_coach_ok(),
        shadow_validated=False,
    )
    assert not decision.promoted
    assert "shadow_validation_requerida" in decision.reasons


def test_promotion_with_failed_gate_is_blocked() -> None:
    finalist = build_strategy_version(candidate=_candidate(), name="SMA-20/50")
    gates = tuple(
        GateResult.passed_gate(g) if g != "oos" else GateResult.failed("oos")
        for g in PROMOTION_GATES
    )
    decision = decide_admin_promotion(
        finalist=finalist,
        gates=gates,
        coach=_coach_ok(),
        shadow_validated=True,
    )
    assert not decision.promoted
    assert any("gates_no_superados" in r for r in decision.reasons)


def test_cannot_replace_active_without_gate() -> None:
    """Anti strategy-chasing: la activa no se sustituye sin shadow (gate falla)."""
    finalist = build_strategy_version(candidate=_candidate(), name="SMA-20/50")
    active = ActiveStrategyRef(version_id="ver-old", candidate_id="cand-0", instrument_id="AAA")
    decision = decide_admin_promotion(
        finalist=finalist,
        gates=_all_pass(),
        coach=_coach_ok(),
        shadow_validated=False,
        active=active,
    )
    assert not decision.promoted
    assert decision.replaces is None


def test_replace_active_when_gate_passes() -> None:
    finalist = build_strategy_version(candidate=_candidate(), name="SMA-20/50")
    active = ActiveStrategyRef(version_id="ver-old", candidate_id="cand-0", instrument_id="AAA")
    decision = decide_admin_promotion(
        finalist=finalist,
        gates=_all_pass(),
        coach=_coach_ok(),
        shadow_validated=True,
        active=active,
    )
    assert decision.promoted
    assert decision.replaces is not None
    assert decision.replaces.version_id == "ver-old"


def test_cannot_re_promote_the_same_active_candidate() -> None:
    finalist = build_strategy_version(candidate=_candidate(), name="SMA-20/50")
    active = ActiveStrategyRef(
        version_id=finalist.version_id, candidate_id="cand-1", instrument_id="AAA"
    )
    decision = decide_admin_promotion(
        finalist=finalist,
        gates=_all_pass(),
        coach=_coach_ok(),
        shadow_validated=True,
        active=active,
    )
    assert not decision.promoted
    assert "ya_activa" in decision.reasons


def test_coach_veto_blocks_against_active_swap() -> None:
    finalist = build_strategy_version(candidate=_candidate(), name="SMA-20/50")
    active = ActiveStrategyRef(version_id="ver-old", candidate_id="cand-0", instrument_id="AAA")
    decision = decide_admin_promotion(
        finalist=finalist,
        gates=_all_pass(),
        coach=CoachAssessment(candidate_id="cand-1", approved=False, contradictions=("regimen",)),
        shadow_validated=True,
        active=active,
    )
    assert not decision.promoted
    assert "coach_veto" in decision.reasons
