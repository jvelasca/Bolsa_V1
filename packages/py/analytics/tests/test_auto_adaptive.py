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
    ADAPTIVE_POLICY_VERSION,
    ADAPTIVE_REGIME_UNKNOWN,
    ADAPTIVE_STRATEGY_COOLDOWN,
    ADAPTIVE_STRATEGY_PAUSED,
    ADAPTIVE_STRATEGY_REGIME_RISK,
    ADAPTIVE_STRATEGY_UNHEALTHY,
    ALLOCATION_AXIS_CURRENCY,
    ALLOCATION_AXIS_NET_R,
    AdaptivePolicy,
    StrategyHealth,
    build_adaptive_plan,
    build_strategy_health,
    recommend_allocation,
    recommend_rotation,
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


def test_regime_cells_alone_do_not_move_rotation_or_allocation() -> None:
    """El paso 5 MAPEA la evidencia; la política sigue ignorando el régimen, como hoy.

    Quien decide con el R neto es la asignación (paso 6). Aquí se fija que tener celdas de
    régimen no cambia ni la pausa ni el multiplicador por sí solo.
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
    assert with_cells.allocation == without_cells.allocation
    assert with_cells.health_for("orb-1").regime == "trend_up", (
        "lo que sí cambia es la evidencia publicada, no la recomendación"
    )


def test_the_policy_version_seals_the_auto9_evidence_contract() -> None:
    """No es tautología: un merge que devolviera ``auto8-v2`` movería el sello sin avisar.

    El contrato de evidencia cambió (régimen determinado + R neto con su medición), así que
    la versión de la política cambia con él; es lo que hace reproducible el plan.
    """
    assert ADAPTIVE_POLICY_VERSION == "auto9-v1"
    assert AdaptivePolicy().policy_version == "auto9-v1"
    assert build_adaptive_plan((_row("v1"),), "TREND_UP").as_dict()["policyVersion"] == "auto9-v1"
