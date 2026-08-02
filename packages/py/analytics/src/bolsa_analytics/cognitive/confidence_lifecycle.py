"""ART-CONFIDENCE-STATE — Confidence Lifecycle (RFC-008 D7 §12)."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import uuid4

ConfidenceHint = Literal["hold", "tighten", "reduce", "exit", "expire"]
ConfidenceEventKind = Literal[
    "market_event",
    "regime_change",
    "invalidator",
    "evidence_update",
    "time_decay",
    "manual",
]


@dataclass(frozen=True, slots=True)
class ConfidenceEvent:
    kind: ConfidenceEventKind
    delta: float  # típico −1…+1 sobre confianza 0–1
    claim: str
    at: str
    refs: dict[str, str] | None = None


@dataclass(frozen=True, slots=True)
class ConfidenceState:
    """Estado de confianza de una tesis / posición abierta."""

    state_id: str
    decision_id: str
    instrument_id: str
    confidence_0: float
    confidence: float
    hint: ConfidenceHint
    expires_at: str | None
    events: tuple[ConfidenceEvent, ...]
    created_at: str
    updated_at: str
    artifact_type: str = "ART-CONFIDENCE-STATE"
    schema_version: str = "1.0.0"
    expired: bool = False
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifactType": self.artifact_type,
            "schemaVersion": self.schema_version,
            "stateId": self.state_id,
            "decisionId": self.decision_id,
            "instrumentId": self.instrument_id,
            "confidence0": self.confidence_0,
            "confidence": self.confidence,
            "hint": self.hint,
            "expiresAt": self.expires_at,
            "expired": self.expired,
            "events": [
                {
                    "kind": e.kind,
                    "delta": e.delta,
                    "claim": e.claim,
                    "at": e.at,
                    "refs": e.refs,
                }
                for e in self.events
            ],
            "notes": list(self.notes),
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
        }


def _clamp01(n: float) -> float:
    return min(1.0, max(0.0, n))


def _hint_for(confidence: float, *, expired: bool, hard_exit: bool) -> ConfidenceHint:
    if expired:
        return "expire"
    if hard_exit or confidence < 0.25:
        return "exit"
    if confidence < 0.45:
        return "reduce"
    if confidence < 0.65:
        return "tighten"
    return "hold"


def open_confidence_state(
    *,
    decision_id: str,
    instrument_id: str,
    confidence_0: float,
    expires_at: str | None = None,
    notes: list[str] | tuple[str, ...] = (),
) -> ConfidenceState:
    """Abre lifecycle desde DecisionPackage.overallConfidence (no recomputa pipeline)."""
    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    c0 = round(_clamp01(confidence_0), 4)
    return ConfidenceState(
        state_id=f"CFS-{uuid4().hex[:12]}",
        decision_id=decision_id,
        instrument_id=instrument_id,
        confidence_0=c0,
        confidence=c0,
        hint=_hint_for(c0, expired=False, hard_exit=False),
        expires_at=expires_at,
        events=(),
        created_at=now,
        updated_at=now,
        notes=tuple(notes),
    )


def apply_confidence_event(
    state: ConfidenceState,
    event: ConfidenceEvent,
    *,
    hard_exit: bool = False,
) -> ConfidenceState:
    """Actualiza confianza ante MarketEvent / régimen / invalidator / decay."""
    if state.expired:
        return state

    now = event.at
    expired = False
    if state.expires_at and now >= state.expires_at:
        expired = True

    new_c = round(_clamp01(state.confidence + event.delta), 4)
    if expired:
        new_c = min(new_c, 0.0)

    hint = _hint_for(new_c, expired=expired, hard_exit=hard_exit)
    note_extra: list[str] = []
    if event.kind == "invalidator" and event.delta < 0:
        note_extra.append(f"invalidator: {event.claim}")
    if expired:
        note_extra.append("expired")

    return replace(
        state,
        confidence=new_c,
        hint=hint,
        expired=expired,
        events=(*state.events, event),
        updated_at=now,
        notes=tuple([*state.notes, *note_extra]),
    )


def apply_time_decay(
    state: ConfidenceState,
    *,
    half_life_hours: float = 48.0,
    elapsed_hours: float,
    at: str | None = None,
) -> ConfidenceState:
    """Decay exponencial simple hacia 0 (no exige recomputar Opportunity)."""
    if state.expired or half_life_hours <= 0 or elapsed_hours <= 0:
        return state
    factor = 0.5 ** (elapsed_hours / half_life_hours)
    target = state.confidence * factor
    delta = target - state.confidence
    ts = at or datetime.now(UTC).isoformat().replace("+00:00", "Z")
    return apply_confidence_event(
        state,
        ConfidenceEvent(
            kind="time_decay",
            delta=round(delta, 4),
            claim=f"decay halfLife={half_life_hours}h elapsed={elapsed_hours:.1f}h",
            at=ts,
        ),
    )
