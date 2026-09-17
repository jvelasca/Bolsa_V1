"""AutoInvestmentSystem — composición del hot path AUTO 2.0 (P0/P3).

Ensambla la cadena operativa canónica en UNA pasada por barra de mercado::

    OPPORTUNITY → PORTFOLIO DECISION → RISK → TRADE PLAN → EXECUTION
          ↘  POSITION MANAGER (PositionState + ExitPlan + PositionDecision)
          ↘  DECISION JOURNAL (trade y NO-trade, con reason_codes)

Responsabilidades de este módulo (y solo estas):

1. **Contrato TradePlan**: el output primario de cada decisión de entrada es un
   ``TradePlan`` (no un ``BUY/SELL/HOLD`` suelto). El ``DecisionPackage`` queda
   como artefacto de ejecución aguas abajo, no como contrato de decisión.
2. **DecisionJournal con reason_codes**: CADA decisión (aprobada o rechazada) genera
   una entrada de journal con su ``reason_codes`` (riesgo/correlación/régimen/stale/
   mandato/fit/edge...), de modo que sea auditable por qué AUTO NO operó.
3. **Research vs Trading (P3)**: discovery/lab/adaptive/param-region/regime-learning
   NUNCA deciden operar directamente; sus candidatos se derivan a Research allocation.
   Solo las estrategias ACTIVE alimentan el pipeline de decisión de trading.

Este módulo es determinista y sin I/O: produce un ``AutoRunReport``. El llamante
(worker) decide qué hacer con las órdenes y cómo persistir el journal (puerto
``JournalWriter``).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import uuid4

from bolsa_analytics.cognitive.auto_portfolio_snapshot import AutoPortfolioSnapshot
from bolsa_analytics.cognitive.exit_policy import resolve_exit_policy
from bolsa_analytics.cognitive.market_regime_gate import map_trial_regime
from bolsa_analytics.cognitive.opportunity_ranker import (
    TOP_N_EXCLUDED,
    OpportunityScore,
    rank_opportunities,
    select_top_opportunities,
)
from bolsa_analytics.cognitive.position_lifecycle import (
    compute_trail_stop,
    is_trail_armed,
)
from bolsa_analytics.cognitive.position_state import PositionState
from bolsa_analytics.cognitive.trade_plan import validate_trade_plan
from bolsa_application.auto_reason_codes import NO_MARK_DATA
from bolsa_application.decision_contract import DecisionPackage
from bolsa_application.portfolio_decision_engine import (
    Direction,
    PortfolioDecision,
    PortfolioDecisionConfig,
    decide_portfolio,
)
from bolsa_application.position_manager import (
    PositionManagerResult,
    PositionManagerSkip,
    manage_position_outcome,
)
from bolsa_domain.entities.cognitive_artifacts import DecisionJournalEntryRecord

# Fuentes que NUNCA deciden operar directamente (P3): alimentan Research allocation.
RESEARCH_SOURCES: frozenset[str] = frozenset(
    {"discovery", "lab", "adaptive", "param_region", "regime_learning", "grammar"}
)
ACTIVE_SOURCE = "active"

EVENT_ENTRY_DECISION = "auto_entry_decision"
EVENT_POSITION_DECISION = "auto_position_decision"
EVENT_POSITION_SKIP = "auto_position_skip"

_OPERATIONAL_REGIMES: frozenset[str] = frozenset(
    {"BULL_TREND", "BEAR_TREND", "SIDEWAYS", "HIGH_VOLATILITY", "LOW_VOLATILITY", "RISK_OFF", "UNKNOWN"}
)


def _coerce_operational_regime(regime: str | None) -> str:
    """Normaliza el régimen: acepta la etiqueta operativa o la de barras (v0)."""
    value = str(regime or "").strip().upper()
    if value in _OPERATIONAL_REGIMES:
        return value
    return map_trial_regime(regime)


@dataclass(frozen=True, slots=True)
class EntryCandidate:
    """Candidato de entrada (geometría + metadatos) aportado por una fuente de señal."""

    instrument_id: str
    direction: Direction = "long"
    entry_price: float | None = None
    stop_price: float | None = None
    atr: float | None = None
    target_price: float | None = None
    sector: str | None = None
    liquidity_notional: float | None = None
    correlation_with_portfolio: float | None = None
    source: str = ACTIVE_SOURCE


@dataclass(frozen=True, slots=True)
class AutoRunReport:
    """Resultado de una pasada operativa completa (auditable, serializable)."""

    decisions: tuple[PortfolioDecision, ...] = ()
    position_results: tuple[PositionManagerResult, ...] = ()
    journal_entries: tuple[DecisionJournalEntryRecord, ...] = ()
    research_allocations: tuple[str, ...] = ()
    regime: str = "UNKNOWN"
    as_of: str = ""

    @property
    def trade_plans(self) -> tuple[Any, ...]:
        """Planes operativos (contrato TradePlan) de las entradas aprobadas."""
        return tuple(d.trade_plan for d in self.decisions if d.approved and d.trade_plan)

    def to_dict(self) -> dict[str, Any]:
        return {
            "regime": self.regime,
            "asOf": self.as_of,
            "decisions": [d.to_dict() for d in self.decisions],
            "positionResults": [p.to_dict() for p in self.position_results],
            "journalEntries": [e.payload for e in self.journal_entries],
            "researchAllocations": list(self.research_allocations),
        }


def is_research_only(source: str) -> bool:
    """True si la fuente solo puede asignar Research (nunca decidir trading)."""
    return str(source or "").strip().lower() in RESEARCH_SOURCES


def _now_iso(at: str) -> str:
    return at if at else datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def trade_plan_to_decision_package(
    trade_plan: Any,
    *,
    source: str = "auto-2.0",
    proposed_at: str = "",
) -> DecisionPackage | None:
    """Adapta el ``TradePlan`` (contrato AUTO 2.0) → ``DecisionPackage`` (propuesta).

    El ``DecisionPackage`` deja de ser el contrato de decisión (BUY/SELL/HOLD suelto)
    y pasa a ser la PROPUESTA de ejecución derivada del ``TradePlan``, que sigue
    gobernada por el RiskGate determinista existente (kill switch, venue SIM-only,
    barricada IA). Es el seam que conecta el nuevo pipeline con el worker endurecido
    sin bypass de seguridad.

    Fail-closed: sin ejecución permitida (``execution_allowed=False``, cantidad 0 o
    dirección no mapeable) ⇒ ``None`` (no se emite propuesta).
    V2.40.4: además, un plan que se contradice a sí mismo (``validate_trade_plan``) ⇒
    ``None``. Es defensa en profundidad en el seam que consume el worker: aunque el
    motor ya lo vete, ningún camino alternativo puede emitir una propuesta incoherente.
    """
    if trade_plan is None:
        return None
    if validate_trade_plan(trade_plan):
        return None
    if not getattr(trade_plan, "execution_allowed", False):
        return None
    quantity = getattr(trade_plan, "quantity", 0.0) or 0.0
    if quantity <= 0:
        return None
    direction = getattr(trade_plan, "direction", None)
    action: Literal["BUY", "SELL"]
    if direction == "long":
        action = "BUY"
    elif direction == "short":
        action = "SELL"
    else:
        return None
    entry = getattr(trade_plan, "entry", None)
    stop = getattr(trade_plan, "structural_stop", None)
    t1 = getattr(trade_plan, "target1", None)
    t2 = getattr(trade_plan, "target2", None)
    memo = (
        f"tradePlan={getattr(trade_plan, 'decision_id', '')} "
        f"entry={entry} stop={stop} t1={t1} t2={t2}"
    )
    return DecisionPackage(
        action=action,
        instrument_id=getattr(trade_plan, "instrument_id", ""),
        quantity=quantity,
        suggested_price=float(entry) if entry is not None else 0.0,
        source=source,
        proposed_at=proposed_at or _now_iso(""),
        memo=memo,
    )


def build_decision_journal_payload(decision: PortfolioDecision) -> dict[str, Any]:
    """Payload canónico de journal para una decisión de entrada (trade o no-trade)."""
    return {
        "event": EVENT_ENTRY_DECISION,
        "instrumentId": decision.instrument_id,
        "action": decision.action,
        "direction": decision.direction,
        "approved": decision.approved,
        "reasonCodes": list(decision.reason_codes),
        "opportunityScore": decision.opportunity_score,
        "regime": decision.regime,
        "tradePlan": None if decision.trade_plan is None else decision.trade_plan.to_dict(),
        "risk": decision.allocation,
        # V2.40.4 — por qué el plan fue declarado incoherente (vacío si no lo fue).
        "planViolations": list(decision.plan_violations),
    }


def build_position_journal_payload(result: PositionManagerResult) -> dict[str, Any]:
    """Payload canónico de journal para una decisión de gestión de posición."""
    return {
        "event": EVENT_POSITION_DECISION,
        "instrumentId": result.position.instrument_id,
        "positionId": result.position.position_id,
        "orderAction": result.order_action,
        "orderQty": result.order_qty,
        "stopUpdate": result.stop_update,
        "exitReasons": list(result.exit_reasons),
        "attention": result.attention,
        "action": result.decision.action,
        "reason": result.decision.reason,
    }


def build_top_n_excluded_payload(
    candidate: EntryCandidate, score: OpportunityScore | None
) -> dict[str, Any]:
    """Payload de journal de un candidato FUERA del TOP N (V2.40.4 · tope de evaluación).

    El score es el REAL del ranking: ``top_n_excluded`` significa "no la evalué", no
    "no tenía edge". Sin él, el journal no permitiría distinguir ambas cosas.
    """
    return {
        "event": EVENT_ENTRY_DECISION,
        "instrumentId": candidate.instrument_id,
        "action": "HOLD",
        "direction": candidate.direction,
        "approved": False,
        "reasonCodes": [TOP_N_EXCLUDED],
        "opportunityScore": None if score is None else score.combined,
        "rank": None if score is None else score.rank,
        "regime": None,
        "tradePlan": None,
        "risk": None,
    }


def build_position_skip_payload(skip: PositionManagerSkip) -> dict[str, Any]:
    """Payload de journal de una posición que NO se pudo gestionar (AUTO-1A).

    Antes estos casos eran ``continue`` mudos: el ciclo parecía "sin nada que hacer"
    cuando en realidad había una posición viva sin gestión. ``attention="high"`` porque
    es un estado OPERATIVO, no un no-op: alguien (o algo) debe poder verlo.
    """
    return {
        "event": EVENT_POSITION_SKIP,
        "instrumentId": skip.instrument_id,
        "positionId": None,
        "action": "SKIP",
        "orderAction": None,
        "orderQty": None,
        "stopUpdate": None,
        "exitReasons": [],
        "attention": "high",
        "reason": skip.reason,
        "reasonCodes": [skip.reason],
        "detail": skip.detail,
    }


def _entry(
    *,
    event_type: str,
    decision_id: str,
    actor: str,
    instrument_id: str,
    payload: dict[str, Any],
    at: str,
) -> DecisionJournalEntryRecord:
    return DecisionJournalEntryRecord(
        id=f"JNL-{uuid4().hex[:12]}",
        decision_id=decision_id,
        event_type=event_type,
        actor=actor,
        created_at=_now_iso(at),
        instrument_id=instrument_id,
        payload=payload,
    )


def run_auto_cycle(
    *,
    snapshot: AutoPortfolioSnapshot,
    opportunities: Iterable[OpportunityScore],
    candidates: Mapping[str, EntryCandidate],
    regime: str | None = None,
    open_positions: Iterable[PositionState] = (),
    marks: Mapping[str, float] | None = None,
    config: PortfolioDecisionConfig | None = None,
    top_n: int = 5,
    exit_template: str | None = None,
    actor: str = "auto-2.0",
    as_of: str = "",
) -> AutoRunReport:
    """Ejecuta UNA pasada operativa completa y devuelve el reporte auditable.

    - Separa candidatos de Research (P3) de los operativos (solo ACTIVE).
    - Rankea y selecciona el TOP N a EVALUAR (V2.40.4: tope de evaluación, no
      prioridad); los candidatos fuera del TOP se journalizan con ``top_n_excluded`` y
      su score real, y no llegan al motor de decisión.
    - Decide cada candidato del TOP con ``decide_portfolio`` (vetos fail-closed).
    - Gestiona cada posición abierta con ``manage_position``.
    - Registra en journal TODAS las decisiones (entrada y posición) con reason_codes.
    """
    resolved_regime = _coerce_operational_regime(regime)
    marks_map = dict(marks or {})

    # P3 — separar Research de Trading: los candidatos adaptativos NUNCA operan.
    research: list[str] = []
    tradable: list[EntryCandidate] = []
    for candidate in candidates.values():
        if is_research_only(candidate.source):
            research.append(candidate.instrument_id)
        else:
            tradable.append(candidate)

    # Ranking de oportunidad sobre el universo operativo. V2.40.4: ``top_n`` acota qué
    # se EVALÚA; el resto conserva su score en el journal con ``top_n_excluded``.
    ranked = rank_opportunities(opportunities)
    top = select_top_opportunities(ranked, top_n=top_n)
    score_by_instrument = {s.instrument_id: s for s in top}
    ranked_by_instrument = {s.instrument_id: s for s in ranked}

    decisions: list[PortfolioDecision] = []
    journal: list[DecisionJournalEntryRecord] = []

    for candidate in tradable:
        if candidate.instrument_id not in score_by_instrument:
            journal.append(
                _entry(
                    event_type=EVENT_ENTRY_DECISION,
                    decision_id=f"EXC-{uuid4().hex[:12]}",
                    actor=actor,
                    instrument_id=candidate.instrument_id,
                    payload=build_top_n_excluded_payload(
                        candidate, ranked_by_instrument.get(candidate.instrument_id)
                    ),
                    at=as_of,
                )
            )
            continue
        score = score_by_instrument[candidate.instrument_id]
        decision = decide_portfolio(
            instrument_id=candidate.instrument_id,
            direction=candidate.direction,
            entry_price=candidate.entry_price,
            stop_price=candidate.stop_price,
            atr=candidate.atr,
            target_price=candidate.target_price,
            opportunity_score=score,
            snapshot=snapshot,
            regime=resolved_regime,
            liquidity_notional=candidate.liquidity_notional,
            sector=candidate.sector,
            correlation_with_portfolio=candidate.correlation_with_portfolio,
            config=config,
            as_of=as_of,
        )
        decisions.append(decision)
        journal.append(
            _entry(
                event_type=EVENT_ENTRY_DECISION,
                decision_id=decision.decision_id,
                actor=actor,
                instrument_id=decision.instrument_id,
                payload=build_decision_journal_payload(decision),
                at=as_of,
            )
        )

    # Gestión de posiciones abiertas (PositionManager).
    # AUTO-2: una sola fuente de política (``resolve_exit_policy``; sin plantilla ⇒
    # MODERATE declarado) y el mismo ratchet de stop que el worker V2. ``trail_hint``
    # sólo se declara cuando hay un stop REAL que proponer: una alerta de trailing sin
    # stop sería journal ruidoso, no gestión.
    exit_policy = resolve_exit_policy(exit_template)
    position_results: list[PositionManagerResult] = []
    for position in open_positions:
        mark = marks_map.get(position.instrument_id)
        if mark is None:
            # AUTO-1A: antes era un ``continue`` mudo. Una posición SIN mark es una
            # posición viva que el motor NO pudo gestionar (ni proteger): se journaliza
            # con atención alta en vez de desaparecer del ciclo.
            journal.append(
                _entry(
                    event_type=EVENT_POSITION_SKIP,
                    decision_id=f"SKIP-{uuid4().hex[:12]}",
                    actor=actor,
                    instrument_id=position.instrument_id,
                    payload=build_position_skip_payload(
                        PositionManagerSkip(
                            instrument_id=position.instrument_id,
                            reason=NO_MARK_DATA,
                            detail="marks_map sin instrumento en el tick",
                        )
                    ),
                    at=as_of,
                )
            )
            continue
        trail_stop = (
            compute_trail_stop(position, trail_width=exit_policy.trail_width)
            if is_trail_armed(position)
            else None
        )
        outcome = manage_position_outcome(
            position,
            mark_price=mark,
            regime=resolved_regime,
            template_id=exit_template,
            trail_hint=trail_stop is not None,
            trail_stop=trail_stop,
            at=as_of,
        )
        if isinstance(outcome, PositionManagerSkip):
            # AUTO-1A: mark rechazado / decisión no construible ⇒ motivo explícito.
            journal.append(
                _entry(
                    event_type=EVENT_POSITION_SKIP,
                    decision_id=f"SKIP-{uuid4().hex[:12]}",
                    actor=actor,
                    instrument_id=position.instrument_id,
                    payload=build_position_skip_payload(outcome),
                    at=as_of,
                )
            )
            continue
        if outcome is None:
            # Benigno (sin posición gestionable): nada que journalizar.
            continue
        position_results.append(outcome)
        journal.append(
            _entry(
                event_type=EVENT_POSITION_DECISION,
                decision_id=outcome.position.decision_id or outcome.position.trade_plan_id,
                actor=actor,
                instrument_id=outcome.position.instrument_id,
                payload=build_position_journal_payload(outcome),
                at=as_of,
            )
        )

    return AutoRunReport(
        decisions=tuple(decisions),
        position_results=tuple(position_results),
        journal_entries=tuple(journal),
        research_allocations=tuple(dict.fromkeys(research)),
        regime=resolved_regime,
        as_of=as_of,
    )
