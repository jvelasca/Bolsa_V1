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
class ShadowValidationResult:
    """Evidencia shadow/paper *ejecutada* de un finalista (V2.32 / A12).

    Sustituye al flag ``AUTO_ORCHESTRATOR_SHADOW_VALIDATED`` como autoridad del
    Promotion Gate: la promoción exige un resultado con evidencia contable (trades
    ejecutados en una ventana separada del LAB), no un booleano humano.

    Fail-closed: ``passed`` solo es True si hay muestra suficiente (``round_trips >=
    min_closed_round_trips``) y las métricas respetan la política. Sin evidencia ⇒
    ``False``.

    V2.32.1 (auditoría): ``trades`` cuenta *piernas* ejecutadas (entradas + salidas);
    ``round_trips`` cuenta operaciones *cerradas* (la guarda de muestra real). El
    fingerprint del dataset (``shadow_start``/``shadow_end``/``bars_hash``/
    ``strategy_definition_hash``/``engine_version``/``config_hash``/
    ``data_snapshot_id``) hace la evidencia reproducible: dentro de meses se puede
    demostrar exactamente con qué barras se autorizó la promoción.
    """

    version_id: str
    trades: int
    passed: bool
    reasons: tuple[str, ...] = ()
    instrument_id: str | None = None
    return_pct: float | None = None
    max_drawdown_pct: float | None = None
    win_rate: float | None = None
    bars_used: int = 0
    as_of: str | None = None
    # --- V2.32.1: semántica de muestra y fingerprint del dataset ---
    round_trips: int = 0
    data_snapshot_id: str | None = None
    shadow_start: str | None = None
    shadow_end: str | None = None
    bars_hash: str | None = None
    strategy_definition_hash: str | None = None
    engine_version: str | None = None
    config_hash: str | None = None
    lab_end: str | None = None


@dataclass(frozen=True, slots=True)
class ShadowPolicy:
    """Umbrales de la validación shadow (deterministas, sin IA).

    ``min_closed_round_trips`` es la guarda de muestra: no se aprueba con evidencia
    anecdótica, y cuenta operaciones **cerradas** (no piernas ejecutadas). Se conserva
    ``min_trades`` como alias de compatibilidad; si ambos se pasan, manda
    ``min_closed_round_trips``.

    ``min_return_pct`` es MÍNIMO (se rechaza por debajo) y ``max_drawdown_pct`` es
    TECHO (se rechaza por encima). Fail-closed: si el umbral está configurado y la
    métrica del replay falta, se rechaza (no se asume que "no medido" es "sin riesgo").
    Un umbral ``None`` desactiva ese check.
    """

    min_closed_round_trips: int = 10
    min_return_pct: float | None = 0.0
    max_drawdown_pct: float | None = None
    min_trades: int | None = None  # alias de compatibilidad (legado)

    def evaluate(
        self,
        *,
        version_id: str,
        trades: int,
        return_pct: float | None,
        max_drawdown_pct: float | None,
        win_rate: float | None = None,
        instrument_id: str | None = None,
        bars_used: int = 0,
        as_of: str | None = None,
        round_trips: int | None = None,
        data_snapshot_id: str | None = None,
        shadow_start: str | None = None,
        shadow_end: str | None = None,
        bars_hash: str | None = None,
        strategy_definition_hash: str | None = None,
        engine_version: str | None = None,
        config_hash: str | None = None,
        lab_end: str | None = None,
    ) -> ShadowValidationResult:
        """Aplica la política a las métricas del replay shadow (fail-closed).

        La guarda de muestra se evalúa sobre ``round_trips`` (operaciones cerradas) si
        se aporta; si no, se asume que ``trades`` ya es el número de round-trips (modo
        legado/compatibilidad con llamantes antiguos).
        """
        reasons: list[str] = []
        min_trips = self.min_closed_round_trips if self.min_trades is None else self.min_trades
        closed = trades if round_trips is None else int(round_trips)
        if closed < min_trips:
            reasons.append("shadow_muestra_insuficiente")
        if self.min_return_pct is not None and (
            return_pct is None or return_pct < self.min_return_pct
        ):
            reasons.append("shadow_retorno_insuficiente")
        # Fail-closed: si el drawdown es un gate configurado y la métrica falta, se
        # rechaza. "No medido" NO es "sin riesgo" (antes se saltaba el check).
        if self.max_drawdown_pct is not None:
            if max_drawdown_pct is None:
                reasons.append("shadow_drawdown_ausente")
            elif max_drawdown_pct > self.max_drawdown_pct:
                reasons.append("shadow_drawdown_excesivo")
        return ShadowValidationResult(
            version_id=version_id,
            trades=trades,
            passed=not reasons,
            reasons=tuple(reasons),
            instrument_id=instrument_id,
            return_pct=return_pct,
            max_drawdown_pct=max_drawdown_pct,
            win_rate=win_rate,
            bars_used=bars_used,
            as_of=as_of,
            round_trips=closed,
            data_snapshot_id=data_snapshot_id,
            shadow_start=shadow_start,
            shadow_end=shadow_end,
            bars_hash=bars_hash,
            strategy_definition_hash=strategy_definition_hash,
            engine_version=engine_version,
            config_hash=config_hash,
            lab_end=lab_end,
        )


