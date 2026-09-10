"""V2.25 / A10 — fases TOP 3 y COACH del Strategy Lifecycle.

* **TOP 3** (``select_top3``): selecciona los tres mejores candidatos por **evidencia**
  (score + robustez), nunca por opinión. Cada slot lleva su ``runId`` (requisito del
  Camino A: un TOP ``lab_validated``/``active`` sin runId se rechaza) reutilizando
  ``assert_lab_validated_slots_have_run_id``.
* **COACH** (``assess_with_coach``): dictamen *offline/advisory* sobre la evidencia ya
  calculada. Reglas deterministas sobre métricas (coherencia, complementariedad,
  régimen). El COACH **solo puede vetar o degradar**: nunca convierte un FAIL
  cuantitativo en PASS. El LLM opcional (prompt ``prompt_backtest_coach_v1``) es
  offline y su salida se trata como advisory, no como gate.

Sin red, sin IA en el hot path, sin DB: transformaciones deterministas que la
orquestación (V2.26) encadena.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from bolsa_domain.entities.strategy_lifecycle import (
    CoachAssessment,
    GateStatus,
    StrategyEvaluation,
    StrategyTop3,
)

__all__ = [
    "CoachThresholds",
    "Top3Selection",
    "assess_with_coach",
    "select_top3",
]


def _rank_key(evaluation: StrategyEvaluation) -> tuple[float, float, float]:
    """Orden por evidencia: score, luego nº de gates PASS, luego robustez (PBO)."""
    passed = sum(1 for g in evaluation.gates if g.passed)
    pbo = evaluation.metrics.get("pbo")
    # Menos PBO es mejor ⇒ se ordena por -pbo; ausente ⇒ 1.0 (peor caso).
    pbo_rank = -(float(pbo) if isinstance(pbo, (int, float)) else 1.0)
    return (float(evaluation.score), float(passed), pbo_rank)


@dataclass(frozen=True, slots=True)
class Top3Selection:
    """Resultado de la fase TOP 3 (ranking por evidencia + slots con runId)."""

    top: StrategyTop3
    slots: tuple[dict[str, Any], ...] = ()
    rejected: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return bool(self.top.candidate_ids)


def select_top3(
    *,
    instrument_id: str,
    evaluations: Sequence[StrategyEvaluation],
    run_id: str,
    min_score: float = 0.0,
    max_candidates: int = 3,
    timeframe: str = "1d",
) -> Top3Selection:
    """Fase TOP 3: ranking por evidencia con ``runId`` por slot.

    Descarta candidatas sin gate ``backtest`` PASS o por debajo de ``min_score``
    (fail-closed: sin evidencia no entran en el TOP). Los slots resultantes cumplen
    el requisito de ``runId`` para poder publicarse como ``lab_validated``.
    """
    eligible: list[StrategyEvaluation] = []
    rejected: list[str] = []
    for evaluation in evaluations:
        backtest_ok = any(g.gate == "backtest" and g.passed for g in evaluation.gates)
        if not backtest_ok or float(evaluation.score) < min_score:
            rejected.append(evaluation.candidate_id)
            continue
        eligible.append(evaluation)

    eligible.sort(key=_rank_key, reverse=True)
    selected = eligible[: max(1, min(max_candidates, 3))]
    candidate_ids = tuple(e.candidate_id for e in selected)
    scores = tuple(float(e.score) for e in selected)
    slots = tuple(
        {
            "rank": rank,
            "candidateId": evaluation.candidate_id,
            "instrumentId": instrument_id,
            "timeframe": timeframe,
            "runId": run_id,
            "score": float(evaluation.score),
            "evidenceLevel": _evidence_level(evaluation),
        }
        for rank, evaluation in enumerate(selected, start=1)
    )
    return Top3Selection(
        top=StrategyTop3(instrument_id=instrument_id, candidate_ids=candidate_ids, scores=scores),
        slots=slots,
        rejected=tuple(rejected),
    )


def _evidence_level(evaluation: StrategyEvaluation) -> str:
    """Nivel de evidencia por gates PASS (honesto: in_sample_only si falta OOS)."""
    passed = {g.gate for g in evaluation.gates if g.passed}
    if {"backtest", "oos", "walk_forward", "robustness"} <= passed:
        return "lab_validated"
    if "backtest" in passed and "oos" in passed:
        return "oos_validated"
    return "in_sample_only"


@dataclass(frozen=True, slots=True)
class CoachThresholds:
    """Umbrales del COACH (advisory determinista)."""

    min_credibility: float = 0.0
    max_pbo: float = 1.0
    regime_fit_required: bool = False
    extra: dict[str, Any] = field(default_factory=dict)


def _status(ok: bool) -> GateStatus:
    return GateStatus.PASS if ok else GateStatus.FAIL


def assess_with_coach(
    *,
    evaluation: StrategyEvaluation,
    thresholds: CoachThresholds | None = None,
    expected_regime: str | None = None,
    recognized_regimes: Sequence[str] = (),
    contradicts_active: bool = False,
) -> CoachAssessment:
    """Fase COACH: dictamen advisory determinista sobre la evidencia del LAB.

    Reglas (todas advisory, solo pueden vetar/degradar):

    * **coherence** — la evaluación tiene evidencia coherente (backtest PASS y métricas).
    * **complementarity** — no contradice la estrategia activa (``contradicts_active``).
    * **regime_fit** — si se exige, el régimen esperado debe estar entre los conocidos.
    * **veto** — contradicciones explícitas o FAIL de coherencia ⇒ ``approved=False``.

    Nunca eleva un gate cuantitativo FAIL a PASS: devuelve un ``CoachAssessment`` que
    el Promotion Gate trata como uno más.
    """
    th = thresholds or CoachThresholds()
    passed = {g.gate for g in evaluation.gates if g.passed}
    contradictions: list[str] = []

    coherence_ok = "backtest" in passed and bool(evaluation.metrics)
    if not coherence_ok:
        contradictions.append("evidencia_incoherente")

    complementarity_ok = not contradicts_active
    if not complementarity_ok:
        contradictions.append("contradice_estrategia_activa")

    regime_ok = True
    if th.regime_fit_required:
        regime_ok = bool(expected_regime) and expected_regime in set(recognized_regimes)
        if not regime_ok:
            contradictions.append("regimen_no_reconocido")

    pbo = evaluation.metrics.get("pbo")
    if isinstance(pbo, (int, float)) and float(pbo) > th.max_pbo:
        contradictions.append("pbo_alto")

    credibility = evaluation.metrics.get("credibility")
    if isinstance(credibility, (int, float)) and float(credibility) < th.min_credibility:
        contradictions.append("credibilidad_baja")

    approved = not contradictions
    facts = tuple(
        f"{key}={evaluation.metrics.get(key)}"
        for key in ("is_score", "oos_score", "wfe", "pbo", "dsr")
        if evaluation.metrics.get(key) is not None
    )
    return CoachAssessment(
        candidate_id=evaluation.candidate_id,
        approved=approved,
        headline=(
            "Evidencia coherente y complementaria"
            if approved
            else "Dictamen del COACH: " + ", ".join(contradictions)
        ),
        coherence=_status(coherence_ok),
        complementarity=_status(complementarity_ok),
        regime_fit=_status(regime_ok),
        contradictions=tuple(contradictions),
        facts=facts,
    )
