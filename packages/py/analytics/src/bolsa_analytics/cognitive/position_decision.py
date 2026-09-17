"""PositionDecision — proyección operativa (V1.27). No durable, no segundo motor."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from bolsa_analytics.cognitive.exit_plan import (
    ExitPlan,
    ExitPlanStatus,
    build_exit_plan_from_position,
)
from bolsa_analytics.cognitive.exit_policy import ExitPolicy, resolve_exit_policy
from bolsa_analytics.cognitive.position_state import PositionState

PositionDecisionAction = Literal[
    "HOLD", "PROTECT", "REDUCE", "TAKE_PROFIT", "EXIT", "REVIEW"
]
PositionAttention = Literal["NORMAL", "ATTENTION", "URGENT", "BLOCKED"]
PositionNextEvent = Literal[
    "NONE", "T1", "T2", "STOP", "TRAIL", "TIME", "THESIS_REVIEW", "RECONCILIATION"
]
PositionReconHealth = Literal["CLEAN", "ATTENTION", "CRITICAL"]
PositionProtection = Literal["ACTIVE", "NONE"]
PositionUrgency = Literal["LOW", "MEDIUM", "HIGH"]

POSITION_DECISION_KEY = "positionDecision"

_ATT_RANK = {"NORMAL": 0, "ATTENTION": 1, "URGENT": 2, "BLOCKED": 3}

_STATUS_CONFIDENCE: dict[ExitPlanStatus, float] = {
    "TRIGGERED": 0.9,
    "ARMED": 0.75,
    "HINT": 0.65,
    "IDLE": 0.55,
    "DONE": 0.5,
}

_RECON_CONFIDENCE: dict[PositionReconHealth, float] = {
    "CLEAN": 1.0,
    "ATTENTION": 0.85,
    "CRITICAL": 0.5,
}


def map_recon_status_to_health(status: str | None) -> PositionReconHealth:
    s = (status or "").strip().lower()
    if s == "drift":
        return "CRITICAL"
    if s in ("clean", "ok"):
        return "CLEAN"
    return "ATTENTION"


def recon_health_to_attention(health: PositionReconHealth) -> PositionAttention:
    if health == "CRITICAL":
        return "BLOCKED"
    if health == "ATTENTION":
        return "ATTENTION"
    return "NORMAL"


def attention_to_urgency(attention: PositionAttention) -> PositionUrgency:
    if attention in ("URGENT", "BLOCKED"):
        return "HIGH"
    if attention == "ATTENTION":
        return "MEDIUM"
    return "LOW"


#: Salidas PROTECTORAS: deshacer riesgo no espera a la reconciliación (invariante de oro
#: del roadmap AUTO-2 §6.4). Con el libro sin verificar, ``CRITICAL`` degrada a ``REVIEW``
#: **salvo** cuando el plan pide reducir riesgo ya (stop rebasado, trail alcanzado, riesgo
#: de cartera): en ese caso manda la salida. Cualquier otro motivo (objetivos, manual,
#: tesis, tiempo) sigue vetado: tomar beneficio puede esperar, no cubrirse no.
#: ``TIME_STOP`` NO entra (una salida por tiempo no es cubrirse) y ``THESIS_INVALIDATION``
#: tampoco (decisión D2 de 2b: vende cuando la reconciliación lo permite, y su veto bajo
#: ``CRITICAL`` se declara en vez de silenciarse).
_PROTECTIVE_EXIT_REASONS: frozenset[str] = frozenset(
    {"STRUCTURAL_STOP", "TRAIL", "PORTFOLIO_RISK"}
)


def _max_attention(a: PositionAttention, b: PositionAttention) -> PositionAttention:
    return a if _ATT_RANK[a] >= _ATT_RANK[b] else b


def _protection_state(position: PositionState) -> PositionProtection:
    if position.current_stop is not None:
        return "ACTIVE"
    return "NONE"


def _next_event(position: PositionState, exit_plan: ExitPlan) -> PositionNextEvent:
    primary = exit_plan.primary_reason
    if primary == "STRUCTURAL_STOP":
        return "STOP"
    if primary == "THESIS_INVALIDATION":
        return "THESIS_REVIEW"
    if primary == "TARGET_1":
        return "T1"
    if primary == "TARGET_2":
        return "T2"
    if primary == "TRAIL":
        return "TRAIL"
    if primary == "TIME_STOP":
        # V2.42 slice 2b (E1): el techo de mantenimiento es el motivo; que no se confunda
        # con "esperando T1/T2" (antes caía en la rama de objetivos).
        return "TIME"
    if not position.target1_achieved_at and position.target1 is not None:
        return "T1"
    if not position.target2_achieved_at and position.target2 is not None:
        return "T2"
    return "NONE"


def _mark_proximity_factor(
    position: PositionState,
    *,
    mark_price: float | None,
    next_event: PositionNextEvent,
) -> float:
    if mark_price is None or mark_price != mark_price:
        return 0.85
    target: float | None = None
    if next_event == "T1" and position.target1 is not None:
        target = position.target1
    elif next_event == "T2" and position.target2 is not None:
        target = position.target2
    if target is None or target <= 0:
        return 0.9
    entry = position.actual_entry or position.planned_entry
    if entry is None or entry <= 0:
        return 0.9
    span = abs(target - entry)
    if span <= 1e-9:
        return 0.9
    progress = abs(mark_price - entry) / span
    return min(1.0, max(0.75, 0.75 + progress * 0.25))


def _evidence_strength(
    exit_plan: ExitPlan,
    recon_health: PositionReconHealth,
    *,
    mark_price: float | None,
) -> float:
    score = 0.2
    if exit_plan.primary_reason:
        score += 0.25
    if mark_price is not None and mark_price == mark_price:
        score += 0.2
    if recon_health == "CLEAN":
        score += 0.2
    elif recon_health == "ATTENTION":
        score += 0.1
    if exit_plan.status in ("TRIGGERED", "ARMED"):
        score += 0.15
    return round(min(1.0, max(0.0, score)), 4)


def _decision_confidence(
    exit_plan: ExitPlan,
    recon_health: PositionReconHealth,
    position: PositionState,
    *,
    mark_price: float | None,
    next_event: PositionNextEvent,
) -> float:
    base = _STATUS_CONFIDENCE.get(exit_plan.status, 0.55)
    recon = _RECON_CONFIDENCE.get(recon_health, 0.85)
    proximity = _mark_proximity_factor(
        position, mark_price=mark_price, next_event=next_event
    )
    value = base * recon * proximity
    return round(min(1.0, max(0.0, value)), 4)


def _action_from_plan(
    exit_plan: ExitPlan,
    recon_health: PositionReconHealth,
    thesis_invalid: bool,
) -> PositionDecisionAction:
    # H-4/§6.4: una salida PROTECTORA no se veta por reconciliación; cualquier otro motivo
    # bajo ``CRITICAL`` degrada a ``REVIEW`` (tomar beneficio puede esperar).
    if (
        recon_health == "CRITICAL"
        and exit_plan.primary_reason not in _PROTECTIVE_EXIT_REASONS
    ):
        return "REVIEW"
    # V2.42 slice 2b (E3 · decisión D2 firmada por el owner): la invalidación CONFIRMADA
    # de la tesis es una salida REAL (proteger capital), no un ``REVIEW``. Antes esto
    # devolvía ``REVIEW`` ⇒ el AUTO declaraba la tesis rota y NO vendía: la posición
    # sobrevivía a su propia invalidación. ``THESIS_INVALIDATION`` está en
    # ``_HARD_TRIGGER`` (``exit_plan``), de modo que el plan ya pidió ``full_exit``; aquí
    # sólo se deja de vetar. Bajo ``CRITICAL`` sigue mandando la rama de arriba (la
    # invalidación NO está en ``_PROTECTIVE_EXIT_REASONS``): el veto de reconciliación
    # está declarado, no silenciado.
    if thesis_invalid or exit_plan.primary_reason == "THESIS_INVALIDATION":
        return "EXIT"
    sug = exit_plan.suggested_action
    primary = exit_plan.primary_reason
    if sug == "protect":
        return "PROTECT"
    if sug == "full_exit":
        return "EXIT"
    if sug == "reduce":
        if primary in ("TARGET_1", "TARGET_2"):
            return "TAKE_PROFIT"
        return "REDUCE"
    return "HOLD"


@dataclass(frozen=True, slots=True)
class PositionDecision:
    position_id: str
    trade_plan_id: str
    action: PositionDecisionAction
    reason: str
    confidence: float
    urgency: PositionUrgency
    evidence_strength: float
    attention: PositionAttention
    next_event: PositionNextEvent
    protection: PositionProtection
    recon_health: PositionReconHealth
    suggested_qty: float | None
    suggested_stop: float | None
    primary_reason: str | None
    market_as_of: str | None
    expires_at: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "positionId": self.position_id,
            "tradePlanId": self.trade_plan_id,
            "action": self.action,
            "reason": self.reason,
            "confidence": self.confidence,
            "urgency": self.urgency,
            "evidenceStrength": self.evidence_strength,
            "attention": self.attention,
            "nextEvent": self.next_event,
            "protection": self.protection,
            "reconHealth": self.recon_health,
            "suggestedQty": self.suggested_qty,
            "suggestedStop": self.suggested_stop,
            "primaryReason": self.primary_reason,
            "marketAsOf": self.market_as_of,
            "expiresAt": self.expires_at,
        }


def build_position_decision(
    position: PositionState | None,
    *,
    mark_price: float | None = None,
    exit_policy: ExitPolicy | None = None,
    template_id: str | None = None,
    portfolio_recon_status: str | None = None,
    thesis_invalid: bool = False,
    at: str | None = None,
    now: str | None = None,
    expires_at: str | None = None,
    trail_hint: bool = False,
    trail_stop: float | None = None,
) -> PositionDecision | None:
    if position is None:
        return None
    if position.direction not in ("long", "short"):
        return None
    # AUTO-2: fuente ÚNICA de política. Antes ``template_id=None`` ⇒ ``policy=None`` ⇒ el
    # fallback suelto de ``suggestion_from_exit_policy`` (0.5/1.0) hacía que los dos
    # caminos AUTO cerraran T1 con fracciones distintas. ``resolve_exit_policy`` ya tiene
    # MODERATE como default declarado: se usa siempre, sin rama silenciosa.
    policy = exit_policy if exit_policy is not None else resolve_exit_policy(template_id)
    exit_plan = build_exit_plan_from_position(
        position,
        mark_price=mark_price,
        now=now,
        expires_at=expires_at,
        thesis_invalid=thesis_invalid,
        trail_hint=trail_hint,
        trail_stop=trail_stop,
        at=at,
        exit_policy=policy,
    )
    if exit_plan is None:
        return None

    recon_health = map_recon_status_to_health(portfolio_recon_status)
    attention = recon_health_to_attention(recon_health)
    action = _action_from_plan(exit_plan, recon_health, thesis_invalid)
    primary = exit_plan.primary_reason
    protection = _protection_state(position)

    if primary == "STRUCTURAL_STOP":
        attention = _max_attention(attention, "URGENT")
    elif thesis_invalid or primary == "THESIS_INVALIDATION":
        attention = _max_attention(attention, "URGENT")
    elif action in ("REDUCE", "TAKE_PROFIT", "EXIT", "PROTECT"):
        attention = _max_attention(attention, "ATTENTION")

    if recon_health == "CRITICAL":
        reason = "reconciliation:portfolio_drift"
        next_event: PositionNextEvent = "RECONCILIATION"
    elif primary:
        reason = primary.lower()
        next_event = _next_event(position, exit_plan)
    else:
        reason = "hold"
        next_event = _next_event(position, exit_plan)

    urgency = attention_to_urgency(attention)
    evidence_strength = _evidence_strength(
        exit_plan, recon_health, mark_price=mark_price
    )
    confidence = _decision_confidence(
        exit_plan,
        recon_health,
        position,
        mark_price=mark_price,
        next_event=next_event,
    )
    stamp = at or exit_plan.updated_at

    return PositionDecision(
        position_id=position.position_id,
        trade_plan_id=position.trade_plan_id,
        action=action,
        reason=reason,
        confidence=confidence,
        urgency=urgency,
        evidence_strength=evidence_strength,
        attention=attention,
        next_event=next_event,
        protection=protection,
        recon_health=recon_health,
        suggested_qty=exit_plan.suggested_qty,
        suggested_stop=exit_plan.suggested_stop,
        primary_reason=primary,
        market_as_of=stamp,
        expires_at=None,
    )
