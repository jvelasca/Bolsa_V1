"""V2.25 / A10 — fases ESTUDIO y LABORATORIO (tests herméticos).

Certifica que ESTUDIO convierte un universo resuelto en candidatas reproducibles
(sin inventar cuando el universo está vacío/no disponible) y que LABORATORIO traduce
un resultado real de optimización en gates fail-closed (NOT_EVALUATED ≠ PASS).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from bolsa_application.strategy_lab_phase import (
    LabThresholds,
    build_estudio_candidates,
    evaluate_optimize_result,
    gate_from_metrics,
)
from bolsa_domain.entities.strategy_lifecycle import GateStatus, StrategyCandidate


@dataclass
class _Resolution:
    status: str
    instrument_ids: list[str] = field(default_factory=list)


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
    max_drawdown_pct: float | None = 5.0


@dataclass
class _Result:
    trials: list[_Trial] = field(default_factory=list)
    cpcv: dict[str, Any] | None = None
    pbo: dict[str, Any] | None = None
    walk_forward: dict[str, Any] | None = None
    edge_report: dict[str, Any] | None = None


# ── ESTUDIO ─────────────────────────────────────────────────────────────────────


def test_estudio_unavailable_produces_nothing() -> None:
    plan = build_estudio_candidates(
        resolution=_Resolution(status="unavailable"),
        strategy_family="sma",
        params={"fast": 20, "slow": 50},
    )
    assert plan.status == "unavailable"
    assert plan.candidates == ()
    assert not plan.ok


def test_estudio_empty_is_not_error() -> None:
    plan = build_estudio_candidates(
        resolution=_Resolution(status="empty"),
        strategy_family="sma",
        params={},
    )
    assert plan.status == "empty"
    assert plan.candidates == ()


def test_estudio_ok_builds_reproducible_candidates() -> None:
    plan = build_estudio_candidates(
        resolution=_Resolution(status="ok", instrument_ids=["AAA", "BBB"]),
        strategy_family="sma",
        params={"fast": 20, "slow": 50},
        data_snapshot_id="snap-1",
        max_candidates=1,
    )
    assert plan.ok
    assert len(plan.candidates) == 1  # max_candidates respetado
    cand = plan.candidates[0]
    assert cand.instrument_id == "AAA"
    assert cand.data_snapshot_id == "snap-1"
    assert cand.strategy_family == "sma_crossover"  # familia normalizada


# ── LABORATORIO ─────────────────────────────────────────────────────────────────


def test_lab_without_trials_is_fail_closed() -> None:
    evaluation = evaluate_optimize_result(candidate=_candidate(), result=_Result())
    by_gate = {g.gate: g for g in evaluation.gates}
    assert by_gate["backtest"].status == GateStatus.FAIL  # sin campeón
    assert by_gate["oos"].status == GateStatus.NOT_EVALUATED
    assert by_gate["walk_forward"].status == GateStatus.NOT_EVALUATED
    assert by_gate["robustness"].status == GateStatus.NOT_EVALUATED
    assert by_gate["coach"].status == GateStatus.NOT_EVALUATED
    assert evaluation.gates_passed is False  # NOT_EVALUATED nunca cuenta como PASS


def test_lab_full_evidence_passes_quantitative_gates() -> None:
    result = _Result(
        trials=[
            _Trial(score=1.0, oos_metrics={"score": 0.8}, max_drawdown_pct=5.0),
            _Trial(score=1.5, oos_metrics={"score": 0.9}, max_drawdown_pct=4.0),
        ],
        cpcv={"pbo": 0.1},
        pbo={"pbo": 0.1},
        walk_forward={"walkForwardEfficiency": 0.7},
        edge_report={"dsr": 0.5},
    )
    evaluation = evaluate_optimize_result(
        candidate=_candidate(),
        result=result,
        thresholds=LabThresholds(min_oos_score=0.2, min_wfe=0.3, max_pbo=0.3, min_dsr=0.0),
    )
    by_gate = {g.gate: g for g in evaluation.gates}
    assert by_gate["backtest"].passed
    assert by_gate["robustness"].passed
    assert by_gate["walk_forward"].passed
    assert by_gate["oos"].passed
    assert by_gate["risk"].passed
    assert by_gate["dsr"].passed
    # El COACH sigue pendiente (lo decide su fase), así que no todo gate está PASS.
    assert by_gate["coach"].status == GateStatus.NOT_EVALUATED
    assert evaluation.score == 1.5  # campeón por score IS
    assert evaluation.metrics["oos_score"] == 0.9


def test_lab_high_pbo_fails_robustness() -> None:
    result = _Result(
        trials=[_Trial(score=1.0, oos_metrics={"score": 0.8})],
        cpcv={"pbo": 0.9},
        pbo={"pbo": 0.9},
        walk_forward={"wfe": 0.7},
    )
    evaluation = evaluate_optimize_result(
        candidate=_candidate(),
        result=result,
        thresholds=LabThresholds(max_pbo=0.3),
    )
    by_gate = {g.gate: g for g in evaluation.gates}
    assert by_gate["robustness"].status == GateStatus.FAIL


def test_gate_from_metrics_fail_closed() -> None:
    assert gate_from_metrics("x", None).status == GateStatus.NOT_EVALUATED
    assert gate_from_metrics("x", {}).status == GateStatus.NOT_EVALUATED
    assert gate_from_metrics("x", {"score": "n/a"}).status == GateStatus.NOT_EVALUATED
    assert gate_from_metrics("x", {"score": 0.5}, min_value=0.4).status == GateStatus.PASS
    assert gate_from_metrics("x", {"score": 0.1}, min_value=0.4).status == GateStatus.FAIL
