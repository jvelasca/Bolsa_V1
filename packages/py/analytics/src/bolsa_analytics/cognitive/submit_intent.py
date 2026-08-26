"""DurableSubmitIntent — intento de envío durable (ADR-035 OR-2 · DEX-1).

Crash/restart: recorded → commit → send_attempted → adapter.submit → UNKNOWN
reconstruible. Mapeo intent ↔ venue_order_id. ≠ PaperOrder status machine (OR-3).
≠ ExecutionRecord (foto) ≠ ExecuteTrade ≠ auto-heal.

DEX-1: ``send_attempted_durable`` = fase/timestamp de envío (no «cualquier fila»).
Fila durable existente ⇒ no re-POST en Confirm (política kernel), aunque phase sea
solo ``recorded`` (crash entre put y mark).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from bolsa_analytics.cognitive.execution_record import ExecutionRecord, build_execution_record

SubmitIntentPhase = Literal["recorded", "send_attempted", "venue_bound", "filled"]

SUBMIT_INTENT_KEY = "submitIntent"

_SEND_PHASES: frozenset[SubmitIntentPhase] = frozenset(
    {"send_attempted", "venue_bound", "filled"}
)


def _non_empty(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    trimmed = value.strip()
    return trimmed or None


def _utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class DurableSubmitIntent:
    """Intento persistido. recorded ≠ send_attempted ≠ venue ack ≠ fill."""

    decision_id: str
    intent_id: str
    order_id: str
    account_id: str
    phase: SubmitIntentPhase
    venue_order_id: str | None
    reason: str | None
    venue: str = "paper"
    send_attempted_at: datetime | None = None

    def to_dict(self) -> dict[str, object]:
        attempted = self.send_attempted_at
        return {
            "decisionId": self.decision_id,
            "intentId": self.intent_id,
            "orderId": self.order_id,
            "accountId": self.account_id,
            "phase": self.phase,
            "venueOrderId": self.venue_order_id,
            "reason": self.reason,
            "venue": self.venue,
            "sendAttemptedAt": attempted.isoformat() if attempted is not None else None,
        }


def record_submit_intent(
    *,
    decision_id: str,
    intent_id: str,
    order_id: str,
    account_id: str,
    venue: str = "paper",
) -> DurableSubmitIntent:
    """Antes de adapter.submit. Fase recorded, sin venue ack ni send mark."""
    venue_norm = _non_empty(venue) or "paper"
    return DurableSubmitIntent(
        decision_id=decision_id.strip(),
        intent_id=intent_id.strip(),
        order_id=order_id.strip(),
        account_id=account_id.strip(),
        phase="recorded",
        venue_order_id=None,
        reason="crash_before_venue_ack",
        venue=venue_norm,
        send_attempted_at=None,
    )


def mark_send_attempted(
    intent: DurableSubmitIntent,
    *,
    at: datetime | None = None,
) -> DurableSubmitIntent:
    """Tras commit de recorded, antes de adapter.submit. No revierte filled/bound."""
    if intent.phase in _SEND_PHASES and intent.phase != "send_attempted":
        return intent
    if intent.phase == "send_attempted" and intent.send_attempted_at is not None:
        return intent
    stamp = at if at is not None else _utcnow()
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=UTC)
    return DurableSubmitIntent(
        decision_id=intent.decision_id,
        intent_id=intent.intent_id,
        order_id=intent.order_id,
        account_id=intent.account_id,
        phase="send_attempted",
        venue_order_id=intent.venue_order_id,
        reason=intent.reason or "crash_before_venue_ack",
        venue=intent.venue,
        send_attempted_at=intent.send_attempted_at or stamp,
    )


def bind_venue_order(
    intent: DurableSubmitIntent,
    *,
    venue_order_id: str | None,
    reason: str | None = None,
) -> DurableSubmitIntent:
    """Tras ack de venue (submitted / unknown). No es fill. Primer venue id gana."""
    existing = _non_empty(intent.venue_order_id)
    incoming = _non_empty(venue_order_id)
    bound = existing or incoming
    if intent.phase == "filled":
        return intent
    return DurableSubmitIntent(
        decision_id=intent.decision_id,
        intent_id=intent.intent_id,
        order_id=intent.order_id,
        account_id=intent.account_id,
        phase="venue_bound" if bound else intent.phase,
        venue_order_id=bound,
        reason=_non_empty(reason) or "crash_after_venue_ack",
        venue=intent.venue,
        send_attempted_at=intent.send_attempted_at,
    )


def mark_submit_filled(intent: DurableSubmitIntent) -> DurableSubmitIntent:
    """Fill local conocido. No revierte."""
    if intent.phase == "filled":
        return intent
    return DurableSubmitIntent(
        decision_id=intent.decision_id,
        intent_id=intent.intent_id,
        order_id=intent.order_id,
        account_id=intent.account_id,
        phase="filled",
        venue_order_id=intent.venue_order_id,
        reason=None,
        venue=intent.venue,
        send_attempted_at=intent.send_attempted_at,
    )


def send_attempted_durable(intent: DurableSubmitIntent | None) -> bool:
    """True si ya se marcó envío (fase o timestamp). Pure ``recorded`` = False.

    Confirm no re-POST si hay *fila* durable (aunque recorded); esa política vive
    en ``_try_recover_in_flight``, no aquí.
    """
    if intent is None:
        return False
    if intent.phase in _SEND_PHASES:
        return True
    return intent.send_attempted_at is not None


def reconstruct_unknown(intent: DurableSubmitIntent) -> ExecutionRecord:
    """OR-2 — UNKNOWN reconstruible. Nunca error ni not_executed."""
    if intent.phase in {"recorded", "send_attempted"}:
        reason = intent.reason or "crash_before_venue_ack"
    elif intent.phase == "filled":
        reason = intent.reason or "crash_after_fill_unconfirmed"
    else:
        reason = intent.reason or "crash_after_venue_ack"
    return build_execution_record(send_attempted=True, exception=reason)
