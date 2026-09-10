"""V2.28 / A10 (P1-02 real) — tests de la vigilancia con métricas OBSERVADAS.

Cubren la semántica acordada:

* retorno/win-rate/profit-factor son umbrales MÍNIMOS (degradan por debajo);
* el drawdown es un TECHO (degrada por encima);
* la guarda de muestra mínima impide que el observado degrade con pocos trades;
* sin evidencia observada no se degrada (no se inventa).
"""

from __future__ import annotations

from bolsa_application.strategy_vigilance_phase import (
    DECISION_CONTINUE,
    DECISION_RELAB,
    HealthThresholds,
    evaluate_active_health,
)


def _observed_thresholds(**overrides: object) -> HealthThresholds:
    base: dict[str, object] = {
        "min_observed_trades": 3,
        "min_observed_return_pct": 0.0,
        "max_observed_drawdown_pct": 20.0,
        "min_observed_win_rate": 0.4,
        "min_observed_profit_factor": 1.0,
    }
    base.update(overrides)
    return HealthThresholds(**base)  # type: ignore[arg-type]


def _metrics(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "observed_return_pct": 5.0,
        "observed_max_drawdown_pct": 10.0,
        "observed_win_rate": 0.6,
        "observed_profit_factor": 1.5,
        "observed_trades": 10,
    }
    base.update(overrides)
    return base


def test_healthy_observed_continues() -> None:
    decision = evaluate_active_health(
        version_id="ver-1",
        as_of="2026-09-10",
        metrics=_metrics(),
        thresholds=_observed_thresholds(),
    )
    assert decision.decision == DECISION_CONTINUE
    assert not decision.degraded
    assert decision.health is not None
    assert decision.health.observed_trades == 10


def test_negative_return_degrades() -> None:
    decision = evaluate_active_health(
        version_id="ver-1",
        as_of="2026-09-10",
        metrics=_metrics(observed_return_pct=-3.0),
        thresholds=_observed_thresholds(),
    )
    assert decision.decision == DECISION_RELAB
    assert "observed_return_pct" in decision.breaches


def test_excessive_drawdown_degrades_above_ceiling() -> None:
    decision = evaluate_active_health(
        version_id="ver-1",
        as_of="2026-09-10",
        metrics=_metrics(observed_max_drawdown_pct=25.0),
        thresholds=_observed_thresholds(),
    )
    assert decision.decision == DECISION_RELAB
    assert "observed_max_drawdown_pct" in decision.breaches


def test_drawdown_below_ceiling_does_not_degrade() -> None:
    decision = evaluate_active_health(
        version_id="ver-1",
        as_of="2026-09-10",
        metrics=_metrics(observed_max_drawdown_pct=19.9),
        thresholds=_observed_thresholds(),
    )
    assert decision.decision == DECISION_CONTINUE


def test_low_win_rate_degrades() -> None:
    decision = evaluate_active_health(
        version_id="ver-1",
        as_of="2026-09-10",
        metrics=_metrics(observed_win_rate=0.2),
        thresholds=_observed_thresholds(),
    )
    assert "observed_win_rate" in decision.breaches


def test_low_profit_factor_degrades() -> None:
    decision = evaluate_active_health(
        version_id="ver-1",
        as_of="2026-09-10",
        metrics=_metrics(observed_profit_factor=0.5),
        thresholds=_observed_thresholds(),
    )
    assert "observed_profit_factor" in decision.breaches


def test_min_trades_guard_prevents_degradation() -> None:
    """Con muestra insuficiente el observado es informativo, no decisorio."""
    decision = evaluate_active_health(
        version_id="ver-1",
        as_of="2026-09-10",
        metrics=_metrics(
            observed_return_pct=-50.0,
            observed_max_drawdown_pct=99.0,
            observed_trades=2,
        ),
        thresholds=_observed_thresholds(min_observed_trades=3),
    )
    assert decision.decision == DECISION_CONTINUE
    assert not decision.degraded


def test_no_observed_metrics_does_not_degrade() -> None:
    decision = evaluate_active_health(
        version_id="ver-1",
        as_of="2026-09-10",
        metrics={},
        thresholds=_observed_thresholds(),
    )
    assert decision.decision == DECISION_CONTINUE
    assert decision.health is not None
    assert decision.health.observed_trades is None


def test_unset_observed_threshold_does_not_apply() -> None:
    """Un umbral observado no configurado no debe degradar por defecto."""
    thresholds = HealthThresholds(min_observed_trades=1)
    decision = evaluate_active_health(
        version_id="ver-1",
        as_of="2026-09-10",
        metrics=_metrics(observed_return_pct=-100.0),
        thresholds=thresholds,
    )
    assert decision.decision == DECISION_CONTINUE
