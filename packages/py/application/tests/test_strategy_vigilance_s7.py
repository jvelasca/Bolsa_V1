"""S7 — la vigilancia no confunde una métrica ausente con salud."""

from __future__ import annotations

from bolsa_application.strategy_vigilance_phase import HealthThresholds, evaluate_active_health


def test_missing_metric_is_declared_unmeasured_not_healthy() -> None:
    decision = evaluate_active_health(
        version_id="v1",
        as_of="2026-11-04",
        metrics={},
        thresholds=HealthThresholds(min_edge=0.1, min_dsr=0.5),
    )
    assert not decision.degraded  # comportamiento histórico (flag OFF)
    assert decision.unmeasured == ("edge", "dsr")
    assert decision.health_state == "unmeasured"


def test_fail_on_unmeasured_degrades() -> None:
    decision = evaluate_active_health(
        version_id="v1",
        as_of="2026-11-04",
        metrics={"edge": 0.5},
        thresholds=HealthThresholds(min_edge=0.1, min_dsr=0.5, fail_on_unmeasured=True),
    )
    assert decision.degraded and decision.relab
    assert decision.breaches == ("dsr_unmeasured",)
    assert decision.health_state == "degraded"


def test_all_measured_is_healthy() -> None:
    decision = evaluate_active_health(
        version_id="v1",
        as_of="2026-11-04",
        metrics={"edge": 0.5},
        thresholds=HealthThresholds(min_edge=0.1, fail_on_unmeasured=True),
    )
    assert decision.health_state == "healthy"
