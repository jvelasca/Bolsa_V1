"""Thesis Health advisory (ADR-031 Ciclo 5.0 / Golden F).

Read-only: no cambia TradePlan.status ni check_opening.
Cola Hoy REVIEW (EXPIRED) ≠ thesisHealth.status == \"review\".
"""

from __future__ import annotations

from typing import Any, Literal

ThesisHealthStatus = Literal["ok", "review"]
ThesisHealthWhy = Literal[
    "confidence_degraded",
    "stop_intact",
    "hard_exit",
    "expired",
]
ConfidenceHint = Literal["hold", "tighten", "reduce", "exit", "expire"]


def _clamp01(n: float) -> float:
    return min(1.0, max(0.0, n))


def _hint_for(confidence: float, *, expired: bool, hard_exit: bool) -> ConfidenceHint:
    """Espejo de confidence_lifecycle / hintForConfidence (shared)."""
    if expired:
        return "expire"
    if hard_exit or confidence < 0.25:
        return "exit"
    if confidence < 0.45:
        return "reduce"
    if confidence < 0.65:
        return "tighten"
    return "hold"


def _stop_intact(
    direction: str | None,
    last_close: float | None,
    structural_stop: float | None,
) -> bool:
    if direction not in ("long", "short"):
        return False
    if last_close is None or structural_stop is None:
        return False
    try:
        close = float(last_close)
        stop = float(structural_stop)
    except (TypeError, ValueError):
        return False
    if direction == "long":
        return close > stop
    return close < stop


def map_thesis_health(
    *,
    confidence: float,
    direction: str | None = None,
    last_close: float | None = None,
    structural_stop: float | None = None,
    expired: bool = False,
    hard_exit: bool = False,
    open_qty: float | None = None,  # noqa: ARG001 — reserved 5.0b
) -> dict[str, Any]:
    """Golden F thin: hint degradado + stop intacto → status review."""
    conf = _clamp01(float(confidence) if confidence is not None else 0.0)
    hint: ConfidenceHint = _hint_for(conf, expired=expired, hard_exit=hard_exit)
    why: list[str] = []
    if expired:
        why.append("expired")
    if hard_exit:
        why.append("hard_exit")
    degraded = hint in ("tighten", "reduce", "exit", "expire")
    if degraded:
        why.append("confidence_degraded")
    intact = _stop_intact(direction, last_close, structural_stop)
    if intact:
        why.append("stop_intact")
    status: ThesisHealthStatus = "review" if degraded and intact else "ok"
    return {
        "hint": hint,
        "status": status,
        "why": why,
        "confidence": conf,
    }


def build_thesis_health_dict(
    *,
    confidence: float,
    direction: str | None = None,
    last_close: float | None = None,
    structural_stop: float | None = None,
    expired: bool = False,
    hard_exit: bool = False,
) -> dict[str, Any]:
    """Alias estable para propose/session runtime."""
    return map_thesis_health(
        confidence=confidence,
        direction=direction,
        last_close=last_close,
        structural_stop=structural_stop,
        expired=expired,
        hard_exit=hard_exit,
    )


THESIS_HEALTH_KEY = "thesisHealth"
