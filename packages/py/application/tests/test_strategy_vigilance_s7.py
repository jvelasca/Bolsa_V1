"""S7 — la vigilancia no confunde una métrica ausente o caducada con salud.

Cubre las dos mitades del hallazgo S7 (auditoría .183):

* **ausencia de medida**: ``unmeasured`` se declara siempre y ``fail_on_unmeasured``
  (fail-closed por defecto) la convierte en degradación; el bloque observado queda
  fuera del endurecimiento porque su ausencia es «aún no hay muestra»;
* **frescura**: la evidencia predictiva declara su fecha y su versión; con TTL
  (``max_metric_age_days``) una evidencia vieja, sin fecha o de otra versión degrada.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from bolsa_application.strategy_vigilance_phase import (
    EVIDENCE_FOREIGN_VERSION,
    EVIDENCE_STALE,
    EVIDENCE_UNDATED,
    HealthThresholds,
    evaluate_active_health,
)

_NOW = datetime(2026, 11, 5, 9, 0, tzinfo=UTC)


def _metrics(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {"edge": 0.5, "walk_forward_efficiency": 0.7, "dsr": 0.8}
    base.update(overrides)
    return base


def _ttl(days: float = 30.0, **overrides: object) -> HealthThresholds:
    base: dict[str, object] = {
        "min_edge": 0.1,
        "min_wfe": 0.3,
        "min_dsr": 0.5,
        "max_metric_age_days": days,
    }
    base.update(overrides)
    return HealthThresholds(**base)  # type: ignore[arg-type]


# ── Ausencia de medida ───────────────────────────────────────────────────────────


def test_missing_metric_degrades_by_default() -> None:
    decision = evaluate_active_health(
        version_id="v1",
        as_of="2026-11-04",
        metrics={},
        thresholds=HealthThresholds(min_edge=0.1, min_dsr=0.5),
    )
    assert decision.degraded and decision.relab  # fail-closed por defecto
    assert decision.unmeasured == ("edge", "dsr")
    assert decision.breaches == ("edge_unmeasured", "dsr_unmeasured")
    assert decision.health_state == "degraded"


def test_missing_metric_is_declared_when_fail_closed_is_off() -> None:
    decision = evaluate_active_health(
        version_id="v1",
        as_of="2026-11-04",
        metrics={},
        thresholds=HealthThresholds(min_edge=0.1, min_dsr=0.5, fail_on_unmeasured=False),
    )
    assert not decision.degraded
    assert decision.unmeasured == ("edge", "dsr")
    assert decision.health_state == "unmeasured"


def test_observed_absence_never_degrades_by_unmeasured() -> None:
    """El observado ausente es «sin muestra» (lo gobierna ``min_observed_trades``)."""
    decision = evaluate_active_health(
        version_id="v1",
        as_of="2026-11-04",
        metrics={},
        thresholds=HealthThresholds(
            min_observed_return_pct=0.0, min_observed_win_rate=0.4
        ),
    )
    assert not decision.degraded
    assert decision.unmeasured == ("observed_return_pct", "observed_win_rate")
    # Se declara (no es salud) pero no degrada: castigar por no haber operado aún sería
    # confundir falta de muestra con pérdida de edge.
    assert decision.health_state == "unmeasured"


def test_all_measured_is_healthy() -> None:
    decision = evaluate_active_health(
        version_id="v1",
        as_of="2026-11-04",
        metrics={"edge": 0.5},
        thresholds=HealthThresholds(min_edge=0.1, fail_on_unmeasured=True),
    )
    assert decision.health_state == "healthy"


def test_lab_robust_score_counts_as_edge() -> None:
    """El LAB publica el edge como ``robust_score``: sin alias quedaría «sin medir»."""
    decision = evaluate_active_health(
        version_id="v1",
        as_of="2026-11-04",
        metrics={"robust_score": 0.4},
        thresholds=HealthThresholds(min_edge=0.1),
    )
    assert decision.health is not None
    assert decision.health.edge == 0.4
    assert decision.health_state == "healthy"


def test_lab_robust_score_below_threshold_degrades() -> None:
    decision = evaluate_active_health(
        version_id="v1",
        as_of="2026-11-04",
        metrics={"robust_score": 0.05},
        thresholds=HealthThresholds(min_edge=0.1),
    )
    assert decision.degraded
    assert "edge" in decision.breaches


# ── Frescura (TTL) ───────────────────────────────────────────────────────────────


def test_fresh_evidence_continues_and_reports_age() -> None:
    decision = evaluate_active_health(
        version_id="v1",
        as_of="2026-11-04",
        metrics=_metrics(),
        thresholds=_ttl(days=30.0),
        metrics_as_of=(_NOW - timedelta(days=3)).isoformat(),
        now=_NOW,
    )
    assert not decision.degraded
    assert decision.stale == ()
    assert decision.metrics_age_days == 3.0
    assert decision.health_state == "healthy"


def test_expired_evidence_degrades_and_triggers_relab() -> None:
    decision = evaluate_active_health(
        version_id="v1",
        as_of="2026-11-04",
        metrics=_metrics(),
        thresholds=_ttl(days=30.0),
        metrics_as_of=(_NOW - timedelta(days=45)).isoformat(),
        now=_NOW,
    )
    assert decision.degraded and decision.relab
    assert decision.stale == (EVIDENCE_STALE,)
    assert decision.breaches == (EVIDENCE_STALE,)
    assert decision.metrics_age_days == 45.0
    assert decision.health_state == "degraded"


def test_expired_evidence_can_be_declared_without_degrading() -> None:
    decision = evaluate_active_health(
        version_id="v1",
        as_of="2026-11-04",
        metrics=_metrics(),
        thresholds=_ttl(days=30.0, fail_on_stale=False),
        metrics_as_of=(_NOW - timedelta(days=45)).isoformat(),
        now=_NOW,
    )
    assert not decision.degraded
    assert decision.stale == (EVIDENCE_STALE,)
    assert decision.health_state == "stale"


def test_undated_evidence_with_ttl_is_not_assumed_fresh() -> None:
    decision = evaluate_active_health(
        version_id="v1",
        as_of="2026-11-04",
        metrics=_metrics(),
        thresholds=_ttl(days=30.0),
        now=_NOW,
    )
    assert decision.degraded
    assert decision.stale == (EVIDENCE_UNDATED,)
    assert decision.metrics_age_days is None


def test_no_ttl_keeps_legacy_route() -> None:
    """Sin TTL configurado no hay política de caducidad (la edad no se declara)."""
    decision = evaluate_active_health(
        version_id="v1",
        as_of="2026-11-04",
        metrics=_metrics(),
        thresholds=_ttl(days=30.0, max_metric_age_days=None),
        now=_NOW,
    )
    assert not decision.degraded
    assert decision.stale == ()
    assert decision.metrics_age_days is None


def test_evidence_from_another_version_is_stale_without_ttl() -> None:
    """La identidad no depende del TTL: una métrica de otra versión no describe la activa."""
    decision = evaluate_active_health(
        version_id="v1",
        as_of="2026-11-04",
        metrics=_metrics(),
        thresholds=HealthThresholds(min_edge=0.1),
        metrics_version_id="v-otra",
    )
    assert decision.degraded
    assert decision.stale == (EVIDENCE_FOREIGN_VERSION,)


def test_declared_version_matching_is_healthy() -> None:
    decision = evaluate_active_health(
        version_id="v1",
        as_of="2026-11-04",
        metrics=_metrics(),
        thresholds=HealthThresholds(min_edge=0.1),
        metrics_version_id="v1",
    )
    assert decision.stale == ()
    assert not decision.degraded


def test_metrics_dict_can_declare_its_own_timestamp_and_version() -> None:
    """El contrato admite que la evidencia viaje con su fecha/versión en el propio dict."""
    decision = evaluate_active_health(
        version_id="v1",
        as_of="2026-11-04",
        metrics=_metrics(
            metrics_as_of="20260901T090000Z",
            metrics_version_id="v1",
        ),
        thresholds=_ttl(days=30.0),
        now=_NOW,
    )
    assert decision.degraded
    assert decision.stale == (EVIDENCE_STALE,)
    # ``20260901T090000Z`` (formato de la traza del AUTO) ⇒ 65 días.
    assert decision.metrics_age_days == 65.0


def test_timestamp_forms_are_parsed_consistently() -> None:
    """ISO con zona, ISO naive (UTC) y el formato compacto de la traza del AUTO."""
    expected_days = 3.0
    naive = (_NOW - timedelta(days=3)).replace(tzinfo=None).isoformat()
    for raw in (
        (_NOW - timedelta(days=3)).isoformat(),
        naive,
        (_NOW - timedelta(days=3)).strftime("%Y%m%dT%H%M%SZ"),
        (_NOW - timedelta(days=3)).strftime("%Y%m%dT%H%M%SZ") + "-abcd1234",
    ):
        decision = evaluate_active_health(
            version_id="v1",
            as_of="2026-11-04",
            metrics=_metrics(),
            thresholds=_ttl(days=30.0),
            metrics_as_of=raw,
            now=_NOW,
        )
        assert decision.metrics_age_days == expected_days, raw
        assert not decision.degraded, raw


def test_unparsable_timestamp_is_undated() -> None:
    decision = evaluate_active_health(
        version_id="v1",
        as_of="2026-11-04",
        metrics=_metrics(),
        thresholds=_ttl(days=30.0),
        metrics_as_of="no-es-una-fecha",
        now=_NOW,
    )
    assert decision.stale == (EVIDENCE_UNDATED,)
