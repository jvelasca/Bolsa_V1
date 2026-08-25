"""Protect / T1 advisory (ADR-031 Ciclo 5.1 / Golden E).

Read-only: no muta structuralStop ni check_opening.
"""

from __future__ import annotations

from typing import Any, Literal

ProtectPlanStatus = Literal["none", "protect_hint"]
ProtectPlanWhy = Literal["mfe_ge_1r", "missing_inputs"]

PROTECT_PLAN_KEY = "protectPlan"


def map_protect_plan(
    *,
    direction: str | None = None,
    entry: float | None = None,
    structural_stop: float | None = None,
    last_close: float | None = None,
    target_r_multiple: float | None = None,
    open_qty: float | None = None,  # noqa: ARG001 — reserved
) -> dict[str, Any]:
    """Golden E thin: MFE ≥ 1R → protect_hint; T1 = entry ± k×R."""
    k = (
        float(target_r_multiple)
        if target_r_multiple is not None and float(target_r_multiple) > 0
        else 1.0
    )
    if direction not in ("long", "short") or entry is None or structural_stop is None or last_close is None:
        return {
            "status": "none",
            "target1": None,
            "suggestedProtectStop": None,
            "rMultiple": None,
            "why": ["missing_inputs"],
        }
    try:
        e = float(entry)
        stop = float(structural_stop)
        close = float(last_close)
    except (TypeError, ValueError):
        return {
            "status": "none",
            "target1": None,
            "suggestedProtectStop": None,
            "rMultiple": None,
            "why": ["missing_inputs"],
        }
    r = abs(e - stop)
    if r <= 0:
        return {
            "status": "none",
            "target1": None,
            "suggestedProtectStop": None,
            "rMultiple": None,
            "why": ["missing_inputs"],
        }
    sign = 1.0 if direction == "long" else -1.0
    target1 = e + sign * k * r
    mfe_r = ((close - e) / r) * sign
    why: list[str] = []
    protect = mfe_r >= 1.0
    if protect:
        why.append("mfe_ge_1r")
    return {
        "status": "protect_hint" if protect else "none",
        "target1": target1,
        "suggestedProtectStop": e if protect else None,
        "rMultiple": round(mfe_r, 4),
        "why": why,
    }


def build_protect_plan_dict(
    *,
    direction: str | None = None,
    entry: float | None = None,
    structural_stop: float | None = None,
    last_close: float | None = None,
    target_r_multiple: float | None = None,
) -> dict[str, Any]:
    return map_protect_plan(
        direction=direction,
        entry=entry,
        structural_stop=structural_stop,
        last_close=last_close,
        target_r_multiple=target_r_multiple,
    )
