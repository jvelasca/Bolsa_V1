"""V1.32 — firma de tamaño en salida SEMI (simétrico a risk_signature)."""

from __future__ import annotations

from typing import Any

QTY_EPS = 1e-9


def _finite(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    n = float(value)
    if n != n or abs(n) == float("inf"):
        return None
    return n


def _audited(reason: object | None) -> bool:
    return isinstance(reason, str) and bool(reason.strip())


def evaluate_exit_risk_signature(
    *,
    planned_qty: float | None,
    signed_qty: float,
    override_reason: str | None = None,
) -> dict[str, Any]:
    """Qty firmada ≤ planned; exceso exige override auditable."""
    signed = _finite(signed_qty)
    if signed is None or signed <= 0:
        planned = _finite(planned_qty)
        return {
            "mode": "exit",
            "plannedQty": planned,
            "maxQty": planned,
            "overrideRequired": False,
            "allowed": False,
            "excess": None,
            "blockReason": "qty_invalid",
        }

    planned = _finite(planned_qty)
    if planned is None or planned <= 0:
        return {
            "mode": "no_plan",
            "plannedQty": None,
            "maxQty": None,
            "overrideRequired": False,
            "allowed": True,
            "excess": None,
            "blockReason": None,
        }

    excess = signed - planned
    exceeds = excess > QTY_EPS
    override = _audited(override_reason)
    return {
        "mode": "exit",
        "plannedQty": planned,
        "maxQty": planned,
        "overrideRequired": exceeds,
        "allowed": (not exceeds) or override,
        "excess": excess if exceeds else None,
        "blockReason": "qty_exceeds_plan" if exceeds and not override else None,
    }
