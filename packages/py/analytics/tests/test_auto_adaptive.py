"""AUTO-8 — tests de la recomendación Adaptive pura (rotación + asignación).

Se verifica lo que hace útil al módulo: que la rotación pausa SOLO con evidencia (salud
probadamente negativa o muestra no confiable en régimen adverso), que la asignación
estrecha (multiplicador en ``[0, 1]``) y nunca ensancha, y que el fallback uniforme es el
comportamiento por defecto cuando nadie tiene expectancy positiva decisoria.

La disciplina de medición es el punto: una estrategia SIN muestra no es "mala", es
desconocida, y el desconocido NO se pausa.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from bolsa_analytics.cognitive.auto_adaptive import (
    ADAPTIVE_STRATEGY_PAUSED,
    ADAPTIVE_STRATEGY_REGIME_RISK,
    ADAPTIVE_STRATEGY_UNHEALTHY,
    build_adaptive_plan,
    build_strategy_health,
    recommend_allocation,
    recommend_rotation,
)
from bolsa_analytics.cognitive.auto_self_evaluation import StrategySelfEvaluation
from bolsa_analytics.cognitive.measurement import (
    MEASUREMENT_COMPLETE,
    MEASUREMENT_UNKNOWN,
)


def _row(
    version: str,
    *,
    decisive: bool = False,
    expectancy: str | None = None,
    profit_factor: float | None = None,
    win_rate: float | None = None,
    trades: int = 0,
) -> StrategySelfEvaluation:
    """Fila de self-evaluation mínima con SOLO lo que Adaptive lee (el resto, ausente)."""
    return StrategySelfEvaluation(
        strategy_version=version,
        trades=trades,
        wins=0,
        losses=0,
        realized_pnl=Decimal("0"),
        expectancy_currency=Decimal(expectancy) if expectancy is not None else None,
        expectancy_r=None,
        win_rate=win_rate,
        profit_factor=profit_factor,
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
        excursions_measurement=MEASUREMENT_UNKNOWN,
        slippage_measurement=MEASUREMENT_UNKNOWN,
        rejection_cost_measurement=MEASUREMENT_UNKNOWN,
        drawdown_measurement=MEASUREMENT_UNKNOWN,
        decisive=decisive,
        notes=(),
    )


# ── build_strategy_health ─────────────────────────────────────────────────────────


def test_build_strategy_health_projects_only_adaptive_fields() -> None:
    rows = (_row("v1", decisive=True, expectancy="3"), _row("v2", decisive=False))
    health = build_strategy_health(rows)
    assert len(health) == 2
    assert health[0].strategy_version == "v1"
    assert health[0].decisive is True
    assert health[0].expectancy_currency == Decimal("3")
    assert health[1].strategy_version == "v2"
    assert health[1].decisive is False


# ── recommend_rotation ───────────────────────────────────────────────────────────


def test_rotation_pauses_decisive_negative_expectancy() -> None:
    plan = recommend_rotation((_row("v1", decisive=True, expectancy="-1"),), "TREND_UP")
    assert plan.is_paused("v1")
    assert plan.reason_for("v1") == ADAPTIVE_STRATEGY_UNHEALTHY


def test_rotation_pauses_decisive_profit_factor_below_one() -> None:
    plan = recommend_rotation(
        (_row("v1", decisive=True, expectancy="1", profit_factor=0.5),), "TREND_UP"
    )
    assert plan.is_paused("v1")
    assert plan.reason_for("v1") == ADAPTIVE_STRATEGY_UNHEALTHY


def test_rotation_keeps_decisive_positive() -> None:
    plan = recommend_rotation(
        (_row("v1", decisive=True, expectancy="2", profit_factor=1.5),), "TREND_UP"
    )
    assert not plan.is_paused("v1")


def test_rotation_pauses_thin_sample_in_adverse_regime() -> None:
    plan = recommend_rotation(
        (_row("v1", decisive=False, win_rate=0.2),), "TREND_DOWN"
    )
    assert plan.is_paused("v1")
    assert plan.reason_for("v1") == ADAPTIVE_STRATEGY_REGIME_RISK


def test_rotation_does_not_pause_thin_sample_in_benign_regime() -> None:
    for regime in ("TREND_UP", "LOW_VOL", "RANGE", "UNKNOWN"):
        plan = recommend_rotation((_row("v1", decisive=False, win_rate=0.2),), regime)
        assert not plan.is_paused("v1"), f"no debe pausarse en {regime}"


def test_rotation_does_not_pause_thin_sample_good_win_rate_in_adverse() -> None:
    plan = recommend_rotation(
        (_row("v1", decisive=False, win_rate=0.6),), "HIGH_VOL"
    )
    assert not plan.is_paused("v1")


def test_rotation_unknown_strategy_is_never_paused() -> None:
    """Sin muestra (expectancy/win_rate ausentes) no hay evidencia ⇒ no se pausa a ciegas."""
    plan = recommend_rotation((_row("v1", decisive=False),), "TREND_DOWN")
    assert not plan.is_paused("v1")


def test_rotation_unknown_version_is_not_paused() -> None:
    plan = recommend_rotation((_row("v1", decisive=False),), "TREND_UP")
    assert not plan.is_paused("v999")  # versión no observada ⇒ no hay decisión sobre ella


# ── recommend_allocation ─────────────────────────────────────────────────────────


def test_allocation_uniform_when_no_decisive_positive() -> None:
    rows = (_row("a", decisive=False), _row("b", decisive=False))
    plan = recommend_allocation(["a", "b"], rows)
    # reparto uniforme 1/n ⇒ multiplicador 1.0 para ambas (sin estrechamiento).
    assert plan.multiplier_for("a") == pytest.approx(1.0)
    assert plan.multiplier_for("b") == pytest.approx(1.0)


def test_allocation_proportional_to_positive_expectancy() -> None:
    rows = (
        _row("a", decisive=True, expectancy="3"),
        _row("b", decisive=True, expectancy="1"),
    )
    plan = recommend_allocation(["a", "b"], rows)
    # shares: a = 3/4, b = 1/4 ⇒ multiplicadores share*2 = 1.5→1.0 y 0.5.
    assert plan.multiplier_for("a") == pytest.approx(1.0)
    assert plan.multiplier_for("b") == pytest.approx(0.5)


def test_allocation_multipliers_are_monotonic_and_bounded() -> None:
    """Todo multiplicador vive en [0, 1]: la asignación solo estrecha, nunca ensancha."""
    rows = (
        _row("a", decisive=True, expectancy="5"),
        _row("b", decisive=True, expectancy="1"),
        _row("c", decisive=False),
    )
    plan = recommend_allocation(["a", "b", "c"], rows)
    assert plan.multiplier_for("a") == pytest.approx(1.0)
    assert 0.0 <= plan.multiplier_for("b") <= 1.0
    assert plan.multiplier_for("c") == pytest.approx(0.0)  # sin expectancy positiva ⇒ 0


def test_allocation_unknown_version_defaults_to_no_narrowing() -> None:
    plan = recommend_allocation(["a"], (_row("a", decisive=False),))
    assert plan.multiplier_for("v999") == pytest.approx(1.0)


def test_allocation_empty_active_set_is_empty() -> None:
    plan = recommend_allocation([], (_row("a", decisive=False),))
    assert plan.multipliers == {}


# ── build_adaptive_plan ──────────────────────────────────────────────────────────


def test_build_adaptive_plan_combines_rotation_and_allocation() -> None:
    rows = (
        _row("bad", decisive=True, expectancy="-2"),
        _row("good", decisive=True, expectancy="3"),
    )
    plan = build_adaptive_plan(rows, "TREND_UP")
    assert plan.is_paused("bad")
    assert not plan.is_paused("good")
    # "bad" pausada ⇒ "good" es la única activa ⇒ su multiplicador es 1.0.
    assert plan.risk_multiplier_for("good") == pytest.approx(1.0)
    assert plan.regime == "TREND_UP"
    assert plan.read_only is True


def test_build_adaptive_plan_as_dict_is_read_only_and_keyed() -> None:
    plan = build_adaptive_plan((_row("v1", decisive=False),), "LOW_VOL")
    payload = plan.as_dict()
    assert payload["key"] == "adaptive"
    assert payload["readOnly"] is True
    assert payload["regime"] == "LOW_VOL"
    assert payload["rotation"]["paused"] == []
    assert payload["allocation"]["riskMultipliers"] == {"v1": 1.0}


def test_rotation_plan_exports_pause_reason_code_vocabulary() -> None:
    """Los motivos de pausa son los literales que el journal consume en el detalle."""
    plan = recommend_rotation((_row("v1", decisive=True, expectancy="-1"),), "TREND_UP")
    assert plan.reason_for("v1") == ADAPTIVE_STRATEGY_UNHEALTHY
    # El literal de no-trade observable (journal) es otro; el de pausa viaja en detalle.
    assert ADAPTIVE_STRATEGY_PAUSED == "adaptive_strategy_paused"
