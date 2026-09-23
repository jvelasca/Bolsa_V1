"""AUTO-8 — tests de la recomendación Adaptive pura (rotación + asignación).

Se verifica lo que hace útil al módulo: que la rotación pausa SOLO con evidencia (salud
probadamente negativa o muestra no confiable en régimen adverso), que la asignación
estrecha (multiplicador en ``[0, 1]``) y nunca ensancha, y que el reparto es uniforme
(neutral) cuando nadie tiene expectancy positiva decisoria.

La disciplina de medición es el punto: una estrategia SIN muestra no es "mala", es
desconocida, y el desconocido NO se pausa ni se castiga con riesgo cero.

AUTO-8.1 añade: gate de decisividad POR FILA en el reparto, materialización explícita de
las versiones sin evidencia (política, no ausencia de clave), hysteresis/cooldown de
rotación y sello de ``policy_version``.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from bolsa_analytics.cognitive.auto_adaptive import (
    ADAPTIVE_CELL_NOTE_AXIS_WITHOUT_CELL,
    ADAPTIVE_CELL_NOTE_NET_UNMEASURED,
    ADAPTIVE_CELL_NOTE_NOT_DECISIVE,
    ADAPTIVE_CELL_NOTE_NOT_FOUND,
    ADAPTIVE_CELL_NOTE_NOT_POSITIVE,
    ADAPTIVE_CELL_NOTE_REGIME_ABSENT,
    ADAPTIVE_CONFIDENCE_PRIOR_DEFAULT,
    ADAPTIVE_POLICY_VERSION,
    ADAPTIVE_RECOVERY_NOTE_NOT_POSITIVE,
    ADAPTIVE_RECOVERY_NOTE_SEVERE,
    ADAPTIVE_RECOVERY_NOTE_UNMEASURED,
    ADAPTIVE_RECOVERY_STEP_CYCLES_DEFAULT,
    ADAPTIVE_RECOVERY_STEPS_DEFAULT,
    ADAPTIVE_REGIME_UNKNOWN,
    ADAPTIVE_SEVERE_DECAY_FACTOR_DEFAULT,
    ADAPTIVE_STATE_ACTIVE,
    ADAPTIVE_STATE_PAUSED,
    ADAPTIVE_STATE_RECOVERING,
    ADAPTIVE_STRATEGY_COOLDOWN,
    ADAPTIVE_STRATEGY_PAUSED,
    ADAPTIVE_STRATEGY_REGIME_RISK,
    ADAPTIVE_STRATEGY_UNHEALTHY,
    ALLOCATION_AXIS_CURRENCY,
    ALLOCATION_AXIS_NET_R,
    AdaptivePolicy,
    RecoveryEvidence,
    StrategyHealth,
    build_adaptive_plan,
    build_strategy_health,
    recommend_allocation,
    recommend_rotation,
    recovery_reading,
    regime_cell_for,
)
from bolsa_analytics.cognitive.auto_adaptive_confidence import (
    ADAPTIVE_DECAY_NONE,
    ADAPTIVE_DECAY_SEVERE,
    ADAPTIVE_LONG_WINDOW_DEFAULT,
    ADAPTIVE_RECENT_WINDOW_DEFAULT,
    AdaptiveConfidence,
    RegimeConfidence,
    StrategyConfidence,
)
from bolsa_analytics.cognitive.auto_self_evaluation import (
    StrategySelfEvaluation,
    aggregate_by_regime,
)
from bolsa_analytics.cognitive.measurement import (
    MEASUREMENT_COMPLETE,
    MEASUREMENT_PARTIAL,
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
    net_expectancy_r: float | None = None,
    net_r_measurement: str = MEASUREMENT_UNKNOWN,
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
        net_expectancy_r=net_expectancy_r,
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
        net_r_measurement=net_r_measurement,
        cycles_without_cost=0,
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
    assert health[0].net_expectancy_r is None  # sin productor: se declara, no se inventa
    assert health[0].regime == "UNKNOWN"
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
    plan = recommend_rotation((_row("v1", decisive=False, win_rate=0.2),), "TREND_DOWN")
    assert plan.is_paused("v1")
    assert plan.reason_for("v1") == ADAPTIVE_STRATEGY_REGIME_RISK


def test_rotation_does_not_pause_thin_sample_in_benign_regime() -> None:
    for regime in ("TREND_UP", "LOW_VOL", "RANGE", "UNKNOWN"):
        plan = recommend_rotation((_row("v1", decisive=False, win_rate=0.2),), regime)
        assert not plan.is_paused("v1"), f"no debe pausarse en {regime}"


def test_rotation_does_not_pause_thin_sample_good_win_rate_in_adverse() -> None:
    plan = recommend_rotation((_row("v1", decisive=False, win_rate=0.6),), "HIGH_VOL")
    assert not plan.is_paused("v1")


def test_rotation_unknown_strategy_is_never_paused() -> None:
    """Sin muestra (expectancy/win_rate ausentes) no hay evidencia ⇒ no se pausa a ciegas."""
    plan = recommend_rotation((_row("v1", decisive=False),), "TREND_DOWN")
    assert not plan.is_paused("v1")


def test_rotation_unknown_version_is_not_paused() -> None:
    plan = recommend_rotation((_row("v1", decisive=False),), "TREND_UP")
    assert not plan.is_paused("v999")  # versión no observada ⇒ no hay decisión sobre ella


def test_rotation_plan_exports_pause_reason_code_vocabulary() -> None:
    """Los motivos de pausa son los literales que el journal consume en el detalle."""
    plan = recommend_rotation((_row("v1", decisive=True, expectancy="-1"),), "TREND_UP")
    assert plan.reason_for("v1") == ADAPTIVE_STRATEGY_UNHEALTHY
    # El literal de no-trade observable (journal) es otro; el de pausa viaja en detalle.
    assert ADAPTIVE_STRATEGY_PAUSED == "adaptive_strategy_paused"


# ── recommend_rotation · hysteresis y cooldown (AUTO-8.1) ────────────────────────


def test_rotation_hysteresis_keeps_pause_inside_profit_factor_dead_zone() -> None:
    """PF 1.05 está por encima del umbral de PAUSA (1.0) pero dentro de la zona muerta."""
    plan = recommend_rotation(
        (_row("v1", decisive=True, expectancy="1", profit_factor=1.05),),
        "TREND_UP",
        paused_cycles={"v1": 5},
    )
    assert plan.is_paused("v1")
    assert plan.reason_for("v1") == ADAPTIVE_STRATEGY_UNHEALTHY


def test_rotation_reactivates_when_metrics_recover_beyond_dead_zone() -> None:
    plan = recommend_rotation(
        (_row("v1", decisive=True, expectancy="1", profit_factor=1.2),),
        "TREND_UP",
        paused_cycles={"v1": 5},
    )
    assert not plan.is_paused("v1")


def test_rotation_cooldown_keeps_pause_before_min_cycles() -> None:
    """Con muestra ya recuperada, la pausa no se levanta antes de ``min_pause_cycles``."""
    policy = AdaptivePolicy(min_pause_cycles=3)
    plan = recommend_rotation(
        (_row("v1", decisive=True, expectancy="2", profit_factor=2.0),),
        "TREND_UP",
        policy=policy,
        paused_cycles={"v1": 1},
    )
    assert plan.is_paused("v1")
    assert plan.reason_for("v1") == ADAPTIVE_STRATEGY_COOLDOWN


def test_rotation_cooldown_expires_and_reactivates() -> None:
    policy = AdaptivePolicy(min_pause_cycles=3)
    plan = recommend_rotation(
        (_row("v1", decisive=True, expectancy="2", profit_factor=2.0),),
        "TREND_UP",
        policy=policy,
        paused_cycles={"v1": 3},
    )
    assert not plan.is_paused("v1")


def test_rotation_regime_hysteresis_dead_zone() -> None:
    """WR 0.40 supera el suelo de pausa (0.35) pero no el de reactivación (0.45)."""
    plan = recommend_rotation(
        (_row("v1", decisive=False, win_rate=0.40),),
        "TREND_DOWN",
        paused_cycles={"v1": 4},
    )
    assert plan.is_paused("v1")
    assert plan.reason_for("v1") == ADAPTIVE_STRATEGY_REGIME_RISK


# ── recommend_allocation ─────────────────────────────────────────────────────────


def test_allocation_uniform_when_no_decisive_positive() -> None:
    rows = (_row("a", decisive=False), _row("b", decisive=False))
    plan = recommend_allocation(["a", "b"], rows)
    # reparto neutral 1/n ⇒ multiplicador 1.0 para ambas (sin estrechamiento).
    assert plan.multiplier_for("a") == pytest.approx(1.0)
    assert plan.multiplier_for("b") == pytest.approx(1.0)
    # Sin ningún peso en juego el eje no puede ser el del R medido: se declara el histórico.
    assert plan.evidence_axis == ALLOCATION_AXIS_CURRENCY
    assert plan.as_dict()["evidenceAxis"] == ALLOCATION_AXIS_CURRENCY


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
    # AUTO-8.1: "c" no tiene evidencia decisoria ⇒ NEUTRAL (política), nunca riesgo 0.
    # La ausencia de muestra no puede leerse como "mala estrategia".
    assert plan.multiplier_for("c") == pytest.approx(1.0)


def test_allocation_non_decisive_positive_does_not_leak_into_reparto() -> None:
    """Una racha favorable SIN muestra decisoria no mueve el reparto de las decisorias."""
    rows = (
        _row("a", decisive=True, expectancy="3"),
        _row("b", decisive=False, expectancy="1"),
    )
    plan = recommend_allocation(["a", "b"], rows)
    assert plan.multiplier_for("a") == pytest.approx(1.0)
    assert plan.multiplier_for("b") == pytest.approx(1.0)  # neutral, no share


def test_allocation_materializes_active_version_without_row() -> None:
    """Una versión activa sin fila de self-evaluation recibe la política, no el default."""
    plan = recommend_allocation(["a", "ghost"], (_row("a", decisive=False),))
    assert plan.multipliers == {"a": 1.0, "ghost": 1.0}


def test_allocation_never_emits_zero_multiplier() -> None:
    rows = (
        _row("a", decisive=True, expectancy="5"),
        _row("b", decisive=True, expectancy="1"),
        _row("c", decisive=False),
        _row("d", decisive=True, expectancy="-2"),
    )
    plan = recommend_allocation(["a", "b", "c", "d"], rows)
    assert all(value > 0.0 for value in plan.multipliers.values())


def test_allocation_unknown_multiplier_is_explicit_policy() -> None:
    policy = AdaptivePolicy(unknown_multiplier=0.5)
    plan = recommend_allocation(["a"], (_row("a", decisive=False),), policy=policy)
    assert plan.multiplier_for("a") == pytest.approx(0.5)


def test_allocation_unknown_version_defaults_to_no_narrowing() -> None:
    plan = recommend_allocation(["a"], (_row("a", decisive=False),))
    assert plan.multiplier_for("v999") == pytest.approx(1.0)


def test_allocation_empty_active_set_is_empty() -> None:
    plan = recommend_allocation([], (_row("a", decisive=False),))
    assert plan.multipliers == {}


# ── recommend_allocation: eje de evidencia (AUTO-9, paso 6) ──────────────────────


def test_allocation_weighs_with_measured_net_r_when_the_pool_measures_it() -> None:
    """El R neto MEDIDO manda sobre la moneda bruta cuando todo el grupo lo mide.

    Moneda bruta 3:1 ⇒ (1.0, 0.5). R neto 2:1 ⇒ (1.0, 2/3): el eje cambia el REPARTO,
    no solo la etiqueta que lo declara.
    """
    rows = (
        _row(
            "a",
            decisive=True,
            expectancy="3",
            net_expectancy_r=2.0,
            net_r_measurement=MEASUREMENT_COMPLETE,
        ),
        _row(
            "b",
            decisive=True,
            expectancy="1",
            net_expectancy_r=1.0,
            net_r_measurement=MEASUREMENT_COMPLETE,
        ),
    )
    plan = recommend_allocation(["a", "b"], rows)
    assert plan.evidence_axis == ALLOCATION_AXIS_NET_R
    assert plan.multiplier_for("a") == pytest.approx(1.0)
    assert plan.multiplier_for("b") == pytest.approx(2 / 3)
    assert 0.0 <= plan.multiplier_for("b") <= 1.0  # el eje nuevo tampoco ensancha


def test_allocation_with_unmeasured_net_r_is_identical_to_the_historical_axis() -> None:
    """Criterio de hecho del paso 6: con el R NO medido, el reparto no cambia nada.

    Cubre los dos huecos: sin R en absoluto y con R ``PARTIAL`` (§6.3: un agregado que
    solo promedia los ciclos con coste NO habilita decidir contra él).
    """
    unmeasured = (
        _row("a", decisive=True, expectancy="3"),
        _row("b", decisive=True, expectancy="1"),
    )
    partial = (
        _row(
            "a",
            decisive=True,
            expectancy="3",
            net_expectancy_r=2.0,
            net_r_measurement=MEASUREMENT_PARTIAL,
        ),
        _row(
            "b",
            decisive=True,
            expectancy="1",
            net_expectancy_r=1.0,
            net_r_measurement=MEASUREMENT_PARTIAL,
        ),
    )
    baseline = recommend_allocation(["a", "b"], unmeasured)
    assert baseline.evidence_axis == ALLOCATION_AXIS_CURRENCY
    assert baseline.multipliers == {"a": 1.0, "b": 0.5}
    for rows in (unmeasured, partial):
        plan = recommend_allocation(["a", "b"], rows)
        assert plan.multipliers == baseline.multipliers
        assert plan.evidence_axis == ALLOCATION_AXIS_CURRENCY
        assert plan.as_dict() == baseline.as_dict()


def test_allocation_does_not_mix_axes_when_only_part_of_the_pool_measures_r() -> None:
    """Un hueco de medición de UNO no lo excluye del reparto ni mezcla unidades.

    ``expectancy_currency`` es absoluta y ``net_expectancy_r`` adimensional: ponderar unas
    con R y otras con moneda sería aritmética sin sentido. Con el pool incompleto se cae
    al eje histórico, sin sacar a nadie del numerador.
    """
    rows = (
        _row(
            "a",
            decisive=True,
            expectancy="3",
            net_expectancy_r=2.0,
            net_r_measurement=MEASUREMENT_COMPLETE,
        ),
        _row("b", decisive=True, expectancy="1"),  # sin coste ⇒ R neto no medido
    )
    plan = recommend_allocation(["a", "b"], rows)
    assert plan.evidence_axis == ALLOCATION_AXIS_CURRENCY
    assert plan.multipliers == {"a": 1.0, "b": 0.5}


def test_allocation_ignores_a_measured_but_non_positive_net_r() -> None:
    """Un R neto medido y NEGATIVO no entra al numerador ni cambia el eje por sí solo."""
    rows = (
        _row(
            "a",
            decisive=True,
            expectancy="3",
            net_expectancy_r=-2.0,
            net_r_measurement=MEASUREMENT_COMPLETE,
        ),
        _row(
            "b",
            decisive=True,
            expectancy="1",
            net_expectancy_r=1.0,
            net_r_measurement=MEASUREMENT_COMPLETE,
        ),
    )
    plan = recommend_allocation(["a", "b"], rows)
    assert plan.evidence_axis == ALLOCATION_AXIS_CURRENCY
    assert plan.multipliers == {"a": 1.0, "b": 0.5}


def test_allocation_axis_requires_decisive_rows_on_both_axes() -> None:
    """Una racha favorable sin muestra decisoria no aporta peso ni en el eje del R."""
    rows = (
        _row(
            "a",
            decisive=True,
            expectancy="3",
            net_expectancy_r=2.0,
            net_r_measurement=MEASUREMENT_COMPLETE,
        ),
        _row(
            "b",
            decisive=False,
            expectancy="1",
            net_expectancy_r=9.0,
            net_r_measurement=MEASUREMENT_COMPLETE,
        ),
    )
    plan = recommend_allocation(["a", "b"], rows)
    # Los dos ejes coinciden (solo "a" compite) ⇒ eje R; "b" recibe la política neutral.
    assert plan.evidence_axis == ALLOCATION_AXIS_NET_R
    assert plan.multiplier_for("a") == pytest.approx(1.0)
    assert plan.multiplier_for("b") == pytest.approx(1.0)


def test_allocation_falls_back_to_the_historical_axis_when_the_two_axes_disagree() -> None:
    """Si un eje ve competir a quien el otro no, no se elige a dedo: manda el histórico."""
    rows = (
        _row(
            "a",
            decisive=True,
            expectancy="0",
            net_expectancy_r=2.0,
            net_r_measurement=MEASUREMENT_COMPLETE,
        ),
    )
    plan = recommend_allocation(["a"], rows)
    assert plan.evidence_axis == ALLOCATION_AXIS_CURRENCY
    assert plan.multiplier_for("a") == pytest.approx(1.0)


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


def test_build_adaptive_plan_as_dict_is_read_only_keyed_and_versioned() -> None:
    plan = build_adaptive_plan((_row("v1", decisive=False),), "LOW_VOL")
    payload = plan.as_dict()
    assert payload["key"] == "adaptive"
    assert payload["readOnly"] is True
    assert payload["regime"] == "LOW_VOL"
    assert payload["policyVersion"] == ADAPTIVE_POLICY_VERSION
    assert payload["rotation"]["paused"] == []
    assert payload["allocation"]["riskMultipliers"] == {"v1": 1.0}


def test_the_plan_payload_declares_the_axis_and_does_not_change_without_net_r() -> None:
    """Sello del paso 6 a nivel de plan: sin R medido, el payload es el histórico."""
    unmeasured = (
        _row("a", decisive=True, expectancy="3"),
        _row("b", decisive=True, expectancy="1"),
    )
    allocation = build_adaptive_plan(unmeasured, "TREND_UP").as_dict()["allocation"]
    assert allocation == {
        "riskMultipliers": {"a": 1.0, "b": 0.5},
        "evidenceAxis": ALLOCATION_AXIS_CURRENCY,
    }

    # AUTO-14: sin R neto medido el grupo pesa con la MONEDA y el reparto queda global —la celda mide
    # R, no moneda—, así que cada versión que compite declara por qué no hubo celda. El frame sellado
    # de ``allocation`` NO se toca: la base de celda va en el nivel del plan.
    cells = build_adaptive_plan(unmeasured, "TREND_UP").as_dict()["allocationCells"]
    assert cells == {
        "axis": None,
        "used": {},
        "fallback": {
            "a": ADAPTIVE_CELL_NOTE_AXIS_WITHOUT_CELL,
            "b": ADAPTIVE_CELL_NOTE_AXIS_WITHOUT_CELL,
        },
    }


def test_measuring_the_net_r_moves_the_allocation_but_never_the_rotation() -> None:
    """Medir R cambia el REPARTO; la rotación no lee R, así que no puede moverse."""
    without_r = (
        _row("a", decisive=True, expectancy="3"),
        _row("b", decisive=True, expectancy="1"),
    )
    with_r = (
        _row(
            "a",
            decisive=True,
            expectancy="3",
            net_expectancy_r=2.0,
            net_r_measurement=MEASUREMENT_COMPLETE,
        ),
        _row(
            "b",
            decisive=True,
            expectancy="1",
            net_expectancy_r=1.0,
            net_r_measurement=MEASUREMENT_COMPLETE,
        ),
    )
    before = build_adaptive_plan(without_r, "TREND_UP")
    after = build_adaptive_plan(with_r, "TREND_UP")
    assert after.rotation.as_dict() == before.rotation.as_dict()
    assert after.rotation.paused == before.rotation.paused == frozenset()
    assert before.risk_multiplier_for("b") == pytest.approx(0.5)
    assert after.risk_multiplier_for("b") == pytest.approx(2 / 3)
    assert after.allocation.evidence_axis == ALLOCATION_AXIS_NET_R


def test_build_adaptive_plan_exports_policy_version() -> None:
    plan = build_adaptive_plan((_row("v1", decisive=False),), "LOW_VOL")
    assert plan.policy_version == ADAPTIVE_POLICY_VERSION


def test_adaptive_plan_exposes_evidence_for_journal() -> None:
    rows = (
        _row(
            "v1",
            decisive=True,
            expectancy="3",
            profit_factor=2.0,
            win_rate=0.6,
            trades=20,
        ),
    )
    plan = build_adaptive_plan(rows, "TREND_UP")
    evidence = plan.evidence_for("v1")
    assert evidence is not None
    assert evidence["decisive"] is True
    assert evidence["trades"] == 20
    assert evidence["expectancyCurrency"] == "3"
    assert evidence["profitFactor"] == 2.0
    assert evidence["winRate"] == 0.6
    assert evidence["netExpectancyR"] is None  # la fila no mide coste: declarado, no inventado
    assert evidence["regime"] == "UNKNOWN"
    # Sin fila para esa versión la evidencia es AUSENTE, no un cero.
    assert plan.evidence_for("nope") is None


def test_adaptive_plan_is_reproducible_regardless_of_row_order() -> None:
    """Misma evidencia + misma política + mismo régimen ⇒ MISMO plan (byte a byte)."""
    rows = (
        _row("a", decisive=True, expectancy="3"),
        _row("b", decisive=True, expectancy="1"),
        _row("c", decisive=False),
    )
    first = build_adaptive_plan(rows, "HIGH_VOL")
    second = build_adaptive_plan(tuple(reversed(rows)), "HIGH_VOL")
    assert first.as_dict() == second.as_dict()


# ── AUTO-9 — evidencia por régimen y R neto en `StrategyHealth` (paso 5 del plan `v2.50`) ──


def _cells(
    version: str = "orb-1",
    regime: str = "trend_up",
    *,
    count: int = 10,
    with_cost: bool = True,
    min_trades: int = 10,
):
    """Celdas REALES del cruce: las construye el módulo de self-evaluation, no el test."""
    return aggregate_by_regime(
        [
            {
                "strategyVersion": version,
                "cycleId": f"{version}-{regime}-{i}",
                "pnl": "10",
                "marketRegime": regime,
                "riskAmount": "5",
                **({"cost": {"total": 1.0, "measurement": "COMPLETE"}} if with_cost else {}),
            }
            for i in range(count)
        ],
        min_trades=min_trades,
    )


def test_health_maps_the_net_expectancy_with_its_measurement() -> None:
    row = _row(
        "orb-1",
        decisive=True,
        net_expectancy_r=1.25,
        net_r_measurement=MEASUREMENT_COMPLETE,
    )
    health = StrategyHealth.from_evaluation(row)

    assert health.net_expectancy_r == pytest.approx(1.25)
    assert health.net_r_measurement == MEASUREMENT_COMPLETE
    assert health.regime == ADAPTIVE_REGIME_UNKNOWN, "sin celdas no hay régimen: se declara"


def test_health_regime_is_populated_only_when_the_cross_determines_it() -> None:
    row = _row("orb-1", decisive=True)

    determined = StrategyHealth.from_evaluation(row, regime_cells=_cells("orb-1", "trend_up"))
    assert determined.regime == "trend_up"

    foreign = StrategyHealth.from_evaluation(row, regime_cells=_cells("orb-2", "trend_up"))
    assert foreign.regime == ADAPTIVE_REGIME_UNKNOWN, (
        "las celdas de OTRA versión no son evidencia de esta"
    )


def test_health_neither_promotes_unknown_nor_picks_between_two_decisive_regimes() -> None:
    row = _row("orb-1", decisive=True)

    only_unknown = StrategyHealth.from_evaluation(row, regime_cells=_cells("orb-1", "UNKNOWN"))
    assert only_unknown.regime == ADAPTIVE_REGIME_UNKNOWN, (
        "una celda UNKNOWN decisiva no asciende a régimen"
    )

    two_regimes = StrategyHealth.from_evaluation(
        row,
        regime_cells=(*_cells("orb-1", "trend_up"), *_cells("orb-1", "range")),
    )
    assert two_regimes.regime == ADAPTIVE_REGIME_UNKNOWN, (
        "con dos regímenes decisivos no se elige uno: se declara el hueco"
    )


def test_build_strategy_health_threads_the_cells_to_every_row() -> None:
    health = build_strategy_health(
        (_row("orb-1", decisive=True), _row("orb-2", decisive=True)),
        by_regime=_cells("orb-1", "trend_up"),
    )

    assert {row.strategy_version: row.regime for row in health} == {
        "orb-1": "trend_up",
        "orb-2": ADAPTIVE_REGIME_UNKNOWN,
    }


def test_the_plan_evidence_carries_the_regime_and_the_net_measurement() -> None:
    row = _row(
        "orb-1",
        decisive=True,
        net_expectancy_r=1.8,
        net_r_measurement=MEASUREMENT_COMPLETE,
    )
    plan = build_adaptive_plan((row,), "TREND_UP", by_regime=_cells("orb-1", "trend_up"))

    health = plan.health_for("orb-1")
    assert health is not None and health.regime == "trend_up"

    evidence = plan.evidence_for("orb-1")
    assert evidence is not None
    assert evidence["netExpectancyR"] == pytest.approx(1.8)
    assert evidence["netRMeasurement"] == MEASUREMENT_COMPLETE, (
        "el neto sale de un coste ESTIMADO: el journal publica con qué cobertura se midió"
    )
    assert evidence["regime"] == "trend_up"


def test_regime_cells_change_the_allocation_declaration_but_never_the_rotation() -> None:
    """AUTO-14 — la celda afina el PESO del reparto; la rotación sigue sin leer el reparto.

    Contrato que CAMBIA respecto a ``v2.54``: tener celdas ya **no** es inocuo para el plan —la celda
    del régimen del tick aporta el número con el que compite la versión y queda DECLARADA—. Lo que no
    cambia es QUIÉN compite (lo decide la fila) ni la rotación.
    """
    rows = (
        _row(
            "orb-1",
            decisive=True,
            expectancy="3",
            net_expectancy_r=1.8,
            net_r_measurement=MEASUREMENT_COMPLETE,
        ),
    )
    without_cells = build_adaptive_plan(rows, "TREND_UP")
    with_cells = build_adaptive_plan(rows, "TREND_UP", by_regime=_cells("orb-1", "trend_up"))

    assert with_cells.rotation == without_cells.rotation
    assert with_cells.allocation.multipliers == without_cells.allocation.multipliers, (
        "la celda mide 1.8, la misma cifra que la fila: el número no cambia aunque la base sí"
    )
    assert with_cells.allocation.cell_axis == ALLOCATION_AXIS_NET_R
    assert with_cells.allocation.cell_for("orb-1") == "trend_up", (
        "la celda del régimen del tick es la que aportó el peso, y el plan lo declara"
    )
    assert with_cells.allocation.cell_note_for("orb-1") is None
    assert with_cells.health_for("orb-1").regime == "trend_up", (
        "lo que sí cambia es la evidencia publicada, no la recomendación"
    )


def test_the_policy_version_seals_the_auto14_evidence_contract() -> None:
    """No es tautología: un merge que devolviera ``auto13-v1`` movería el sello sin avisar.

    ``auto13-v1`` selló el techo de la rampa de reincorporación. ``AUTO-14`` vuelve a cambiar la regla
    de asignación —el peso de una versión que ya competía sale de su celda ``strategy × regime``
    cuando está medida—, así que la versión sube con ella: es lo que hace reproducible el plan (dos
    planes iguales no pueden venir de una base de reparto distinta sin que se note).
    """
    assert ADAPTIVE_POLICY_VERSION == "auto14-v1"
    assert AdaptivePolicy().policy_version == "auto14-v1"
    assert build_adaptive_plan((_row("v1"),), "TREND_UP").as_dict()["policyVersion"] == "auto14-v1"


# ── AUTO-12 — confianza estadística en el reparto (encogimiento por muestra) ────────


def _strategy_confidence(
    version: str,
    *,
    effective_n: int,
    decay: str = ADAPTIVE_DECAY_NONE,
    confidence: str = "HIGH",
    long_r: float | None = 1.0,
    recent_r: float | None = 1.0,
    cells: tuple[RegimeConfidence, ...] = (),
) -> StrategyConfidence:
    """Confianza de UNA estrategia, con solo lo que el reparto lee (el resto, declarado)."""
    return StrategyConfidence(
        strategy_version=version,
        sample_size=effective_n,
        effective_n=effective_n,
        measurement_completeness=MEASUREMENT_COMPLETE,
        risk_coverage=1.0,
        cost_coverage=1.0,
        regime_coverage=1.0,
        long_expectancy_r=long_r,
        recent_expectancy_r=recent_r,
        decay=decay,
        confidence=confidence,
        by_regime=cells,
        notes=(),
    )


def _cell_confidence(
    regime: str,
    *,
    effective_n: int,
    decay: str = ADAPTIVE_DECAY_NONE,
) -> RegimeConfidence:
    """Confianza de UNA celda ``strategy × regime``, con el mismo contrato que la de la fila."""
    return RegimeConfidence(
        regime=regime,
        sample_size=effective_n,
        effective_n=effective_n,
        measurement_completeness=MEASUREMENT_COMPLETE,
        risk_coverage=1.0,
        cost_coverage=1.0,
        long_expectancy_r=1.0,
        recent_expectancy_r=1.0,
        decay=decay,
        confidence="HIGH",
        notes=(),
    )


def _reading(*rows: StrategyConfidence) -> AdaptiveConfidence:
    return AdaptiveConfidence(
        by_strategy=tuple(rows),
        recent_window=ADAPTIVE_RECENT_WINDOW_DEFAULT,
        long_window=ADAPTIVE_LONG_WINDOW_DEFAULT,
        recent_available=True,
        notes=(),
    )


def test_without_confidence_the_allocation_is_byte_identical_to_the_historical_one() -> None:
    """El eje de confianza es OPCIONAL: sin él, el plan es el de ``AUTO-9`` sin tocar."""
    rows = (
        _row("a", decisive=True, expectancy="3"),
        _row("b", decisive=True, expectancy="1"),
        _row("c", decisive=False),
    )
    historical = build_adaptive_plan(rows, "TREND_UP")
    explicit_none = build_adaptive_plan(rows, "TREND_UP", confidence=None)

    assert explicit_none.as_dict() == historical.as_dict()
    assert historical.as_dict()["allocation"] == {
        "riskMultipliers": {"a": 1.0, "b": 0.5, "c": 1.0},
        "evidenceAxis": ALLOCATION_AXIS_CURRENCY,
    }
    # AUTO-14: el reparto por celda solo actúa sobre el eje del R neto medido; aquí el grupo pesa con
    # la moneda, así que el reparto es global y cada competidor lo declara.
    assert historical.as_dict()["allocationCells"] == {
        "axis": None,
        "used": {},
        "fallback": {
            "a": ADAPTIVE_CELL_NOTE_AXIS_WITHOUT_CELL,
            "b": ADAPTIVE_CELL_NOTE_AXIS_WITHOUT_CELL,
        },
    }


def test_the_shrinkage_can_be_switched_off_without_hiding_the_measured_band() -> None:
    """§29: **medir** la confianza y **usarla para repartir** son dos cosas distintas.

    Con ``shrink=False`` (el efecto ``LIMITS``/``FREEZES`` del gate) el reparto cae a su eje
    histórico —no se estrecha por evidencia fina que no es de fiar— pero la banda MEDIDA sigue
    publicándose en la evidencia. Ocultarla sería mezclar los ejes: ``shrinkage=False`` con
    ``health.confidence = LOW`` es el estado legal ``ACTIVE`` + datos ``DEGRADED`` + calidad ``LOW``
    del audit, y tiene que poder leerse entero.
    """
    rows = (
        _row("a", decisive=True, expectancy="2"),
        _row("b", decisive=True, expectancy="1"),
    )
    reading = _reading(
        _strategy_confidence("a", effective_n=12, confidence="LOW"),
        _strategy_confidence("b", effective_n=180, confidence="HIGH"),
    )

    shrunk = build_adaptive_plan(rows, "TREND_UP", confidence=reading)
    plain = build_adaptive_plan(rows, "TREND_UP", confidence=reading, shrink=False)
    historical = build_adaptive_plan(rows, "TREND_UP")

    assert shrunk.shrinkage is True
    assert plain.shrinkage is False
    assert plain.as_dict()["shrinkage"] is False
    assert plain.allocation.as_dict() == historical.allocation.as_dict(), (
        "sin encogimiento el reparto es el histórico, aunque la banda esté medida"
    )
    assert shrunk.risk_multiplier_for("a") < plain.risk_multiplier_for("a")
    assert plain.health_for("a").confidence == "LOW", "el hecho medido no se apaga con el uso"
    assert plain.evidence_for("a")["confidence"] == "LOW"


def test_a_thin_positive_edge_cannot_outweigh_a_broad_one() -> None:
    """El caso §25 del audit: A ``+2R/N=12`` no puede llevarse el peso pleno frente a B.

    Sin confianza, A empata en el techo (1.0) con la muestra ancha; con confianza, su peso se
    encoge por muestra efectiva y B —misma medición, historia amplia— pasa por delante.
    """
    rows = (
        _row("c", decisive=True, expectancy="3"),
        _row("a", decisive=True, expectancy="2"),
        _row("b", decisive=True, expectancy="1"),
    )
    without = build_adaptive_plan(rows, "TREND_UP")
    with_confidence = build_adaptive_plan(
        rows,
        "TREND_UP",
        confidence=_reading(
            _strategy_confidence("c", effective_n=180),
            _strategy_confidence("a", effective_n=12),
            _strategy_confidence("b", effective_n=180),
        ),
    )

    assert without.risk_multiplier_for("a") == pytest.approx(1.0)
    assert with_confidence.risk_multiplier_for("a") < 1.0, "el edge fino pierde el peso pleno"
    assert with_confidence.risk_multiplier_for("b") >= with_confidence.risk_multiplier_for("a")
    for version in ("a", "b", "c"):
        assert 0.0 < with_confidence.risk_multiplier_for(version) <= 1.0


def test_the_shrinkage_redistributes_and_never_empties_a_strategy() -> None:
    """Encoger es redistribuir, no eliminar: ninguna activa queda con multiplicador 0."""
    rows = (
        _row("a", decisive=True, expectancy="10"),
        _row("b", decisive=True, expectancy="1"),
    )
    plan = build_adaptive_plan(
        rows,
        "TREND_UP",
        confidence=_reading(
            _strategy_confidence("a", effective_n=1, confidence="LOW"),
            _strategy_confidence("b", effective_n=500),
        ),
    )

    assert plan.risk_multiplier_for("a") > 0.0
    assert plan.risk_multiplier_for("b") > 0.0
    assert plan.risk_multiplier_for("b") > build_adaptive_plan(rows, "TREND_UP").risk_multiplier_for("b")


def test_a_severe_decay_gets_an_additional_declared_discount() -> None:
    """``decay == SEVERE`` modula el reparto; NO pausa (la pausa sigue siendo de la rotación)."""
    rows = (
        _row("c", decisive=True, expectancy="4"),
        _row("a", decisive=True, expectancy="2"),
        _row("b", decisive=True, expectancy="1"),
    )
    healthy = build_adaptive_plan(
        rows,
        "TREND_UP",
        confidence=_reading(
            _strategy_confidence("c", effective_n=180),
            _strategy_confidence("a", effective_n=180),
            _strategy_confidence("b", effective_n=180),
        ),
    )
    decaying = build_adaptive_plan(
        rows,
        "TREND_UP",
        confidence=_reading(
            _strategy_confidence("c", effective_n=180),
            _strategy_confidence("a", effective_n=180, decay=ADAPTIVE_DECAY_SEVERE),
            _strategy_confidence("b", effective_n=180),
        ),
    )

    assert decaying.rotation == healthy.rotation, "el decay no crea un motivo de pausa nuevo"
    assert decaying.risk_multiplier_for("a") < healthy.risk_multiplier_for("a")


def test_a_strategy_without_a_decisive_edge_keeps_the_neutral_multiplier() -> None:
    """La confianza fina solo actúa sobre un edge MEDIDO: el desconocido no se castiga."""
    rows = (
        _row("a", decisive=True, expectancy="2"),
        _row("z", decisive=False),
    )
    plan = build_adaptive_plan(
        rows,
        "TREND_UP",
        confidence=_reading(_strategy_confidence("a", effective_n=12, confidence="LOW")),
    )

    assert plan.risk_multiplier_for("z") == pytest.approx(1.0), "sin evidencia decisoria no hay castigo"


def test_confidence_alone_never_moves_the_rotation() -> None:
    rows = (
        _row("a", decisive=True, expectancy="-2"),
        _row("b", decisive=True, expectancy="3"),
    )
    without = build_adaptive_plan(rows, "TREND_UP")
    with_confidence = build_adaptive_plan(
        rows,
        "TREND_UP",
        confidence=_reading(
            _strategy_confidence("a", effective_n=12),
            _strategy_confidence("b", effective_n=180, decay=ADAPTIVE_DECAY_SEVERE),
        ),
    )

    assert with_confidence.rotation.as_dict() == without.rotation.as_dict()


def test_the_policy_carries_the_shrinkage_knobs() -> None:
    """Los parámetros del encogimiento son POLÍTICA versionada, no constantes sueltas."""
    policy = AdaptivePolicy()
    assert policy.confidence_prior == ADAPTIVE_CONFIDENCE_PRIOR_DEFAULT
    assert policy.severe_decay_factor == ADAPTIVE_SEVERE_DECAY_FACTOR_DEFAULT
    # Un prior distinto cambia el reparto sin tocar la evidencia: es la política quien lo manda.
    lazy = AdaptivePolicy(confidence_prior=0.0)
    rows = (_row("a", decisive=True, expectancy="1"), _row("b", decisive=True, expectancy="1"))
    reading = _reading(
        _strategy_confidence("a", effective_n=5), _strategy_confidence("b", effective_n=500)
    )
    with_prior = build_adaptive_plan(rows, "TREND_UP", policy=policy, confidence=reading)
    without_prior = build_adaptive_plan(rows, "TREND_UP", policy=lazy, confidence=reading)

    assert with_prior.risk_multiplier_for("a") < without_prior.risk_multiplier_for("a")


def test_health_carries_the_confidence_and_the_two_windows() -> None:
    row = _row("orb-1", decisive=True, expectancy="3")
    health = build_strategy_health(
        (row,),
        confidence=_reading(
            _strategy_confidence(
                "orb-1", effective_n=180, long_r=0.21, recent_r=-0.15, decay=ADAPTIVE_DECAY_SEVERE
            )
        ),
    )[0]

    assert health.confidence == "HIGH"
    assert health.long_expectancy_r == pytest.approx(0.21)
    assert health.recent_expectancy_r == pytest.approx(-0.15)
    assert health.decay == ADAPTIVE_DECAY_SEVERE


def test_without_a_confidence_reading_the_health_fields_are_declared_absent() -> None:
    health = StrategyHealth.from_evaluation(_row("orb-1", decisive=True))

    assert health.confidence is None
    assert health.decay is None
    assert health.long_expectancy_r is None and health.recent_expectancy_r is None


def test_the_plan_evidence_publishes_the_confidence_axis() -> None:
    """La confianza viaja en el payload durable DENTRO de la forma existente (sin migración)."""
    rows = (_row("orb-1", decisive=True, expectancy="3"),)
    plan = build_adaptive_plan(
        rows,
        "TREND_UP",
        confidence=_reading(_strategy_confidence("orb-1", effective_n=12, long_r=0.4, recent_r=0.4)),
    )
    evidence = plan.evidence_for("orb-1")

    assert evidence is not None
    assert evidence["confidence"] == "HIGH"
    assert evidence["longExpectancyR"] == pytest.approx(0.4)
    assert evidence["recentExpectancyR"] == pytest.approx(0.4)
    assert evidence["decay"] == ADAPTIVE_DECAY_NONE
    assert plan.as_dict()["readOnly"] is True, "la confianza no toca la autoridad de ejecución"
    assert set(evidence) >= {
        "confidence",
        "recentExpectancyR",
        "longExpectancyR",
        "decay",
    }


def test_the_plan_stays_reproducible_with_a_confidence_reading() -> None:
    rows = (
        _row("a", decisive=True, expectancy="3"),
        _row("b", decisive=True, expectancy="1"),
    )
    reading = _reading(
        _strategy_confidence("a", effective_n=12), _strategy_confidence("b", effective_n=180)
    )
    first = build_adaptive_plan(rows, "HIGH_VOL", confidence=reading)
    second = build_adaptive_plan(tuple(reversed(rows)), "HIGH_VOL", confidence=reading)

    assert first.as_dict() == second.as_dict()


# ── AUTO-13 — RECOVERING y la rampa de reincorporación (§23/§24) ────────────────────


def _evidence(
    version: str = "a",
    *,
    cycles: int = 0,
    window: bool = True,
    positive: bool = True,
    severe: bool = False,
) -> RecoveryEvidence:
    return RecoveryEvidence(
        strategy_version=version,
        measured_cycles=cycles,
        window_available=window,
        measured_positive=positive,
        severe_decay=severe,
    )


def test_the_ramp_steps_are_declared_policy_with_a_positive_floor() -> None:
    """Los escalones son POLÍTICA versionada y su suelo es > 0: la rampa no es una pausa encubierta."""
    policy = AdaptivePolicy()
    assert policy.recovery_steps == ADAPTIVE_RECOVERY_STEPS_DEFAULT
    assert policy.recovery_step_cycles == ADAPTIVE_RECOVERY_STEP_CYCLES_DEFAULT
    assert policy.recovery_steps[0] > 0.0, "suelo: nunca deja a nadie en 0"
    assert policy.recovery_steps[-1] == 1.0, "el techo es el peso pleno"


@pytest.mark.parametrize(
    "steps",
    [(0.0, 1.0), (0.25, 0.25), (1.0, 0.5), (0.25, 1.5)],
)
def test_a_broken_ramp_is_rejected_instead_of_silently_applied(steps: tuple[float, ...]) -> None:
    with pytest.raises(ValueError):
        AdaptivePolicy(recovery_steps=steps)


def test_a_broken_recovery_step_is_rejected() -> None:
    with pytest.raises(ValueError):
        AdaptivePolicy(recovery_step_cycles=0)


def test_the_ramp_climbs_one_step_per_evidence_cycles() -> None:
    """Sube por EVIDENCIA: 3 ciclos positivos por escalón, con el paso declarado en la política."""
    per = ADAPTIVE_RECOVERY_STEP_CYCLES_DEFAULT
    assert recovery_reading(_evidence(cycles=0)).step == pytest.approx(0.25)
    assert recovery_reading(_evidence(cycles=per - 1)).step == pytest.approx(0.25)
    assert recovery_reading(_evidence(cycles=per)).step == pytest.approx(0.50)
    assert recovery_reading(_evidence(cycles=2 * per)).step == pytest.approx(0.75)
    assert recovery_reading(_evidence(cycles=3 * per)).step == pytest.approx(1.00)
    assert recovery_reading(_evidence(cycles=1000)).step == pytest.approx(1.00), "techo estable"


def test_the_ramp_does_not_climb_by_time_alone() -> None:
    """Sin ciclos positivos medidos no sube: es el caso §24 que la rampa NO debe inventar."""
    flat = recovery_reading(_evidence(cycles=0))
    assert flat.step_index == 0
    assert flat.step == pytest.approx(ADAPTIVE_RECOVERY_STEPS_DEFAULT[0])
    assert flat.note is None, "evidencia plana medida no es un hueco: no se declara motivo"


def test_a_deteriorating_evidence_resets_the_ramp_and_declares_why() -> None:
    severe = recovery_reading(_evidence(cycles=99, severe=True))
    not_positive = recovery_reading(_evidence(cycles=99, positive=False))
    unmeasured = recovery_reading(_evidence(cycles=99, window=False))

    assert severe.step == pytest.approx(0.25)
    assert severe.note == ADAPTIVE_RECOVERY_NOTE_SEVERE
    assert not_positive.step == pytest.approx(0.25)
    assert not_positive.note == ADAPTIVE_RECOVERY_NOTE_NOT_POSITIVE
    assert unmeasured.step == pytest.approx(0.25)
    assert unmeasured.note == ADAPTIVE_RECOVERY_NOTE_UNMEASURED


def test_the_unreadable_window_wins_over_an_optimistic_count() -> None:
    """Sin fechas legibles la rampa NO sube aunque el contador traiga ciclos: hueco declarado."""
    reading = recovery_reading(_evidence(cycles=30, window=False))

    assert reading.step == pytest.approx(0.25)
    assert reading.evidence_cycles == 30, "los ciclos medidos se declaran; el escalón no los usa"


def test_without_recovery_evidence_the_plan_is_byte_identical() -> None:
    """La rampa es OPCIONAL: sin ella el plan es el histórico de ``auto12``/``auto13``."""
    rows = (_row("a", decisive=True, expectancy="3"), _row("b", decisive=True, expectancy="1"))
    historical = build_adaptive_plan(rows, "TREND_UP")
    explicit_empty = build_adaptive_plan(rows, "TREND_UP", recovery={})

    assert explicit_empty.as_dict() == historical.as_dict()
    assert historical.recovery == {}
    assert historical.state_for("a") == ADAPTIVE_STATE_ACTIVE


def test_the_ramp_is_a_ceiling_of_the_allocation_and_never_widens() -> None:
    """``m_final = min(m_reparto, escalón)``: estrecha, nunca ensancha, y nunca llega a 0."""
    rows = (_row("a", decisive=True, expectancy="3"), _row("b", decisive=True, expectancy="1"))
    base = build_adaptive_plan(rows, "TREND_UP")
    ramped = build_adaptive_plan(
        rows,
        "TREND_UP",
        recovery={"a": _evidence("a", cycles=0), "b": _evidence("b", cycles=3)},
    )

    assert base.risk_multiplier_for("a") == pytest.approx(1.0)
    assert ramped.risk_multiplier_for("a") == pytest.approx(0.25), "el techo manda"
    assert ramped.risk_multiplier_for("b") == base.risk_multiplier_for("b"), (
        "un escalón por encima del reparto no lo ensancha"
    )
    assert ramped.risk_multiplier_for("b") == pytest.approx(0.5)
    for version in ("a", "b"):
        assert 0.0 < ramped.risk_multiplier_for(version) <= 1.0


def test_the_ramp_does_not_touch_the_rotation() -> None:
    """La rampa es una modulación del reparto: quien pausa sigue siendo ``recommend_rotation``."""
    rows = (_row("a", decisive=True, expectancy="-2"), _row("b", decisive=True, expectancy="3"))
    base = build_adaptive_plan(rows, "TREND_UP")
    ramped = build_adaptive_plan(
        rows, "TREND_UP", recovery={"a": _evidence("a"), "b": _evidence("b")}
    )

    assert ramped.rotation.as_dict() == base.rotation.as_dict()
    assert ramped.state_for("a") == ADAPTIVE_STATE_PAUSED


def test_a_paused_version_discards_its_ramp_instead_of_publishing_it() -> None:
    """Si el deterioro devuelve a pausa, la rotación manda y el escalón se DESCARTA (§24)."""
    rows = (_row("a", decisive=True, expectancy="-2"),)
    plan = build_adaptive_plan(rows, "TREND_UP", recovery={"a": _evidence("a", cycles=3)})

    assert plan.recovery_for("a") is None
    assert plan.recovery == {}
    assert plan.state_for("a") == ADAPTIVE_STATE_PAUSED


def test_recovering_is_derived_and_the_ceiling_step_returns_the_version_to_active() -> None:
    rows = (_row("a", decisive=True, expectancy="3"),)
    recovering = build_adaptive_plan(rows, "TREND_UP", recovery={"a": _evidence("a", cycles=3)})
    recovered = build_adaptive_plan(
        rows,
        "TREND_UP",
        recovery={"a": _evidence("a", cycles=3 * ADAPTIVE_RECOVERY_STEP_CYCLES_DEFAULT)},
    )

    assert recovering.state_for("a") == ADAPTIVE_STATE_RECOVERING
    assert recovering.recovery_for("a") is not None
    assert recovered.state_for("a") == ADAPTIVE_STATE_ACTIVE, "el techo (1.00) es recuperación cumplida"
    assert recovered.risk_multiplier_for("a") == pytest.approx(1.0)


def test_the_operational_states_travel_in_their_own_field_without_mixing_axes() -> None:
    """§29: el estado operativo viaja declarado y NO se mezcla con la confianza ni con el gate."""
    rows = (_row("a", decisive=True, expectancy="3"), _row("b", decisive=True, expectancy="-1"))
    plan = build_adaptive_plan(
        rows,
        "TREND_UP",
        confidence=_reading(_strategy_confidence("a", effective_n=180, recent_r=0.5)),
        recovery={"a": _evidence("a", cycles=0), "b": _evidence("b", cycles=0)},
    )
    payload = plan.as_dict()

    assert payload["operationalStates"] == {"a": ADAPTIVE_STATE_RECOVERING, "b": ADAPTIVE_STATE_PAUSED}
    assert payload["recovery"]["a"]["step"] == pytest.approx(0.25)
    assert "b" not in payload["recovery"], "una pausada no publica rampa"
    assert payload["readOnly"] is True
    assert payload["policyVersion"] == ADAPTIVE_POLICY_VERSION == "auto14-v1"
    assert plan.health_for("a").confidence == "HIGH", "la calidad estadística va en su propio campo"


def test_the_ramp_is_reproducible_regardless_of_row_order() -> None:
    rows = (_row("a", decisive=True, expectancy="3"), _row("b", decisive=True, expectancy="1"))
    evidence = {"a": _evidence("a", cycles=4), "b": _evidence("b", cycles=0)}
    first = build_adaptive_plan(rows, "TREND_UP", recovery=evidence)
    second = build_adaptive_plan(tuple(reversed(rows)), "TREND_UP", recovery=evidence)

    assert first.as_dict() == second.as_dict()


# ── AUTO-13 (§20): el hueco del cruce se declara y NUNCA se vuelve adverso ──────────


def test_the_health_row_keeps_the_undetermined_regime_with_its_reason() -> None:
    """El par ``(régimen, motivo)`` no se separa: un ``UNKNOWN`` legítimo lo dice."""
    row = _row("orb-1", decisive=True)

    determined = StrategyHealth.from_evaluation(row, regime_cells=_cells("orb-1", "trend_up"))
    assert determined.regime == "trend_up"
    assert determined.regime_undetermined is False

    # Dos regímenes decisivos: no se elige uno a dedo y el hueco se DECLARA.
    two = StrategyHealth.from_evaluation(
        row,
        regime_cells=(*_cells("orb-1", "trend_up"), *_cells("orb-1", "range")),
    )
    assert two.regime == ADAPTIVE_REGIME_UNKNOWN
    assert two.regime_undetermined is True

    # Sin celdas tampoco hay régimen: mismo motivo declarado, nunca un régimen implícito.
    empty = StrategyHealth.from_evaluation(row)
    assert empty.regime == ADAPTIVE_REGIME_UNKNOWN
    assert empty.regime_undetermined is True


def test_an_undetermined_cross_regime_falls_back_to_the_global_evidence() -> None:
    """§20: sin régimen del cruce manda la fila GLOBAL — pausa por salud, nunca por régimen."""
    thin = _row("thin", win_rate=0.1, trades=3)
    bad = _row("bad", decisive=True, expectancy="-1", trades=20)
    undetermined = (*_cells("thin", "trend_up"), *_cells("thin", "range"))

    plan = recommend_rotation((thin, bad), "TREND_UP", by_regime=undetermined)

    assert plan.is_paused("bad"), "la evidencia global sí pausa una estrategia probadamente mala"
    assert plan.reason_for("bad") == ADAPTIVE_STRATEGY_UNHEALTHY
    assert not plan.is_paused("thin"), "sin cruce determinado no se pausa por régimen"
    assert plan.reason_for("thin") is None


def test_a_regime_that_could_not_be_read_never_arms_the_adverse_branch() -> None:
    """§20: ``None``/``UNKNOWN`` ⇒ nunca adverso. La rama adversa solo se arma con un régimen REAL."""
    thin = _row("thin", win_rate=0.1, trades=3)

    for unreadable in (None, "", "UNKNOWN", "RISK_OFF"):
        plan = recommend_rotation((thin,), unreadable)
        assert not plan.is_paused("thin"), f"{unreadable!r} no es un régimen adverso"
        assert plan.reason_for("thin") is None

    # Control: con el régimen adverso de verdad (y la muestra fina) la rama SÍ se arma.
    adverse = recommend_rotation((thin,), "TREND_DOWN")
    assert adverse.reason_for("thin") == ADAPTIVE_STRATEGY_REGIME_RISK


def test_the_plan_publishes_the_undetermined_regimes_in_their_own_field() -> None:
    """La declaración viaja en el plan, con campo propio y ordenada (no es un régimen)."""
    rows = (_row("orb-1", decisive=True), _row("orb-2", decisive=True))
    plan = build_adaptive_plan(
        rows,
        "TREND_UP",
        by_regime=(*_cells("orb-1", "trend_up"), *_cells("orb-2", "trend_up"), *_cells("orb-2", "range")),
    )

    payload = plan.as_dict()

    assert payload["regimeUndetermined"] == ["orb-2"]
    assert payload["regime"] == "TREND_UP", "el régimen del tick es otra cosa y va en su campo"
    assert plan.health_for("orb-1").regime == "trend_up"


def test_without_a_regime_gap_the_declaration_is_empty_and_the_plan_is_unchanged() -> None:
    """Sin hueco no hay nada que declarar: el campo viaja vacío, no se inventa."""
    plan = build_adaptive_plan(
        (_row("orb-1", decisive=True),), "TREND_UP", by_regime=_cells("orb-1", "trend_up")
    )

    assert plan.regime_undetermined == ()
    assert plan.as_dict()["regimeUndetermined"] == []


# ── AUTO-14 — reparto por CELDA de régimen (pasos 1–3 del plan `v2.55`) ─────────────
#
# El invariante: **el reparto no puede mejorar su peso con una celda que no se ha medido**. La celda
# afina el PESO de una versión que YA competía (la composición la decide la fila) y todo hueco se
# declara: celda fina, celda sin el neto medido, celda no positiva, celda ausente y régimen ilegible.


def _cell(
    version: str = "orb-1",
    regime: str = "trend_up",
    *,
    pnl: str = "10",
    risk: str = "5",
    cost: float | None = 1.0,
    count: int = 10,
    min_trades: int = 10,
):
    """Celda REAL del cruce con su R neto CONTROLADO (la construye self-evaluation, no el test)."""
    return aggregate_by_regime(
        [
            {
                "strategyVersion": version,
                "cycleId": f"{version}-{regime}-{i}",
                "pnl": pnl,
                "marketRegime": regime,
                "riskAmount": risk,
                **({"cost": {"total": cost, "measurement": "COMPLETE"}} if cost is not None else {}),
            }
            for i in range(count)
        ],
        min_trades=min_trades,
    )


def _competing_rows() -> tuple[StrategySelfEvaluation, ...]:
    """Dos versiones que compiten en el eje del R NETO con la misma cifra (reparto plano)."""
    return (
        _row(
            "a",
            decisive=True,
            expectancy="3",
            net_expectancy_r=1.0,
            net_r_measurement=MEASUREMENT_COMPLETE,
        ),
        _row(
            "b",
            decisive=True,
            expectancy="1",
            net_expectancy_r=1.0,
            net_r_measurement=MEASUREMENT_COMPLETE,
        ),
    )


def test_regime_cell_for_reads_the_measured_cell_of_the_tick_regime() -> None:
    """La celda se elige por ``(versión, régimen del tick)`` con normalización de CAJA declarada.

    La celda guarda el régimen tal y como lo midió el cruce (``trend_up``) y el plan recibe el
    canónico del tick (``TREND_UP``): la normalización es de FORMA y única, no un segundo mapa de
    alias que pudiera divergir del que usó la rotación.
    """
    cells = _cell("orb-1", "trend_up", pnl="20")  # R neto = (20 − 1) / 5 = 3.8

    found, note = regime_cell_for(cells, "orb-1", "TREND_UP")

    assert note is None
    assert found is not None
    assert found.regime == "trend_up"
    assert found.net_expectancy_r == pytest.approx(3.8)
    assert found.decisive is True


def test_regime_cell_for_declares_every_gap_without_inventing_a_cell() -> None:
    """Sin coincidencia no se elige OTRA celda ni se hereda la de otro: el hueco se declara."""
    cells = _cell("orb-1", "trend_up")

    for unreadable in (None, "", "   ", "UNKNOWN", "unknown"):
        assert regime_cell_for(cells, "orb-1", unreadable) == (
            None,
            ADAPTIVE_CELL_NOTE_REGIME_ABSENT,
        ), f"{unreadable!r} no es un régimen legible"

    assert regime_cell_for(cells, "orb-2", "TREND_UP") == (
        None,
        ADAPTIVE_CELL_NOTE_NOT_FOUND,
    ), "la celda de OTRA versión no es evidencia de esta"
    assert regime_cell_for(cells, "orb-1", "RANGE") == (None, ADAPTIVE_CELL_NOTE_NOT_FOUND)
    assert regime_cell_for((), "orb-1", "TREND_UP") == (None, ADAPTIVE_CELL_NOTE_NOT_FOUND)


def test_regime_cell_for_refuses_a_thin_an_unmeasured_or_a_non_positive_cell() -> None:
    """Los tres huecos que impiden que una celda mueva el peso, cada uno con su motivo."""
    thin = _cell("orb-1", "trend_up", count=3, min_trades=10)
    assert regime_cell_for(thin, "orb-1", "TREND_UP") == (None, ADAPTIVE_CELL_NOTE_NOT_DECISIVE)

    unmeasured = _cell("orb-1", "trend_up", cost=None)
    assert regime_cell_for(unmeasured, "orb-1", "TREND_UP") == (
        None,
        ADAPTIVE_CELL_NOTE_NET_UNMEASURED,
    )

    losing = _cell("orb-1", "trend_up", pnl="-20")
    assert regime_cell_for(losing, "orb-1", "TREND_UP") == (
        None,
        ADAPTIVE_CELL_NOTE_NOT_POSITIVE,
    )


def test_a_measured_cell_moves_the_pool_weight_of_its_version() -> None:
    """La celda del régimen del tick SUSTITUYE al global en el peso de quien ya competía."""
    rows = _competing_rows()
    flat = build_adaptive_plan(rows, "TREND_UP").allocation
    assert flat.evidence_axis == ALLOCATION_AXIS_NET_R
    assert flat.multiplier_for("a") == pytest.approx(1.0)
    assert flat.multiplier_for("b") == pytest.approx(1.0)

    # La celda de "a" mide 3.8 frente al 1.0 global: su peso relativo sube y el de "b" baja.
    celled = build_adaptive_plan(
        rows, "TREND_UP", by_regime=_cell("a", "trend_up", pnl="20")
    ).allocation

    assert celled.evidence_axis == ALLOCATION_AXIS_NET_R
    assert celled.cell_axis == ALLOCATION_AXIS_NET_R
    assert celled.cell_for("a") == "trend_up"
    assert celled.cell_note_for("a") is None
    assert celled.multiplier_for("a") == pytest.approx(1.0)
    assert celled.multiplier_for("b") == pytest.approx((1.0 / 4.8) * 2)
    # "b" no tiene celda para el régimen del tick: conserva su GLOBAL y lo declara.
    assert celled.cell_note_for("b") == ADAPTIVE_CELL_NOTE_NOT_FOUND
    assert celled.multipliers["b"] < flat.multipliers["b"]


def test_a_thin_cell_never_moves_the_weight_and_the_gap_is_declared() -> None:
    """Una racha medida sobre pocos ciclos NO puede mejorar el peso: se declara y se cae al global."""
    rows = _competing_rows()
    flat = build_adaptive_plan(rows, "TREND_UP").allocation

    thin = _cell("a", "trend_up", pnl="200", count=3, min_trades=10)  # R neto 39.8, sin muestra
    plan = build_adaptive_plan(rows, "TREND_UP", by_regime=thin).allocation

    assert plan.multipliers == flat.multipliers, "la celda fina no mueve NADA"
    assert plan.cell_used == {}
    assert plan.cell_note_for("a") == ADAPTIVE_CELL_NOTE_NOT_DECISIVE
    assert plan.cell_note_for("b") == ADAPTIVE_CELL_NOTE_NOT_FOUND


def test_an_unreadable_tick_regime_never_arms_the_cell_path() -> None:
    """Sin régimen legible no hay juicio de régimen: la celda se ignora y el motivo se declara."""
    rows = _competing_rows()
    flat = build_adaptive_plan(rows, "TREND_UP").allocation

    for unreadable in (None, "", "UNKNOWN"):
        plan = build_adaptive_plan(
            rows, unreadable, by_regime=_cell("a", "trend_up", pnl="20")
        ).allocation
        assert plan.multipliers == flat.multipliers
        assert plan.cell_used == {}
        assert plan.cell_note_for("a") == ADAPTIVE_CELL_NOTE_REGIME_ABSENT


def test_the_currency_axis_never_applies_a_cell_and_declares_why() -> None:
    """La celda mide R, no moneda: con el eje de moneda el reparto queda global y se declara."""
    rows = (
        _row("a", decisive=True, expectancy="3"),
        _row("b", decisive=True, expectancy="1"),
    )
    plan = build_adaptive_plan(
        rows, "TREND_UP", by_regime=_cell("a", "trend_up", pnl="20")
    ).allocation

    assert plan.evidence_axis == ALLOCATION_AXIS_CURRENCY
    assert plan.multiplier_for("a") == pytest.approx(1.0)
    assert plan.multiplier_for("b") == pytest.approx(0.5)
    assert plan.cell_axis is None
    assert plan.cell_used == {}
    assert plan.cell_note_for("a") == ADAPTIVE_CELL_NOTE_AXIS_WITHOUT_CELL
    assert plan.cell_note_for("b") == ADAPTIVE_CELL_NOTE_AXIS_WITHOUT_CELL


def test_the_cell_never_changes_who_competes_nor_mixes_the_axes() -> None:
    """La celda afina el PESO: la composición del numerador la sigue decidiendo la FILA."""
    rows = (
        *_competing_rows(),
        _row("c", decisive=False, expectancy="9"),  # muestra fina: no compite ni con celda buena
    )
    baseline = build_adaptive_plan(rows, "TREND_UP").allocation

    cells = (*_cell("a", "trend_up", pnl="20"), *_cell("c", "trend_up", pnl="90"))
    celled = build_adaptive_plan(rows, "TREND_UP", by_regime=cells).allocation

    assert celled.evidence_axis == baseline.evidence_axis == ALLOCATION_AXIS_NET_R
    assert celled.multiplier_for("c") == pytest.approx(1.0), "sigue NEUTRAL: no entra al numerador"
    assert "c" not in celled.cell_used, "una celda propia no puede admitir a quien la fila no admite"
    assert celled.cell_note_for("c") is None
    assert set(celled.multipliers) == set(baseline.multipliers)
    assert all(0.0 < value <= 1.0 for value in celled.multipliers.values())


def test_the_shrinkage_uses_the_confidence_of_the_CELL_not_the_strategy() -> None:
    """``AUTO-12`` encoge el peso con la banda de la CELDA cuando el peso salió de ella."""
    rows = _competing_rows()
    cells = _cell("a", "trend_up", pnl="20")  # R neto 3.8

    # La FILA de "a" declara base amplia (180) y su CELDA es fina (4): si el encogimiento leyera la
    # fila, "a" conservaría casi todo su 3.8; leyendo la celda, su peso se recorta.
    by_cell = build_adaptive_plan(
        rows,
        "TREND_UP",
        by_regime=cells,
        confidence=_reading(
            _strategy_confidence(
                "a", effective_n=180, cells=(_cell_confidence("trend_up", effective_n=4),)
            ),
            _strategy_confidence("b", effective_n=180),
        ),
    ).allocation

    share_a = 3.8 * (4.0 / 24.0)  # factor de la celda: n/(n+prior)
    share_b = 1.0 * (180.0 / 200.0)
    assert by_cell.multiplier_for("a") == pytest.approx((share_a / (share_a + share_b)) * 2)

    # CONTROL: con la banda de la FILA (base amplia) "a" pesa más y "b" menos. Sin la celda el
    # encogimiento no cambia, así que la diferencia solo puede venir de leer la banda de la celda.
    by_row = build_adaptive_plan(
        rows,
        "TREND_UP",
        by_regime=cells,
        confidence=_reading(
            _strategy_confidence("a", effective_n=180),
            _strategy_confidence("b", effective_n=180),
        ),
    ).allocation
    assert by_row.multiplier_for("b") < by_cell.multiplier_for("b")


def test_the_auto13_ramp_is_still_the_ceiling_of_the_cell_weight() -> None:
    """La rampa sigue siendo TECHO del peso de celda: se aplica después y solo estrecha."""
    rows = _competing_rows()
    plan = build_adaptive_plan(
        rows,
        "TREND_UP",
        by_regime=_cell("a", "trend_up", pnl="20"),
        recovery={"a": _evidence("a", cycles=0)},
    )

    assert plan.allocation.cell_for("a") == "trend_up", "la rampa no borra la base del reparto"
    assert plan.risk_multiplier_for("a") == pytest.approx(0.25), "el escalón inicial es el techo"
    assert plan.state_for("a") == ADAPTIVE_STATE_RECOVERING


def test_the_plan_publishes_the_cell_basis_in_its_own_field_without_touching_the_frame() -> None:
    """La base de celda viaja en el plan con campo propio; el frame sellado de ``allocation`` no."""
    rows = _competing_rows()
    payload = build_adaptive_plan(
        rows, "TREND_UP", by_regime=_cell("a", "trend_up", pnl="20")
    ).as_dict()

    assert set(payload["allocation"]) == {"riskMultipliers", "evidenceAxis"}
    assert payload["allocationCells"] == {
        "axis": ALLOCATION_AXIS_NET_R,
        "used": {"a": "trend_up"},
        "fallback": {"b": ADAPTIVE_CELL_NOTE_NOT_FOUND},
    }


def test_without_cells_the_cell_basis_is_declared_empty_and_stays_reproducible() -> None:
    """Sin celdas no hay base que declarar, y la reproducibilidad del plan no cambia."""
    rows = _competing_rows()
    first = build_adaptive_plan(rows, "TREND_UP")
    second = build_adaptive_plan(tuple(reversed(rows)), "TREND_UP")

    assert first.as_dict() == second.as_dict()
    assert first.as_dict()["allocationCells"] == {
        "axis": ALLOCATION_AXIS_NET_R,
        "used": {},
        "fallback": {
            "a": ADAPTIVE_CELL_NOTE_NOT_FOUND,
            "b": ADAPTIVE_CELL_NOTE_NOT_FOUND,
        },
    }