@dataclass(frozen=True, slots=True)
class PaperForwardResult:
    """Evidencia **forward** de una estrategia ACTIVE (V2.33 / A13).

    A diferencia de ``ShadowValidationResult`` (validación *histórica* sobre un hold-out
    del LAB), este resultado mide lo que ocurre con **mercado nuevo posterior a la
    promoción**: la propia definición de la ACTIVE produce señales sobre barras nuevas,
    esas señales pasan por los gates deterministas y, si procede, se ejecutan como
    órdenes/fills **paper** (SIM). El P&L resultante es forward de verdad, no replay
    histórico.

    Fail-closed: ``passed`` solo es True si hay operaciones **cerradas** suficientes
    (``round_trips >= min_closed_round_trips``) y las métricas respetan la política. Sin
    barras nuevas posteriores a la promoción ⇒ ``sin_barras_forward`` y ``passed=False``
    (nunca se inventa P&L).

    El fingerprint (``forward_start``/``forward_end``/``bars_hash``/
    ``strategy_definition_hash``/``engine_version``/``config_hash``/``data_snapshot_id``)
    hace la evidencia reproducible: dentro de meses se puede demostrar exactamente con
    qué barras nuevas se comportó la estrategia.
    """

    version_id: str
    trades: int
    passed: bool
    reasons: tuple[str, ...] = ()
    instrument_id: str | None = None
    return_pct: float | None = None
    max_drawdown_pct: float | None = None
    win_rate: float | None = None
    bars_used: int = 0
    as_of: str | None = None
    # --- V2.33: semántica de muestra y fingerprint del dataset forward ---
    round_trips: int = 0
    data_snapshot_id: str | None = None
    forward_start: str | None = None
    forward_end: str | None = None
    bars_hash: str | None = None
    strategy_definition_hash: str | None = None
    engine_version: str | None = None
    config_hash: str | None = None
    # Barrera temporal: solo cuentan barras posteriores a la promoción de la ACTIVE.
    promoted_at: str | None = None
    # ``dry_run``/``blocked`` distinguen "no se ejecutó paper" de "se ejecutó y perdió".
    fills: int = 0
    vetoes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class PaperForwardPolicy:
    """Umbrales de la validación forward (deterministas, sin IA).

    ``min_closed_round_trips`` es la guarda de muestra (misma semántica que el shadow):
    no se valida una estrategia forward con evidencia anecdótica. ``min_bars`` exige una
    ventana forward mínima para que el resultado sea interpretable.

    ``min_return_pct`` es MÍNIMO y ``max_drawdown_pct`` es TECHO. Fail-closed: si el
    umbral está configurado y la métrica falta, se rechaza (no se asume que "no medido"
    es "sin riesgo"). Un umbral ``None`` desactiva ese check.
    """

    min_closed_round_trips: int = 10
    min_bars: int = 20
    min_return_pct: float | None = 0.0
    max_drawdown_pct: float | None = None

    def evaluate(
        self,
        *,
        version_id: str,
        trades: int,
        return_pct: float | None,
        max_drawdown_pct: float | None,
        win_rate: float | None = None,
        instrument_id: str | None = None,
        bars_used: int = 0,
        as_of: str | None = None,
        round_trips: int | None = None,
        data_snapshot_id: str | None = None,
        forward_start: str | None = None,
        forward_end: str | None = None,
        bars_hash: str | None = None,
        strategy_definition_hash: str | None = None,
        engine_version: str | None = None,
        config_hash: str | None = None,
        promoted_at: str | None = None,
        fills: int = 0,
        vetoes: tuple[str, ...] = (),
    ) -> PaperForwardResult:
        """Aplica la política a las métricas del forward paper (fail-closed)."""
        reasons: list[str] = []
        closed = trades if round_trips is None else int(round_trips)
        if bars_used < self.min_bars:
            reasons.append("forward_barras_insuficientes")
        if closed < self.min_closed_round_trips:
            reasons.append("forward_muestra_insuficiente")
        if self.min_return_pct is not None and (
            return_pct is None or return_pct < self.min_return_pct
        ):
            reasons.append("forward_retorno_insuficiente")
        # Fail-closed: si el drawdown es un gate configurado y la métrica falta, se
        # rechaza. "No medido" NO es "sin riesgo".
        if self.max_drawdown_pct is not None:
            if max_drawdown_pct is None:
                reasons.append("forward_drawdown_ausente")
            elif max_drawdown_pct > self.max_drawdown_pct:
                reasons.append("forward_drawdown_excesivo")
        return PaperForwardResult(
            version_id=version_id,
            trades=trades,
            passed=not reasons,
            reasons=tuple(reasons),
            instrument_id=instrument_id,
            return_pct=return_pct,
            max_drawdown_pct=max_drawdown_pct,
            win_rate=win_rate,
            bars_used=bars_used,
            as_of=as_of,
            round_trips=closed,
            data_snapshot_id=data_snapshot_id,
            forward_start=forward_start,
            forward_end=forward_end,
            bars_hash=bars_hash,
            strategy_definition_hash=strategy_definition_hash,
            engine_version=engine_version,
            config_hash=config_hash,
            promoted_at=promoted_at,
            fills=fills,
            vetoes=vetoes,
        )


