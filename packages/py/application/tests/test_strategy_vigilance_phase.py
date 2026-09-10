"""V2.25 / A10 — vigilancia de la estrategia activa (tests herméticos)."""

from __future__ import annotations

from bolsa_application.strategy_vigilance_phase import (
    DECISION_CONTINUE,
    DECISION_RELAB,
    HealthThresholds,
    evaluate_active_health,
)
from bolsa_domain.entities.strategy_lifecycle import StrategyLifecycleState

_TH = HealthThresholds(min_edge=0.2, min_wfe=0.5, min_dsr=0.0, min_credibility=0.3)


def test_healthy_active_continues() -> None:
    decision = evaluate_active_health(
        version_id="ver-1",
        as_of="2026-09-10",
        metrics={"edge": 0.5, "walk_forward_efficiency": 0.8, "dsr": 0.4, "credibility": 0.9},
        thresholds=_TH,
    )
    assert decision.decision == DECISION_CONTINUE
    assert not decision.degraded
    assert not decision.relab
    assert decision.target_state is None


def test_degraded_active_triggers_relab() -> None:
    decision = evaluate_active_health(
        version_id="ver-1",
        as_of="2026-09-10",
        metrics={"edge": 0.05, "walk_forward_efficiency": 0.8},
        thresholds=_TH,
    )
    assert decision.decision == DECISION_RELAB
    assert decision.degraded
    assert decision.relab
    assert "edge" in decision.breaches
    # La degradación vuelve al LAB, nunca a un swap directo de la activa.
    assert decision.target_state == StrategyLifecycleState.DEGRADED


def test_multiple_breaches_reported() -> None:
    decision = evaluate_active_health(
        version_id="ver-1",
        as_of="2026-09-10",
        metrics={"edge": 0.0, "wfe": 0.1, "credibility": 0.1},
        thresholds=_TH,
    )
    assert set(decision.breaches) == {"edge", "walk_forward_efficiency", "credibility"}


def test_missing_metrics_do_not_invent_degradation() -> None:
    decision = evaluate_active_health(
        version_id="ver-1",
        as_of="2026-09-10",
        metrics={},
        thresholds=_TH,
    )
    assert not decision.degraded
    assert decision.health is not None
    assert decision.health.edge is None


def test_health_snapshot_carries_thresholds() -> None:
    decision = evaluate_active_health(
        version_id="ver-1",
        as_of="2026-09-10",
        metrics={"edge": 0.5},
        thresholds=_TH,
    )
    assert decision.health is not None
    assert decision.health.thresholds["edge"] == 0.2
    assert not decision.health.degraded
