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
    "Top3CoachVerdict",
    "assess_top3_with_coach",
    "assess_with_coach",
    "select_top3",
]


def _finite(value: Any) -> float | None:
    """Devuelve ``value`` como float finito, o ``None`` (fail-closed: ausente/no finito)."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        if number != number or number in (float("inf"), float("-inf")):
            return None
        return number
    return None


def _evidence_precedence(evaluation: StrategyEvaluation) -> int:
    """Nivel de evidencia como orden: lab_validated > oos_validated > in_sample_only."""
    return {
        "lab_validated": 2,
        "oos_validated": 1,
        "in_sample_only": 0,
    }.get(_evidence_level(evaluation), 0)


def _rank_key(
    evaluation: StrategyEvaluation,
    *,
    expected_regime: str | None = None,
) -> tuple[float, int, float, float, float, float]:
    """Clave de ranking por evidencia robusta fuera de muestra (no IS puro).

    Orden lexicográfico descendente:

    1. ``edge``     — OOS score si está medido; si no, IS (fallback in_sample_only).
    2. ``evidence`` — lab_validated > oos_validated > in_sample_only.
    3. ``wfe``      — walk-forward efficiency (ausente ⇒ -inf).
    4. ``dsr``      — deflated Sharpe ratio (ausente ⇒ -inf).
    5. ``-pbo``     — menos overfit (ausente ⇒ -1.0, peor caso).
    6. ``regime_match`` — 1.0 si el régimen coincide con el esperado, else 0.0.
    """
    metrics = evaluation.metrics
    oos = _finite(metrics.get("oos_score"))
    edge = oos if oos is not None else float(evaluation.score)
    wfe = _finite(metrics.get("wfe"))
    dsr = _finite(metrics.get("dsr"))
    pbo = _finite(metrics.get("pbo"))
    wfe_rank = wfe if wfe is not None else float("-inf")
    dsr_rank = dsr if dsr is not None else float("-inf")
    pbo_rank = -(pbo if pbo is not None else 1.0)
    regime_match = 0.0
    if expected_regime:
        candidate_regime = metrics.get("regime")
        if isinstance(candidate_regime, str) and candidate_regime.strip():
            regime_match = (
                1.0 if candidate_regime.strip() == str(expected_regime).strip() else 0.0
            )
    return (edge, _evidence_precedence(evaluation), wfe_rank, dsr_rank, pbo_rank, regime_match)


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
    expected_regime: str | None = None,
    min_gates: tuple[str, ...] = ("backtest",),
) -> Top3Selection:
    """Fase TOP 3: ranking por evidencia robusta con ``runId`` por slot.

    Descarta candidatas sin los gates mínimos en PASS (por defecto ``backtest``) o por
    debajo de ``min_score`` (fail-closed: sin evidencia no entran en el TOP). El ranking
    ya **no** se ordena por el IS puro: prefiere la evidencia fuera de muestra
    (``oos_score`` → ``wfe`` → ``dsr`` → ``1 - pbo`` → ``regime_match``) y degrada las
    hipótesis ``in_sample_only`` frente a las ``lab_validated``.

    ``min_gates`` eleva la barrera de evidencia cuando se exige (p. ej.
    ``("backtest", "oos", "walk_forward", "robustness")``); por defecto se mantiene el
    mínimo histórico para no romper el flujo ``semifinal``/in_sample_only. Los slots
    resultantes cumplen el requisito de ``runId`` para poder publicarse como
    ``lab_validated``.
    """
    eligible: list[StrategyEvaluation] = []
    rejected: list[str] = []
    for evaluation in evaluations:
        passed_gates = {g.gate for g in evaluation.gates if g.passed}
        gates_ok = all(gate in passed_gates for gate in min_gates)
        if not gates_ok or float(evaluation.score) < min_score:
            rejected.append(evaluation.candidate_id)
            continue
        eligible.append(evaluation)

    eligible.sort(key=lambda e: _rank_key(e, expected_regime=expected_regime), reverse=True)
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
class Top3CoachVerdict:
    """V2.29 — dictamen COACH comparativo sobre el TOP3 completo.

    El ranking del TOP3 lo fija la evidencia (``select_top3``); este dictamen **no lo
    reordena**: recorre el ranking en orden y elige el **primer candidato sin veto**
    (``selected_id``). Si todos están vetados, ``approved_id`` es ``None`` y la
    orquestación corta con ``coach_veto`` (fail-closed).
    """

    assessments: tuple[CoachAssessment, ...]
    selected_id: str | None = None
    rejected_ids: tuple[str, ...] = ()

    @property
    def all_vetoed(self) -> bool:
        return self.selected_id is None

    @property
    def contradictions(self) -> tuple[str, ...]:
        """Contradicciones agregadas de todos los dictámenes (para el motivo de veto)."""
        out: list[str] = []
        for assessment in self.assessments:
            out.extend(assessment.contradictions)
        return tuple(out)


def assess_top3_with_coach(
    *,
    selection: Top3Selection,
    evaluations: Sequence[StrategyEvaluation],
    thresholds: CoachThresholds | None = None,
    expected_regime: str | None = None,
    recognized_regimes: Sequence[str] = (),
    contradicts_active: bool = False,
) -> Top3CoachVerdict:
    """V2.29 — COACH comparativo: dictamina los tres candidatos del TOP3.

    Recorre ``selection.top.candidate_ids`` **en el orden de ranking por evidencia** y
    devuelve un ``CoachAssessment`` por candidato. No reordena ni "elige al mejor
    número": el primero sin veto gana. Un candidato del TOP3 sin evaluación asociada
    se registra como vetado (nunca se inventa evidencia).
    """
    by_id = {e.candidate_id: e for e in evaluations}
    assessments: list[CoachAssessment] = []
    selected_id: str | None = None
    rejected: list[str] = []

    for candidate_id in selection.top.candidate_ids:
        evaluation = by_id.get(candidate_id)
        if evaluation is None:
            rejected.append(candidate_id)
            continue
        assessment = assess_with_coach(
            evaluation=evaluation,
            thresholds=thresholds,
            expected_regime=expected_regime,
            recognized_regimes=recognized_regimes,
            contradicts_active=contradicts_active,
        )
        assessments.append(assessment)
        if assessment.vetoes:
            rejected.append(candidate_id)
        elif selected_id is None:
            selected_id = candidate_id

    return Top3CoachVerdict(
        assessments=tuple(assessments),
        selected_id=selected_id,
        rejected_ids=tuple(rejected),
    )


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
