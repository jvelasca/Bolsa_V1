"""PositionRevision — historia auditada de stop/status (ADR-034 OI-5).

Append-only en PositionState.revisions. ≠ Journal ≠ ExecutionRecord ≠ PaperOrder.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from uuid import uuid4

PositionStatus = Literal["OPEN", "PARTIAL", "PROTECTED", "CLOSED"]
PositionRevisionOrigin = Literal["protect", "trail", "reduce", "override", "stop"]

POSITION_REVISIONS_KEY = "revisions"

_VALID_ORIGINS = frozenset({"protect", "trail", "reduce", "override", "stop"})
_VALID_STATUSES = frozenset({"OPEN", "PARTIAL", "PROTECTED", "CLOSED"})


def _non_empty(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    trimmed = value.strip()
    return trimmed or None


def _finite(value: object) -> float | None:
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if number != number:
        return None
    return number


def _status(value: object) -> PositionStatus | None:
    if isinstance(value, str) and value in _VALID_STATUSES:
        return value  # type: ignore[return-value]
    return None


@dataclass(frozen=True, slots=True)
class PositionRevision:
    """Una huella: stop y/o status anterior→nuevo + origen."""

    revision_id: str
    at: str
    previous_stop: float | None
    next_stop: float | None
    previous_status: PositionStatus | None
    next_status: PositionStatus | None
    origin: PositionRevisionOrigin
    reason: str | None

    def to_dict(self) -> dict[str, object]:
        return {
            "revisionId": self.revision_id,
            "at": self.at,
            "previousStop": self.previous_stop,
            "nextStop": self.next_stop,
            "previousStatus": self.previous_status,
            "nextStatus": self.next_status,
            "origin": self.origin,
            "reason": self.reason,
        }


def build_position_revision(
    *,
    at: str,
    previous_stop: float | None = None,
    next_stop: float | None = None,
    previous_status: PositionStatus | None = None,
    next_status: PositionStatus | None = None,
    origin: PositionRevisionOrigin = "stop",
    reason: str | None = None,
    revision_id: str | None = None,
) -> PositionRevision:
    """Factory pura. origin inválido → stop."""
    oid: PositionRevisionOrigin = origin if origin in _VALID_ORIGINS else "stop"
    rid = _non_empty(revision_id) or f"REV-{uuid4().hex[:12]}"
    when = _non_empty(at) or ""
    return PositionRevision(
        revision_id=rid,
        at=when,
        previous_stop=previous_stop,
        next_stop=next_stop,
        previous_status=previous_status,
        next_status=next_status,
        origin=oid,
        reason=_non_empty(reason),
    )


def position_revision_from_dict(raw: object) -> PositionRevision | None:
    """Rehidrata una revisión. Dict inválido → None."""
    if not isinstance(raw, dict):
        return None
    rid = _non_empty(raw.get("revisionId"))
    at = _non_empty(raw.get("at"))
    origin_raw = raw.get("origin")
    if rid is None or at is None:
        return None
    if not isinstance(origin_raw, str) or origin_raw not in _VALID_ORIGINS:
        return None
    return PositionRevision(
        revision_id=rid,
        at=at,
        previous_stop=_finite(raw.get("previousStop")),
        next_stop=_finite(raw.get("nextStop")),
        previous_status=_status(raw.get("previousStatus")),
        next_status=_status(raw.get("nextStatus")),
        origin=origin_raw,  # type: ignore[arg-type]
        reason=_non_empty(raw.get("reason")),
    )


def revisions_from_raw(raw: object) -> tuple[PositionRevision, ...]:
    """Lista JSON → tuple. Entradas inválidas se omiten."""
    if not isinstance(raw, list):
        return ()
    out: list[PositionRevision] = []
    for item in raw:
        rev = position_revision_from_dict(item)
        if rev is not None:
            out.append(rev)
    return tuple(out)


def revision_origin_from_exit_reason(
    reason: str | None,
) -> Literal["protect", "trail"]:
    """V1.44 — TRAIL → origin=trail; resto de protect enqueue → protect."""
    return "trail" if reason == "TRAIL" else "protect"


def stop_or_status_changed(
    *,
    previous_stop: float | None,
    next_stop: float | None,
    previous_status: PositionStatus | None,
    next_status: PositionStatus | None,
) -> bool:
    """True si hay cambio real de stop o status (tolerancia 1e-9 en stop)."""
    if previous_status != next_status:
        return True
    if previous_stop is None and next_stop is None:
        return False
    if previous_stop is None or next_stop is None:
        return True
    return abs(previous_stop - next_stop) > 1e-9
