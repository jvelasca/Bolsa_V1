"""V1.48 — PositionEvent durable log in position_state JSONB (no Alembic table).

TRAIL/PROTECT identity = (positionId, eventType, nextStop).
T1/STOP identity = (positionId, eventType, asOf-day, action).
eventId is server-derived and stable; sequence is assigned on create.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date
from typing import Any, Literal

from bolsa_application.auto_execute_idempotency import as_of_from_iso

POSITION_EVENTS_KEY = "events"

PositionEventAction = Literal["protect", "reduce", "exit"]


def _trim(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


def _finite(value: object) -> float | None:
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if number != number:
        return None
    return number


def _round4(value: float) -> float:
    return round(value + 0.0, 4)


def event_as_of_day(raw: date | str | None) -> str:
    if isinstance(raw, date):
        return raw.isoformat()
    return as_of_from_iso(str(raw) if raw else None)


@dataclass(frozen=True, slots=True)
class DurablePositionEvent:
    event_id: str
    position_id: str
    event_type: str
    as_of: str
    sequence: int
    action: PositionEventAction
    detected_at: str | None = None
    next_stop: float | None = None
    quantity: float | None = None
    revision_id: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "eventId": self.event_id,
            "positionId": self.position_id,
            "eventType": self.event_type,
            "asOf": self.as_of,
            "sequence": self.sequence,
            "action": self.action,
            "detectedAt": self.detected_at,
            "nextStop": self.next_stop,
            "quantity": self.quantity,
            "revisionId": self.revision_id,
        }


def durable_event_from_dict(raw: object) -> DurablePositionEvent | None:
    if not isinstance(raw, dict):
        return None
    event_id = _trim(raw.get("eventId") or raw.get("event_id"))
    position_id = _trim(raw.get("positionId") or raw.get("position_id"))
    event_type = _trim(raw.get("eventType") or raw.get("event_type"))
    as_of = _trim(raw.get("asOf") or raw.get("as_of"))
    action_raw = _trim(raw.get("action")) or "protect"
    if event_id is None or position_id is None or event_type is None or as_of is None:
        return None
    if action_raw not in ("protect", "reduce", "exit"):
        return None
    seq_raw = raw.get("sequence")
    try:
        sequence = max(int(seq_raw), 1) if seq_raw is not None else 1
    except (TypeError, ValueError):
        sequence = 1
    return DurablePositionEvent(
        event_id=event_id,
        position_id=position_id,
        event_type=event_type,
        as_of=as_of[:10],
        sequence=sequence,
        action=action_raw,  # type: ignore[arg-type]
        detected_at=_trim(raw.get("detectedAt") or raw.get("detected_at")),
        next_stop=_finite(raw.get("nextStop") or raw.get("next_stop")),
        quantity=_finite(raw.get("quantity")),
        revision_id=_trim(raw.get("revisionId") or raw.get("revision_id")),
    )


def events_from_blob(blob: dict[str, Any] | None) -> list[DurablePositionEvent]:
    if not isinstance(blob, dict):
        return []
    raw = blob.get(POSITION_EVENTS_KEY)
    if not isinstance(raw, list):
        return []
    out: list[DurablePositionEvent] = []
    for item in raw:
        ev = durable_event_from_dict(item)
        if ev is not None:
            out.append(ev)
    return out


def write_events_to_blob(
    blob: dict[str, Any],
    events: list[DurablePositionEvent],
) -> dict[str, Any]:
    next_blob = dict(blob)
    next_blob[POSITION_EVENTS_KEY] = [e.to_dict() for e in events]
    return next_blob


def preserve_position_events(
    previous_blob: dict[str, Any] | None,
    next_blob: dict[str, Any],
) -> dict[str, Any]:
    """to_dict() de PositionState no incluye events — no perder el log."""
    if POSITION_EVENTS_KEY in next_blob and isinstance(next_blob[POSITION_EVENTS_KEY], list):
        return next_blob
    if not isinstance(previous_blob, dict):
        return next_blob
    raw = previous_blob.get(POSITION_EVENTS_KEY)
    if isinstance(raw, list):
        next_blob[POSITION_EVENTS_KEY] = list(raw)
    return next_blob


def make_durable_event_id(
    *,
    position_id: str,
    event_type: str,
    action: str,
    as_of_day: str | None = None,
    next_stop: float | None = None,
) -> str:
    """Identidad estable 16–128 chars (ExecuteTrade). No incluye sequence ni qty."""
    pos = (position_id or "").strip() or "pos"
    ev = (event_type or "").strip() or "UNKNOWN"
    act = (action or "").strip() or "protect"
    if act == "protect" and next_stop is not None:
        material = f"{pos}|{ev}|{act}|{_round4(float(next_stop)):.4f}"
    else:
        day = (as_of_day or "").strip()[:10] or "0000-00-00"
        material = f"{pos}|{ev}|{act}|{day}"
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:32]
    return f"EVT-{digest}"


def event_identity_matches(
    event: DurablePositionEvent,
    *,
    position_id: str,
    event_type: str,
    action: str,
    as_of_day: str,
    next_stop: float | None,
) -> bool:
    if event.position_id != position_id or event.event_type != event_type:
        return False
    if event.action != action:
        return False
    if action == "protect":
        if next_stop is None or event.next_stop is None:
            return False
        return abs(float(event.next_stop) - _round4(float(next_stop))) <= 1e-9
    return event.as_of[:10] == as_of_day[:10]


def find_matching_event(
    events: list[DurablePositionEvent],
    *,
    position_id: str,
    event_type: str,
    action: str,
    as_of_day: str,
    next_stop: float | None,
) -> DurablePositionEvent | None:
    for event in events:
        if event_identity_matches(
            event,
            position_id=position_id,
            event_type=event_type,
            action=action,
            as_of_day=as_of_day,
            next_stop=next_stop,
        ):
            return event
    return None


def next_sequence_for(
    events: list[DurablePositionEvent],
    *,
    event_type: str,
    as_of_day: str,
) -> int:
    n = 0
    day = as_of_day[:10]
    for event in events:
        if event.event_type == event_type and event.as_of[:10] == day:
            n += 1
    return n + 1


def claim_durable_event(
    blob: dict[str, Any],
    *,
    position_id: str,
    event_type: str,
    action: PositionEventAction,
    as_of: str | None,
    next_stop: float | None = None,
    quantity: float | None = None,
    revision_id: str | None = None,
    detected_at: str | None = None,
) -> tuple[dict[str, Any], DurablePositionEvent, bool]:
    """Upsert por identidad. Devuelve (blob, event, created)."""
    day = event_as_of_day(as_of)
    events = events_from_blob(blob)
    existing = find_matching_event(
        events,
        position_id=position_id,
        event_type=event_type,
        action=action,
        as_of_day=day,
        next_stop=next_stop,
    )
    if existing is not None:
        linked = existing
        if revision_id and not existing.revision_id:
            linked = DurablePositionEvent(
                event_id=existing.event_id,
                position_id=existing.position_id,
                event_type=existing.event_type,
                as_of=existing.as_of,
                sequence=existing.sequence,
                action=existing.action,
                detected_at=existing.detected_at or detected_at,
                next_stop=existing.next_stop,
                quantity=existing.quantity if existing.quantity is not None else quantity,
                revision_id=revision_id,
            )
            events = [linked if e.event_id == existing.event_id else e for e in events]
            return write_events_to_blob(blob, events), linked, False
        return write_events_to_blob(blob, events), existing, False

    event_id = make_durable_event_id(
        position_id=position_id,
        event_type=event_type,
        action=action,
        as_of_day=day,
        next_stop=next_stop,
    )
    created = DurablePositionEvent(
        event_id=event_id,
        position_id=position_id,
        event_type=event_type,
        as_of=day,
        sequence=next_sequence_for(events, event_type=event_type, as_of_day=day),
        action=action,
        detected_at=detected_at or as_of,
        next_stop=_round4(float(next_stop)) if next_stop is not None else None,
        quantity=float(quantity) if quantity is not None else None,
        revision_id=revision_id,
    )
    events.append(created)
    return write_events_to_blob(blob, events), created, True