@dataclass(frozen=True, slots=True)
class StrategyPromotion:
    """Promoción (o rechazo) de un finalista a ACTIVE, con su porqué auditable."""

    finalist_id: str
    promoted: bool
    reasons: tuple[str, ...] = ()
    shadow_validated: bool = False
    shadow_validation_id: str | None = None
    promoted_at: str | None = None


@dataclass(frozen=True, slots=True)
class ActiveStrategy:
    """Estrategia ACTIVE (versión inmutable) sujeta a vigilancia."""

    version_id: str
    candidate_id: str
    instrument_id: str
    name: str
    definition: dict[str, Any]
    # V2.32/A12: evidencia shadow que autorizó la promoción (None si no hay).
    shadow_validated: bool = False
    shadow_validation_id: str | None = None
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
    shadow: ShadowValidationResult | None = None,
    shadow_validated: bool | None = None,
) -> StrategyPromotion:
    """Promotion Gate (V2.25 · Fase 6): decide si un finalista puede ser ACTIVE.

    Exige, en este orden:

    1. Los SEIS gates cuantitativos en PASS (``validation.passed``).
    2. El COACH sin veto (un veto del COACH bloquea aunque los gates pasen).
    3. Evidencia shadow/paper *ejecutada* (anti strategy-chasing): V2.32 / A12.

    V2.32: la autoridad es ``shadow`` (``ShadowValidationResult``). El booleano
    ``shadow_validated`` se conserva SOLO como override explícito del operador
    (rollout/compatibilidad de herméticos): si se pasa, sustituye a la evidencia.
    Por defecto (``shadow_validated=None``) el flag no puede certificar sin
    evidencia: sin ``shadow`` que pase ⇒ ``shadow_validation_requerida``.
    """
    reasons: list[str] = []
    missing = validation.missing_gates
    if missing:
        reasons.append(f"gates_no_superados:{','.join(missing)}")
    if coach.vetoes:
        reasons.append("coach_veto")
    effective = shadow if shadow is not None else _shadow_override(shadow_validated, finalist)
    if effective is None or not effective.passed:
        reasons.append("shadow_validation_requerida")
    promoted = not reasons
    return StrategyPromotion(
        finalist_id=finalist.version_id,
        promoted=promoted,
        reasons=tuple(reasons),
        shadow_validated=bool(effective.passed) if effective is not None else False,
        shadow_validation_id=effective.version_id if effective is not None else None,
    )


def _shadow_override(
    shadow_validated: bool | None,
    finalist: StrategyFinalist | None,
) -> ShadowValidationResult | None:
    """Adapta el override booleano (legado) a un resultado shadow sintético.

    ``None`` ⇒ no hay override (sin evidencia ⇒ no promoción). Un booleano explícito
    se materializa como resultado con motivo ``shadow_override_operador`` para que la
    auditoría distinga "aprobado por evidencia" de "aprobado por override humano".
    """
    if shadow_validated is None:
        return None
    version_id = finalist.version_id if finalist is not None else "override"
    if not shadow_validated:
        return ShadowValidationResult(
            version_id=version_id,
            trades=0,
            passed=False,
            reasons=("shadow_override_operador_denegado",),
        )
    return ShadowValidationResult(
        version_id=version_id,
        trades=0,
        passed=True,
        reasons=("shadow_override_operador",),
    )


def can_transition(
    *,
    state: StrategyLifecycleState,
    gates: tuple[GateResult, ...] = (),
    coach: CoachAssessment | None = None,
    validation: StrategyValidation | None = None,
    shadow_validated: bool | None = None,
    shadow: ShadowValidationResult | None = None,
) -> TransitionResult:
    """Máquina de estados: ¿puede avanzar desde ``state`` y con qué motivos?

    Fail-closed y explícita: cada paso exige su condición y devuelve los motivos de
    bloqueo. No ejecuta efectos; solo decide.

    V2.32 / A12: en ``VALIDACION`` la autoridad es la evidencia ``shadow``; el
    booleano ``shadow_validated`` (``None`` por defecto) se acepta como override
    explícito para compatibilidad de herméticos.
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
        if failed:
            return TransitionResult(state, target, False, (f"gates_fallidos:{','.join(failed)}",))
        # Fail-closed: avanzar sin haber evaluado NINGÚN gate no es PASS. ``gates=()``
        # (el propio default de la firma) NO puede autorizar el salto de estado.
        if not gates:
            return TransitionResult(state, target, False, ("gates_no_evaluados",))
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
        effective = shadow if shadow is not None else _shadow_override(shadow_validated, None)
        if effective is None or not effective.passed:
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
    "PaperForwardPolicy",
    "PaperForwardResult",
    "ShadowPolicy",
    "ShadowValidationResult",
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
