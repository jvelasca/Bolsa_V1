"""V2.25 / A10 — Ciclo de vida de estrategia (Strategy Lifecycle).

Modelo de dominio, puro y sin dependencias externas, del embudo que convierte un
universo ESTUDIO en una estrategia ACTIVA vigilada:

    ESTUDIO → LABORATORIO → TOP3 → COACH → FINALISTA → VALIDACION → PROMOCION
            → ACTIVE → (vigilancia; degradación → re-LAB)

Reglas de oro (auditoría V2.24, sección 20):

* Un candidato del LAB **nunca** sustituye a la estrategia activa directamente.
* Cada transición avanza SOLO si el gate previo está PASS; si no, se queda y se
  dice por qué (``TransitionResult.reasons``).
* El COACH es *advisory*: puede vetar o degradar, jamás aprobar por encima de un
  gate cuantitativo.
* ``StrategyVersion`` es inmutable: una versión publicada no se reescribe, se crea
  otra.
* Fail-closed: sin evidencia suficiente no hay promoción.

Este módulo no toca DB ni ejecuta backtests: define tipos, invariantes y la
máquina de estados. La orquestación (V2.26) y la persistencia viven fuera.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class StrategyLifecycleState(StrEnum):
    """Estados del ciclo de vida de una estrategia/candidata."""

    ESTUDIO = "estudio"
    LABORATORIO = "laboratorio"
    TOP3 = "top3"
    COACH = "coach"
    FINALISTA = "finalista"
    VALIDACION = "validacion"
    PROMOCION = "promocion"
    ACTIVE = "active"
    REJECTED = "rejected"  # terminal: la evidencia no sostiene el avance.
    DEGRADED = "degraded"  # la activa pierde salud ⇒ vuelve al LAB (no swap directo).


# Orden lineal del embudo (REJECTED/DEGRADED se tratan aparte).
_ORDER: tuple[StrategyLifecycleState, ...] = (
    StrategyLifecycleState.ESTUDIO,
    StrategyLifecycleState.LABORATORIO,
    StrategyLifecycleState.TOP3,
    StrategyLifecycleState.COACH,
    StrategyLifecycleState.FINALISTA,
    StrategyLifecycleState.VALIDACION,
    StrategyLifecycleState.PROMOCION,
    StrategyLifecycleState.ACTIVE,
)


def next_state(state: StrategyLifecycleState) -> StrategyLifecycleState | None:
    """Siguiente estado del embudo (``None`` si es terminal o ACTIVE)."""
    if state not in _ORDER:
        return None
    idx = _ORDER.index(state)
    if idx + 1 >= len(_ORDER):
        return None
    return _ORDER[idx + 1]


class GateStatus(StrEnum):
    """Resultado de un gate cuantitativo/analítico."""

    PASS = "pass"
    FAIL = "fail"
    NOT_EVALUATED = "not_evaluated"  # fail-closed: no evaluado NO es PASS.


@dataclass(frozen=True, slots=True)
class GateResult:
    """Veredicto de un gate concreto (evidencia auditable)."""

    gate: str
    status: GateStatus
    detail: str | None = None
    metrics: dict[str, Any] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return self.status == GateStatus.PASS

    @classmethod
    def passed_gate(cls, gate: str, detail: str | None = None) -> GateResult:
        return cls(gate=gate, status=GateStatus.PASS, detail=detail)

    @classmethod
    def failed(cls, gate: str, detail: str | None = None) -> GateResult:
        return cls(gate=gate, status=GateStatus.FAIL, detail=detail)


# Los seis gates del Promotion Gate (V2.25 · Fase 7). Todos deben ser PASS.
PROMOTION_GATES: tuple[str, ...] = (
    "backtest",
    "robustness",
    "walk_forward",
    "oos",
    "risk",
    "coach",
)


@dataclass(frozen=True, slots=True)
class StrategyCandidate:
    """Idea de estrategia para un instrumento/familia, aún sin validar (ESTUDIO→LAB)."""

    id: str
    instrument_id: str
    strategy_family: str
    params: dict[str, Any]
    origin: str = "estudio"
    data_snapshot_id: str | None = None
    preset_key: str | None = None
    created_at: str | None = None
    strategy_definition_id: str | None = None
    state: StrategyLifecycleState = StrategyLifecycleState.ESTUDIO


@dataclass(frozen=True, slots=True)
class StrategyEvaluation:
    """Resultado de evaluar un candidato en el LABORATORIO (backtest/OOS/robustez)."""

    candidate_id: str
    score: float
    gates: tuple[GateResult, ...] = ()
    trial_ids: tuple[str, ...] = ()
    optimization_run_id: str | None = None
    edge_report_id: str | None = None
    metrics: dict[str, Any] = field(default_factory=dict)

    @property
    def gates_passed(self) -> bool:
        """True solo si TODOS los gates evaluados pasan y hay al menos uno."""
        if not self.gates:
            return False
        return all(g.passed for g in self.gates)


@dataclass(frozen=True, slots=True)
class StrategyTop3:
    """Selección por evidencia de los tres mejores candidatos de un ámbito."""

    instrument_id: str
    candidate_ids: tuple[str, ...]
    scores: tuple[float, ...] = ()

    def __post_init__(self) -> None:
        if len(self.candidate_ids) > 3:
            raise ValueError("StrategyTop3 admite como máximo 3 candidatos")
        if self.scores and len(self.scores) != len(self.candidate_ids):
            raise ValueError("scores y candidate_ids deben tener la misma longitud")


@dataclass(frozen=True, slots=True)
class CoachAssessment:
    """Dictamen del COACH (advisory). No puede saltarse los gates cuantitativos."""

    candidate_id: str
    approved: bool
    headline: str | None = None
    coherence: GateStatus = GateStatus.NOT_EVALUATED
    complementarity: GateStatus = GateStatus.NOT_EVALUATED
    regime_fit: GateStatus = GateStatus.NOT_EVALUATED
    contradictions: tuple[str, ...] = ()
    facts: tuple[str, ...] = ()

    @property
    def vetoes(self) -> bool:
        """El COACH veta cuando no aprueba o declara contradicciones."""
        return (not self.approved) or bool(self.contradictions)


@dataclass(frozen=True, slots=True)
class StrategyFinalist:
    """Candidato finalista con versión inmutable lista para validación/promoción."""

    candidate_id: str
    version_id: str
    name: str
    definition_hash: str
    definition: dict[str, Any]
    created_at: str | None = None


@dataclass(frozen=True, slots=True)
class StrategyValidation:
    """Validación formal del finalista (mismos seis gates, evidencia enlazada)."""

    finalist_id: str
    gates: tuple[GateResult, ...]

    @property
    def passed(self) -> bool:
        present = {g.gate for g in self.gates if g.passed}
        return all(gate in present for gate in PROMOTION_GATES)

    @property
    def missing_gates(self) -> tuple[str, ...]:
        present = {g.gate for g in self.gates if g.passed}
        return tuple(gate for gate in PROMOTION_GATES if gate not in present)


@dataclass(frozen=True, slots=True)
class StrategyPromotion:
    """Promoción (o rechazo) de un finalista a ACTIVE, con su porqué auditable."""

    finalist_id: str
    promoted: bool
    reasons: tuple[str, ...] = ()
    shadow_validated: bool = False
    promoted_at: str | None = None


@dataclass(frozen=True, slots=True)
class ActiveStrategy:
    """Estrategia ACTIVE (versión inmutable) sujeta a vigilancia."""

    version_id: str
    candidate_id: str
    instrument_id: str
    name: str
    definition: dict[str, Any]
    promoted_at: str | None = None


@dataclass(frozen=True, slots=True)
class StrategyHealth:
    """Salud de una estrategia ACTIVA en un instante (serie temporal fuera).

    V2.28 / A10: además de los indicadores *predictivos* de robustez (``edge``/``wfe``/
    ``dsr``/``credibility``, derivados del LAB), puede llevar el bloque *observado* de la
    ejecución SIM real (``observed_*``), que responde a otra pregunta: «¿qué está pasando
    de verdad con el dinero?». Los umbrales observados viven en ``thresholds`` con prefijo
    ``observed_``. El bloque observado solo degrada cuando hay evidencia suficiente
    (``observed_trades >= min_observed_trades``): no se degrada una estrategia por ruido
    de uno o dos trades.
    """

    version_id: str
    as_of: str
    edge: float | None = None
    walk_forward_efficiency: float | None = None
    dsr: float | None = None
    credibility: float | None = None
    thresholds: dict[str, float] = field(default_factory=dict)
    # --- Bloque observado (ejecución SIM real; V2.28 / A10) ---
    observed_return_pct: float | None = None
    observed_max_drawdown_pct: float | None = None
    observed_win_rate: float | None = None
    observed_profit_factor: float | None = None
    observed_trades: int | None = None

    @property
    def degraded(self) -> bool:
        """True si algún indicador conocido cae por debajo de su umbral.

        Los indicadores predictivos degradan siempre que estén presentes. El bloque
        observado exige además evidencia mínima (``min_observed_trades``) para no
        degradar por una muestra anecdótica.
        """
        checks = (
            ("edge", self.edge),
            ("walk_forward_efficiency", self.walk_forward_efficiency),
            ("dsr", self.dsr),
            ("credibility", self.credibility),
        )
        for key, value in checks:
            threshold = self.thresholds.get(key)
            if value is not None and threshold is not None and value < threshold:
                return True
        return self.observed_degraded

    @property
    def observed_degraded(self) -> bool:
        """Degradación por métricas observadas, con guarda de muestra mínima.

        Semántica de umbral por métrica: retorno/win-rate/profit-factor son MÍNIMOS (se
        degrada por debajo); el drawdown es un TECHO (se degrada por encima), porque una
        caída grande es lo malo. Público porque el dict de motivos lo consulta la capa de
        aplicación para poblar ``breaches``.
        """
        if self.observed_trades is None:
            return False
        min_trades = self.thresholds.get("min_observed_trades")
        if min_trades is not None and self.observed_trades < min_trades:
            # Muestra insuficiente: el observado es informativo, no decisorio.
            return False
        minimums = (
            ("observed_return_pct", self.observed_return_pct),
            ("observed_win_rate", self.observed_win_rate),
            ("observed_profit_factor", self.observed_profit_factor),
        )
        for key, value in minimums:
            threshold = self.thresholds.get(key)
            if value is not None and threshold is not None and value < threshold:
                return True
        max_dd = self.thresholds.get("observed_max_drawdown_pct")
        if (
            max_dd is not None
            and self.observed_max_drawdown_pct is not None
            and self.observed_max_drawdown_pct > max_dd
        ):
            return True
        return False


@dataclass(frozen=True, slots=True)
class TransitionResult:
    """Resultado de intentar avanzar de estado: autorizado o no, con motivos."""

    from_state: StrategyLifecycleState
    to_state: StrategyLifecycleState | None
    allowed: bool
    reasons: tuple[str, ...] = ()


def evaluate_promotion(
    *,
    finalist: StrategyFinalist,
    validation: StrategyValidation,
    coach: CoachAssessment,
    shadow_validated: bool,
) -> StrategyPromotion:
    """Promotion Gate (V2.25 · Fase 6): decide si un finalista puede ser ACTIVE.

    Exige, en este orden:

    1. Los SEIS gates cuantitativos en PASS (``validation.passed``).
    2. El COACH sin veto (un veto del COACH bloquea aunque los gates pasen).
    3. Validación en shadow/paper (anti strategy-chasing): sin ella, no promoción.
    """
    reasons: list[str] = []
    missing = validation.missing_gates
    if missing:
        reasons.append(f"gates_no_superados:{','.join(missing)}")
    if coach.vetoes:
        reasons.append("coach_veto")
    if not shadow_validated:
        reasons.append("shadow_validation_requerida")
    promoted = not reasons
    return StrategyPromotion(
        finalist_id=finalist.version_id,
        promoted=promoted,
        reasons=tuple(reasons),
        shadow_validated=shadow_validated,
    )


def can_transition(
    *,
    state: StrategyLifecycleState,
    gates: tuple[GateResult, ...] = (),
    coach: CoachAssessment | None = None,
    validation: StrategyValidation | None = None,
    shadow_validated: bool = False,
) -> TransitionResult:
    """Máquina de estados: ¿puede avanzar desde ``state`` y con qué motivos?

    Fail-closed y explícita: cada paso exige su condición y devuelve los motivos de
    bloqueo. No ejecuta efectos; solo decide.
    """
    target = next_state(state)
    if state in {StrategyLifecycleState.REJECTED, StrategyLifecycleState.ACTIVE}:
        return TransitionResult(
            from_state=state,
            to_state=None,
            allowed=False,
            reasons=("estado_terminal_o_active",),
        )

    # Estados intermedios del embudo: basta con tener los gates del paso en PASS.
    if state in {
        StrategyLifecycleState.ESTUDIO,
        StrategyLifecycleState.LABORATORIO,
        StrategyLifecycleState.TOP3,
        StrategyLifecycleState.COACH,
        StrategyLifecycleState.FINALISTA,
    }:
        failed = tuple(g.gate for g in gates if not g.passed)
        if gates and failed:
            return TransitionResult(state, target, False, (f"gates_fallidos:{','.join(failed)}",))
        if state == StrategyLifecycleState.COACH and coach is not None and coach.vetoes:
            return TransitionResult(state, target, False, ("coach_veto",))
        return TransitionResult(state, target, True)

    if state == StrategyLifecycleState.VALIDACION:
        if validation is None:
            return TransitionResult(state, target, False, ("validacion_ausente",))
        if not validation.passed:
            return TransitionResult(
                state,
                target,
                False,
                (f"gates_no_superados:{','.join(validation.missing_gates)}",),
            )
        if not shadow_validated:
            return TransitionResult(state, target, False, ("shadow_validation_requerida",))
        return TransitionResult(state, target, True)

    if state == StrategyLifecycleState.PROMOCION:
        return TransitionResult(state, StrategyLifecycleState.ACTIVE, True)

    if state == StrategyLifecycleState.DEGRADED:
        # Degradación vuelve al LAB (nunca swap directo de la activa).
        return TransitionResult(state, StrategyLifecycleState.LABORATORIO, True)

    return TransitionResult(state, target, False, ("estado_desconocido",))


__all__ = [
    "PROMOTION_GATES",
    "ActiveStrategy",
    "CoachAssessment",
    "GateResult",
    "GateStatus",
    "StrategyCandidate",
    "StrategyEvaluation",
    "StrategyFinalist",
    "StrategyHealth",
    "StrategyLifecycleState",
    "StrategyPromotion",
    "StrategyTop3",
    "StrategyValidation",
    "TransitionResult",
    "can_transition",
    "evaluate_promotion",
    "next_state",
]
