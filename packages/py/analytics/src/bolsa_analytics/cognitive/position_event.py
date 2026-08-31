"""PositionEvent — vista canónica de ExitReason (V1.44). ≠ ExitPlan."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from bolsa_analytics.cognitive.exit_plan import ExitReason

PositionEventKind = Literal[
    "STOP",
    "T1",
    "T2",
    "TRAIL",
    "INVALIDATION",
    "TIME",
    "PORTFOLIO_RISK",
    "MANUAL",
]

_KIND_BY_REASON: dict[str, PositionEventKind] = {
    "STRUCTURAL_STOP": "STOP",
    "TARGET_1": "T1",
    "TARGET_2": "T2",
    "TRAIL": "TRAIL",
    "THESIS_INVALIDATION": "INVALIDATION",
    "TIME_STOP": "TIME",
    "PORTFOLIO_RISK": "PORTFOLIO_RISK",
    "MANUAL": "MANUAL",
}


@dataclass(frozen=True, slots=True)
class PositionEvent:
    kind: PositionEventKind
    reason_code: ExitReason
    at: str


def position_event_kind_from_reason(reason: str | None) -> PositionEventKind | None:
    if not reason:
        return None
    return _KIND_BY_REASON.get(reason)


def build_position_event(reason: str | None, at: str) -> PositionEvent | None:
    kind = position_event_kind_from_reason(reason)
    if kind is None or not reason or not isinstance(at, str) or not at.strip():
        return None
    return PositionEvent(kind=kind, reason_code=reason, at=at)  # type: ignore[arg-type]


def is_target_event_kind(kind: PositionEventKind | None) -> bool:
    return kind in ("T1", "T2", "TIME")


def is_immediate_risk_reason(reason: str | None) -> bool:
    return reason in (
        "STRUCTURAL_STOP",
        "THESIS_INVALIDATION",
        "PORTFOLIO_RISK",
    )
