"""V2.25 / A10 — fases TOP 3 y COACH (tests herméticos).

Certifica que el TOP 3 es por evidencia (no opinión) y exige ``runId`` por slot, y
que el COACH es advisory: solo veta/degrada, jamás aprueba por encima de los gates.
"""

from __future__ import annotations

from bolsa_application.strategy_top3_coach_phase import (
    CoachThresholds,
    assess_with_coach,
    select_top3,
)
from bolsa_domain.entities.strategy_lifecycle import (
    CoachAssessment,
    GateResult,
    GateStatus,
    StrategyEvaluation,
)


def _evaluation(
    candidate_id: str,
    *,
    score: float,
    gates: tuple[str, ...] = ("backtest", "oos"),
    pbo: float | None = None,
) -> StrategyEvaluation:
    metrics = {"instrument_id": "AAA"}
    if pbo is not None:
        metrics["pbo"] = pbo
    return StrategyEvaluation(
        candidate_id=candidate_id,
        score=score,
        gates=tuple(GateResult.passed_gate(g) for g in gates),
        metrics=metrics,
    )


# ── TOP 3 ───────────────────────────────────────────────────────────────────────


def test_top3_ranks_by_evidence_not_input_order() -> None:
    selection = select_top3(
        instrument_id="AAA",
        run_id="run-1",
        evaluations=[
            _evaluation("c-low", score=0.5),
            _evaluation("c-high", score=2.0),
            _evaluation("c-mid", score=1.0),
        ],
    )
    assert selection.top.candidate_ids == ("c-high", "c-mid", "c-low")
    assert [s["rank"] for s in selection.slots] == [1, 2, 3]
    assert all(s["runId"] == "run-1" for s in selection.slots)


def test_top3_excludes_candidates_without_backtest_pass() -> None:
    no_gates = StrategyEvaluation(candidate_id="c-none", score=9.0, gates=())
    failed_backtest = StrategyEvaluation(
        candidate_id="c-fail",
        score=8.0,
        gates=(GateResult.failed("backtest"),),
    )
    selection = select_top3(
        instrument_id="AAA",
        run_id="run-1",
        evaluations=[_evaluation("c-ok", score=1.0), no_gates, failed_backtest],
    )
    assert selection.top.candidate_ids == ("c-ok",)
    assert set(selection.rejected) == {"c-none", "c-fail"}


def test_top3_caps_at_three() -> None:
    evaluations = [_evaluation(f"c{i}", score=float(i)) for i in range(5)]
    selection = select_top3(instrument_id="AAA", run_id="run-1", evaluations=evaluations)
    assert len(selection.top.candidate_ids) == 3


def test_top3_evidence_level_reflects_gates() -> None:
    selection = select_top3(
        instrument_id="AAA",
        run_id="run-1",
        evaluations=[
            _evaluation(
                "c-full",
                score=2.0,
                gates=("backtest", "oos", "walk_forward", "robustness"),
            )
        ],
    )
    assert selection.slots[0]["evidenceLevel"] == "lab_validated"


# ── COACH ───────────────────────────────────────────────────────────────────────


def test_coach_approves_coherent_evidence() -> None:
    assessment = assess_with_coach(evaluation=_evaluation("c1", score=1.0))
    assert assessment.approved
    assert not assessment.vetoes
    assert assessment.coherence == GateStatus.PASS


def test_coach_vetoes_incoherent_evidence() -> None:
    empty = StrategyEvaluation(candidate_id="c1", score=1.0, gates=(), metrics={})
    assessment = assess_with_coach(evaluation=empty)
    assert not assessment.approved
    assert assessment.vetoes
    assert "evidencia_incoherente" in assessment.contradictions


def test_coach_vetoes_when_contradicts_active() -> None:
    assessment = assess_with_coach(
        evaluation=_evaluation("c1", score=1.0),
        contradicts_active=True,
    )
    assert not assessment.approved
    assert "contradice_estrategia_activa" in assessment.contradictions


def test_coach_regime_fit_can_be_required() -> None:
    assessment = assess_with_coach(
        evaluation=_evaluation("c1", score=1.0),
        thresholds=CoachThresholds(regime_fit_required=True),
        expected_regime="trend",
        recognized_regimes=("range",),
    )
    assert not assessment.approved
    assert "regimen_no_reconocido" in assessment.contradictions


def test_coach_high_pbo_degrades() -> None:
    assessment = assess_with_coach(
        evaluation=_evaluation("c1", score=1.0, pbo=0.9),
        thresholds=CoachThresholds(max_pbo=0.3),
    )
    assert not assessment.approved
    assert "pbo_alto" in assessment.contradictions


def test_coach_never_upgrades_quantitative_fail() -> None:
    """Aunque el COACH apruebe, un gate cuantitativo FAIL no se convierte en PASS."""
    from bolsa_domain.entities.strategy_lifecycle import (
        PROMOTION_GATES,
        StrategyFinalist,
        StrategyValidation,
        evaluate_promotion,
    )

    evaluation = _evaluation("c1", score=1.0, gates=("backtest",))
    assessment = assess_with_coach(evaluation=evaluation)
    assert assessment.approved  # el COACH no ve el hueco de OOS como contradicción
    validation = StrategyValidation(
        finalist_id="ver-1",
        gates=(
            GateResult.passed_gate("backtest"),
            *(
                GateResult.failed(g)
                for g in PROMOTION_GATES
                if g not in {"backtest", "coach"}
            ),
        ),
    )
    promo = evaluate_promotion(
        finalist=StrategyFinalist(
            candidate_id="c1",
            version_id="ver-1",
            name="x",
            definition_hash="h",
            definition={},
        ),
        validation=validation,
        coach=CoachAssessment(candidate_id="c1", approved=True),
        shadow_validated=True,
    )
    assert not promo.promoted  # los gates cuantitativos mandan
