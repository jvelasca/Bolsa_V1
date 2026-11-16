"""P1 — beneficio NETO y expectativa positiva (auditoría LAB 2026-11-16).

El LAB optimizaba sobre retorno bruto y no exigía que el campeón ganara dinero después de
comisiones. Estos tests fijan el gate P1: sin base neta medida, con fricción por debajo del
suelo, sin beneficio neto o sin expectativa positiva **no hay PASS** (fail-closed: un hueco
de medición queda ``NOT_EVALUATED``, que nunca es PASS).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from bolsa_application.strategy_lab_phase import LabThresholds, evaluate_optimize_result
from bolsa_domain.entities.strategy_lifecycle import GateStatus, StrategyCandidate


def _candidate() -> StrategyCandidate:
    return StrategyCandidate(
        id="cand-1",
        instrument_id="AAA",
        strategy_family="sma",
        params={"fast": 20, "slow": 50},
    )


@dataclass
class _Trial:
    score: float
    oos_metrics: dict[str, Any] | None = None
    max_drawdown_pct: float | None = 4.0
    is_metrics: dict[str, Any] | None = None


@dataclass
class _Result:
    trials: list[_Trial] = field(default_factory=list)
    cpcv: dict[str, Any] | None = None
    pbo: dict[str, Any] | None = None
    walk_forward: dict[str, Any] | None = None
    edge_report: dict[str, Any] | None = None


def _p1_trial(
    *,
    net: float | None = 8.0,
    basis: str | None = "net",
    cost_bps: float | None = 32.0,
    expectancy: float | None = 15.0,
    excess: float | None = 5.0,
    closed: int | None = 60,
) -> _Trial:
    metrics: dict[str, Any] = {}
    if basis is not None:
        metrics["returnBasis"] = basis
    if net is not None:
        metrics["netReturnPct"] = net
    if cost_bps is not None:
        metrics["roundTripCostBps"] = cost_bps
    if expectancy is not None:
        metrics["expectancyCurrency"] = expectancy
    if excess is not None:
        metrics["excessReturnPct"] = excess
    if closed is not None:
        metrics["netTradeCount"] = closed
    return _Trial(
        score=1.0,
        oos_metrics={"score": 0.8},
        max_drawdown_pct=4.0,
        is_metrics=metrics,
    )


def _p1_gate_of(trial: _Trial, **thresholds: Any) -> tuple[Any, Any]:
    result = _Result(
        trials=[trial],
        cpcv={"pbo": 0.1},
        pbo={"pbo": 0.1},
        walk_forward={"walkForwardEfficiency": 0.7},
        edge_report={"dsr": 0.8, "suite": {"sampleTradesCount": 60}},
    )
    evaluation = evaluate_optimize_result(
        candidate=_candidate(),
        result=result,
        thresholds=LabThresholds(**thresholds),
    )
    return evaluation, {g.gate: g for g in evaluation.gates}["p1"]


def test_p1_passes_with_net_profit_expectancy_and_declared_friction() -> None:
    evaluation, gate = _p1_gate_of(_p1_trial())
    assert gate.status == GateStatus.PASS
    assert gate.detail == "neto_y_expectancy_positivos"
    # La evidencia que decide el gate se publica para la UI (sin re-derivarla).
    assert evaluation.metrics["netReturnPct"] == 8.0
    assert evaluation.metrics["roundTripCostBps"] == 32.0
    assert evaluation.metrics["returnBasis"] == "net"


def test_p1_never_passes_without_measured_net() -> None:
    _, gate = _p1_gate_of(_p1_trial(basis="gross", net=None))
    assert gate.status == GateStatus.NOT_EVALUATED
    assert gate.detail == "neto_no_medido"


def test_p1_fails_when_the_declared_friction_is_below_the_floor() -> None:
    _, gate = _p1_gate_of(_p1_trial(cost_bps=0.0))
    assert gate.status == GateStatus.FAIL
    assert gate.detail.startswith("coste_declarado_insuficiente")


def test_p1_fails_on_non_positive_net_even_with_good_is_score() -> None:
    _, gate = _p1_gate_of(_p1_trial(net=-1.5))
    assert gate.status == GateStatus.FAIL
    assert gate.detail == "neto_no_positivo"


def test_p1_fails_on_non_positive_expectancy() -> None:
    _, gate = _p1_gate_of(_p1_trial(expectancy=-2.0))
    assert gate.status == GateStatus.FAIL
    assert gate.detail == "expectancy_no_positiva"


def test_p1_expectancy_missing_is_not_evaluated_and_never_passes() -> None:
    _, gate = _p1_gate_of(_p1_trial(expectancy=None))
    assert gate.status == GateStatus.NOT_EVALUATED
    assert gate.detail == "expectancy_ausente"


def test_p1_without_metrics_is_not_evaluated() -> None:
    _, gate = _p1_gate_of(_Trial(score=1.0, oos_metrics={"score": 0.8}))
    assert gate.status == GateStatus.NOT_EVALUATED
    assert gate.detail == "sin_metricas"


def test_p1_friction_floor_is_configurable() -> None:
    _, gate = _p1_gate_of(_p1_trial(cost_bps=0.0), min_round_trip_cost_bps=0.0)
    assert gate.status == GateStatus.PASS


def test_p1_fails_with_insufficient_closed_trades() -> None:
    """La expectativa de dos operaciones es anécdota, no evidencia (min_trades=30)."""
    _, gate = _p1_gate_of(_p1_trial(closed=2))
    assert gate.status == GateStatus.FAIL
    assert gate.detail == "muestra_insuficiente"


def test_p1_without_net_trade_count_is_not_evaluated() -> None:
    _, gate = _p1_gate_of(_p1_trial(closed=None))
    assert gate.status == GateStatus.NOT_EVALUATED
    assert gate.detail == "trades_netos_ausentes"


def test_p1_fails_when_it_does_not_beat_buy_and_hold() -> None:
    """Ganar 5 pp mientras el benchmark paga lo mismo y gana 20 pp no es aportar valor."""
    _, gate = _p1_gate_of(_p1_trial(net=5.0, excess=-15.0))
    assert gate.status == GateStatus.FAIL
    assert gate.detail == "no_bate_benchmark"


def test_p1_without_benchmark_is_not_evaluated() -> None:
    _, gate = _p1_gate_of(_p1_trial(excess=None))
    assert gate.status == GateStatus.NOT_EVALUATED
    assert gate.detail == "exceso_ausente"


def test_p1_benchmark_component_can_be_disabled_explicitly() -> None:
    _, gate = _p1_gate_of(
        _p1_trial(net=5.0, excess=-15.0), min_excess_vs_buy_hold_pct=None
    )
    assert gate.status == GateStatus.PASS
