"""V2.26 / A10 — Auto Orchestrator: el ciclo completo del Strategy Lifecycle.

Encadena las fases (reutilizando los módulos de A10 ya existentes) y deja el
resultado en el store del lifecycle:

    ESTUDIO → LABORATORIO → TOP3 → COACH → FINALISTA → VALIDACION → PROMOCION
            → ACTIVE → (vigilancia; degradación → DEGRADED/re-LAB)

Restricciones duras (auditoría V2.24 §20):

* **SIM-only**: este orquestador NO abre venues ni habilita LIVE. La ejecución sigue
  gobernada por el worker AUTO SIM y su ``DecisionProvider``.
* **Sin swap directo**: el LAB nunca sustituye la activa; solo promociona por el
  Promotion Gate (gates + coach + shadow). La vigilancia degrada y vuelve al LAB.
* **Determinista/inyectable**: los ``DecisionProvider`` y las funciones de fase se
  inyectan; el orquestador no llama a la red ni a un LLM.

Este módulo es el CEREBRO de orquestación; el worker (``background/``) es el reloj que
lo invoca con el gate de entorno y las dependencias reales.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

from bolsa_domain.entities.strategy_lifecycle import (
    PROMOTION_GATES,
    ActiveStrategy,
    GateResult,
    StrategyCandidate,
    StrategyEvaluation,
)

from bolsa_application.strategy_executable_definition import (
    build_executable_definition,
    champion_params_from_result,
)
from bolsa_application.strategy_lab_phase import (
    LabThresholds,
    build_estudio_candidates,
    evaluate_optimize_result,
)
from bolsa_application.strategy_promotion_phase import (
    ActiveStrategyRef,
    build_strategy_version,
    decide_promotion,
)
from bolsa_application.strategy_top3_coach_phase import (
    CoachThresholds,
    Top3CoachVerdict,
    assess_top3_with_coach,
    select_top3,
)
from bolsa_application.strategy_vigilance_phase import (
    HealthThresholds,
    evaluate_active_health,
)

logger = logging.getLogger(__name__)

__all__ = [
    "AutoOrchestrator",
    "OrchestratorDeps",
    "OrchestratorResult",
    "active_strategy_decider",
]


class LifecycleStorePort(Protocol):
    """Subconjunto del store del lifecycle que el orquestador necesita."""

    async def save_candidate(self, candidate: StrategyCandidate) -> None: ...
    async def list_candidates(self, *, instrument_id: str | None = ...) -> list[Any]: ...
    async def save_evaluation(self, evaluation: StrategyEvaluation) -> None: ...
    async def save_finalist(self, finalist: Any) -> None: ...
    async def save_promotion(self, record: Any) -> None: ...
    async def save_active(self, record: Any) -> None: ...
    async def get_active(self, *, instrument_id: str) -> Any: ...
    async def save_health(self, version_id: str, health: Any) -> None: ...
    # V2.29 / A10: dictamen COACH comparativo sobre el TOP3 (uno por candidato). El
    # orquestador lo persiste como evidencia advisory; nunca sustituye a los gates.
    async def save_coach_assessment(self, assessment: Any) -> None: ...


# ``run_optimize(candidate) -> result`` (resultado de RunSmaGridOptimize o compatible).
OptimizeRunner = Callable[[StrategyCandidate], Awaitable[Any]]
# ``resolve_universe() -> resolution`` (objeto de resolve_estudio_universe).
UniverseResolver = Callable[[], Awaitable[Any]]
# ``observed_metrics(version_id) -> metrics`` (dict para evaluate_active_health).
# V2.28 / A10: puerto opcional para la vigilancia real; sin él la vigilancia queda como
# antes (métricas que le pase el llamante) y NO se inventa evidencia.
ObservedMetricsProvider = Callable[[str], Awaitable[dict[str, Any]]]


@dataclass(slots=True)
class OrchestratorDeps:
    """Dependencias inyectables del orquestador (todas opcionales para herméticos)."""

    store: LifecycleStorePort
    resolve_universe: UniverseResolver | None = None
    run_optimize: OptimizeRunner | None = None
    candidate_id_factory: Callable[[str, int], str] | None = None
    lab_thresholds: LabThresholds = field(default_factory=LabThresholds)
    coach_thresholds: CoachThresholds = field(default_factory=CoachThresholds)
    health_thresholds: HealthThresholds = field(default_factory=HealthThresholds)
    strategy_family: str = "sma_crossover"
    params: dict[str, Any] = field(default_factory=dict)
    max_candidates: int = 3
    # V2.28 / A10 (P1-02 real): métricas observadas de la versión activa (fills SIM
    # atribuidos). Si es ``None``, ``watch_active`` usa exactamente las métricas que le
    # pase el llamante (comportamiento previo, sin regresión).
    observed_metrics: ObservedMetricsProvider | None = None


@dataclass(slots=True)
class OrchestratorResult:
    """Resumen auditable de una pasada del ciclo (por instrumento)."""

    instrument_id: str
    status: str
    candidates: int = 0
    evaluated: int = 0
    promoted: bool = False
    active_version_id: str | None = None
    replaces_version_id: str | None = None
    degraded: bool = False
    relab_triggered: bool = False
    reasons: tuple[str, ...] = ()
    detail: str | None = None


class AutoOrchestrator:
    """Orquesta el ciclo A10 para un instrumento (determinista, SIM-only)."""

    def __init__(self, deps: OrchestratorDeps) -> None:
        self._deps = deps

    @property
    def deps(self) -> OrchestratorDeps:
        """Dependencias del orquestador (lectura; útil para composición/introspección)."""
        return self._deps

    async def resolve_universe(self) -> Any:
        """Resuelve el universo (ESTUDIO) con el resolver cableado.

        Devuelve ``None`` cuando no hay resolver inyectado (modo hermético/test): el
        llamante debe entonces usar su allowlist configurada.
        """
        if self._deps.resolve_universe is None:
            return None
        return await self._deps.resolve_universe()

    async def run_cycle(
        self,
        *,
        instrument_id: str,
        data_snapshot_id: str | None = None,
        shadow_validated: bool = False,
        run_id: str = "auto-orchestrator",
    ) -> OrchestratorResult:
        """Ejecuta una pasada completa del ciclo para ``instrument_id``.

        ``shadow_validated`` es la validación shadow/paper exigida por el Promotion
        Gate; el orquestador NO la inventa (default False ⇒ no promociona).
        """
        deps = self._deps
        resolution = None
        if deps.resolve_universe is not None:
            resolution = await deps.resolve_universe()

        # ESTUDIO: candidatas reproducibles (respetando el instrumento pedido).
        if resolution is not None:
            plan = build_estudio_candidates(
                resolution=resolution,
                strategy_family=deps.strategy_family,
                params=deps.params,
                data_snapshot_id=data_snapshot_id,
                candidate_id_factory=deps.candidate_id_factory,
                max_candidates=deps.max_candidates,
                instrument_id=instrument_id,
            )
            candidates = list(plan.candidates)
            if not candidates:
                return OrchestratorResult(
                    instrument_id=instrument_id,
                    status=plan.status,
                    detail="instrumento_ausente_en_universo",
                )
        else:
            # Sin resolver de universo: candidata directa (modo test/explicit).
            cid = (
                deps.candidate_id_factory(instrument_id, 0)
                if deps.candidate_id_factory is not None
                else f"cand-{instrument_id}-{deps.strategy_family}-0"
            )
            candidates = [
                StrategyCandidate(
                    id=cid,
                    instrument_id=instrument_id,
                    strategy_family=deps.strategy_family,
                    params=dict(deps.params),
                    data_snapshot_id=data_snapshot_id,
                )
            ]

        for candidate in candidates:
            await deps.store.save_candidate(candidate)

        # LABORATORIO: evaluar cada candidata con el runner real inyectado.
        evaluations: list[StrategyEvaluation] = []
        # V2.29/A10: resultado crudo por candidata para extraer el campeón y persistir
        # sus parámetros ganadores en la versión (habilita el SignalEvaluator real).
        results_by_candidate: dict[str, Any] = {}
        if deps.run_optimize is not None:
            for candidate in candidates:
                try:
                    result = await deps.run_optimize(candidate)
                except Exception:  # noqa: BLE001 — un fallo del LAB no inventa evidencia.
                    logger.exception("auto_orchestrator lab failed for %s", candidate.id)
                    continue
                if result is None:
                    continue
                evaluation = evaluate_optimize_result(
                    candidate=candidate, result=result, thresholds=deps.lab_thresholds
                )
                await deps.store.save_evaluation(evaluation)
                evaluations.append(evaluation)
                results_by_candidate[candidate.id] = result

        # TOP3 (por evidencia) — solo si hay evaluaciones.
        selection = (
            select_top3(
                instrument_id=instrument_id,
                evaluations=evaluations,
                run_id=run_id,
            )
            if evaluations
            else None
        )
        if selection is None or not selection.ok:
            return OrchestratorResult(
                instrument_id=instrument_id,
                status="sin_evidencia_top3",
                candidates=len(candidates),
                evaluated=len(evaluations),
            )

        # COACH (advisory, V2.29 comparativo): dictamina los tres candidatos del TOP3
        # en orden de ranking por evidencia y elige el primero sin veto. El ranking lo
        # fija la evidencia (select_top3); el COACH nunca lo reordena ni aprueba por
        # encima de un gate cuantitativo.
        verdict: Top3CoachVerdict = assess_top3_with_coach(
            selection=selection,
            evaluations=evaluations,
            thresholds=deps.coach_thresholds,
        )
        for assessment in verdict.assessments:
            await deps.store.save_coach_assessment(assessment)
        if verdict.all_vetoed:
            return OrchestratorResult(
                instrument_id=instrument_id,
                status="coach_veto",
                candidates=len(candidates),
                evaluated=len(evaluations),
                reasons=verdict.contradictions,
            )

        best_id = verdict.selected_id
        assert best_id is not None  # garantizado por all_vetoed
        best_eval = next(e for e in evaluations if e.candidate_id == best_id)
        coach = next(a for a in verdict.assessments if a.candidate_id == best_id)

        # FINALISTA: versión inmutable (V2.29/A10: con los parámetros del CAMPEÓN y la
        # definición ejecutable para que la ACTIVE pueda evaluar su propia señal).
        best_candidate = next(c for c in candidates if c.id == best_id)
        finalist = build_strategy_version(
            candidate=best_candidate,
            name=best_candidate.id,
            definition=_champion_definition(
                candidate=best_candidate,
                result=results_by_candidate.get(best_id),
            ),
        )
        await deps.store.save_finalist(finalist)

        # VALIDACION + PROMOCION: gates cuantitativos (del LAB) + coach + shadow.
        active_record = await deps.store.get_active(instrument_id=instrument_id)
        active_ref = (
            ActiveStrategyRef(
                version_id=active_record.active.version_id,
                candidate_id=active_record.active.candidate_id,
                instrument_id=instrument_id,
            )
            if active_record is not None
            else None
        )
        gates = _promotion_gates(best_eval, coach)
        decision = decide_promotion(
            finalist=finalist,
            gates=gates,
            coach=coach,
            shadow_validated=shadow_validated,
            active=active_ref,
        )
        await deps.store.save_promotion(
            _promotion_record(decision, instrument_id=instrument_id)
        )
        if not decision.promoted:
            return OrchestratorResult(
                instrument_id=instrument_id,
                status="no_promocionada",
                candidates=len(candidates),
                evaluated=len(evaluations),
                reasons=decision.reasons,
            )

        # ACTIVE (+ vigilancia inicial).
        from bolsa_application.strategy_lifecycle_store import ActiveStrategyRecord

        await deps.store.save_active(
            ActiveStrategyRecord(
                active=ActiveStrategy(
                    version_id=finalist.version_id,
                    candidate_id=finalist.candidate_id,
                    instrument_id=instrument_id,
                    name=finalist.name,
                    definition=finalist.definition,
                ),
                promoted_at=finalist.definition.get("promoted_at") or "",
            )
        )
        vigilance = evaluate_active_health(
            version_id=finalist.version_id,
            as_of=run_id,
            metrics=best_eval.metrics,
            thresholds=deps.health_thresholds,
        )
        if vigilance.health is not None:
            await deps.store.save_health(finalist.version_id, vigilance.health)

        return OrchestratorResult(
            instrument_id=instrument_id,
            status="active",
            candidates=len(candidates),
            evaluated=len(evaluations),
            promoted=True,
            active_version_id=finalist.version_id,
            replaces_version_id=decision.replaces.version_id if decision.replaces else None,
            degraded=vigilance.degraded,
            relab_triggered=vigilance.relab,
        )

    async def watch_active(
        self,
        *,
        instrument_id: str,
        metrics: dict[str, Any] | None = None,
        as_of: str,
    ) -> OrchestratorResult:
        """Vigilancia: evalúa la activa y persiste el snapshot; degrada si procede.

        V2.28 / A10 (P1-02 real): si hay ``observed_metrics`` cableado, se calculan las
        métricas *observadas* de la versión activa desde sus fills SIM y se fusionan con
        las que pase el llamante (las predictivas del LAB tienen prioridad si coinciden).
        Sin provider, se comporta como antes: solo las métricas del llamante.

        Fail-closed: un fallo del provider NO degrada ni aprueba por sí mismo — se degrada
        a «sin métricas observadas» y se sigue evaluando con lo disponible.
        """
        record = await self._deps.store.get_active(instrument_id=instrument_id)
        if record is None:
            return OrchestratorResult(instrument_id=instrument_id, status="sin_activa")
        effective_metrics: dict[str, Any] = {}
        if self._deps.observed_metrics is not None:
            try:
                effective_metrics = dict(
                    await self._deps.observed_metrics(record.active.version_id) or {}
                )
            except Exception:  # noqa: BLE001 — sin evidencia observada no se inventa nada.
                logger.exception(
                    "auto_orchestrator observed metrics failed for %s",
                    record.active.version_id,
                )
                effective_metrics = {}
        if metrics:
            effective_metrics.update(metrics)
        decision = evaluate_active_health(
            version_id=record.active.version_id,
            as_of=as_of,
            metrics=effective_metrics,
            thresholds=self._deps.health_thresholds,
        )
        if decision.health is not None:
            await self._deps.store.save_health(record.active.version_id, decision.health)
        return OrchestratorResult(
            instrument_id=instrument_id,
            status="degraded" if decision.degraded else "active",
            active_version_id=record.active.version_id,
            degraded=decision.degraded,
            relab_triggered=decision.relab,
            reasons=decision.breaches,
        )


def _champion_definition(
    *,
    candidate: StrategyCandidate,
    result: Any,
) -> dict[str, Any] | None:
    """V2.29/A10 — ``definition`` extra para la versión promocionada.

    Añade ``champion_params`` (parámetros ganadores del grid) y ``executable`` (esquema
    declarativo listo para ``evaluate_strategy_last_bar``). Es aditivo: si no hay
    resultado o campeón, devuelve ``None`` y la versión conserva su definición previa
    (sin inventar señal ejecutable).
    """
    champion = champion_params_from_result(result) if result is not None else None
    if champion is None:
        return None
    extra: dict[str, Any] = {"champion_params": champion}
    executable = build_executable_definition(candidate.strategy_family, champion)
    if executable is not None:
        extra["executable"] = executable
    return extra


def _promotion_gates(evaluation: StrategyEvaluation, coach: Any) -> tuple[GateResult, ...]:
    """Compone los seis gates del Promotion Gate desde la evaluación + coach.

    Toma los gates cuantitativos de la evaluación y añade el gate ``coach`` a partir
    del ``CoachAssessment`` (PASS si no veta). Un gate ausente en la evaluación queda
    como NOT_EVALUATED ⇒ el Promotion Gate lo tratará como no superado.
    """
    from bolsa_domain.entities.strategy_lifecycle import GateStatus

    by_name = {g.gate: g for g in evaluation.gates}
    gates: list[GateResult] = []
    for name in PROMOTION_GATES:
        if name == "coach":
            gates.append(
                GateResult(
                    gate="coach",
                    status=GateStatus.FAIL if coach.vetoes else GateStatus.PASS,
                    detail=coach.headline,
                )
            )
        elif name in by_name:
            gates.append(by_name[name])
        else:
            gates.append(GateResult(gate=name, status=GateStatus.NOT_EVALUATED))
    return tuple(gates)


def _promotion_record(decision: Any, *, instrument_id: str) -> Any:
    from bolsa_application.strategy_lifecycle_store import new_promotion_record

    return new_promotion_record(
        promotion=decision.promotion,
        candidate_id=decision.finalist.candidate_id,
        instrument_id=instrument_id,
    )


def active_strategy_decider(
    *,
    active: ActiveStrategy,
    fallback: Any,
    watch: Sequence[str],
    lot_qty: float = 100.0,
) -> Callable[[str], Any]:
    """``DecisionProvider`` que expone la estrategia ACTIVE al AUTO (SIM-only).

    Seam ÚNICO por el que A10 entra en el hot path: devuelve un ``Callable[[str],
    DecisionPackage]`` que el worker AUTO ya sabe usar. No ejecuta nada por sí mismo:
    solo traduce la definición de la estrategia activa a propuestas que los gates
    (RiskGate/SimulationGate) siguen pudiendo vetar. Sin estrategia aplicable,
    delega en ``fallback`` (el spine determinista) — nunca abre LIVE.

    ``kind == "deterministic_sma"`` (o sin ``kind``) usa la lógica del spine; el
    ``definition`` puede aportar ``lot_qty``/``watch`` sin cambiar la seguridad.
    """
    from bolsa_application.decision_contract import DecisionPackage

    definition = dict(active.definition or {})
    effective_lot = float(definition.get("lot_qty", lot_qty) or lot_qty)
    effective_watch = tuple(str(s) for s in (definition.get("watch") or watch))
    source = f"active-strategy:{active.version_id}"

    def _decide(symbol: str) -> DecisionPackage:
        if symbol not in effective_watch:
            return DecisionPackage(action="HOLD", instrument_id=symbol, quantity=0, source=source)
        try:
            proposal = fallback(symbol)
        except Exception:  # noqa: BLE001 — una estrategia nunca rompe el motor.
            return DecisionPackage(
                action="HOLD", instrument_id=symbol, quantity=0, source=source
            )
        # Reescala la propuesta del spine al lote de la estrategia activa, sin alterar
        # la acción: la ejecución sigue gobernada por los gates y el settlement SIM.
        if proposal.action in {"BUY", "SELL"}:
            return DecisionPackage(
                action=proposal.action,
                instrument_id=symbol,
                quantity=min(float(proposal.quantity or effective_lot), effective_lot),
                source=source,
            )
        return DecisionPackage(
            action=proposal.action, instrument_id=symbol, quantity=0, source=source
        )

    return _decide
