"""Bracket Plan advisory thin (ADR-031 Ciclo 8.2).

Structural picture: entry / stop / T1(1R) / T2(2R) + display-only leg fracs.
Aligns Protect 5.1 T1 = entry±1R. Does not place OCO, call broker, or auto-exit.
"""

from __future__ import annotations

from typing import Any, Literal

BracketPlanStatus = Literal["none", "picture"]
BracketPlanWhy = Literal[
    "missing_inputs",
    "aligned_protect_t1",
    "display_only",
    "not_permission",
    "hint_only",
    "no_broker_oco",
]

BRACKET_PLAN_KEY = "bracketPlan"
BRACKET_T1_R = 1.0
BRACKET_T2_R = 2.0
BRACKET_LEG_T1_FRAC = 0.5
BRACKET_LEG_T2_FRAC = 0.5


def map_bracket_plan(
    *,
    direction: str | None = None,
    entry: float | None = None,
    structural_stop: float | None = None,
) -> dict[str, Any]:
    """Advisory structural bracket picture. Never places orders."""
    base: dict[str, Any] = {
        "target1R": BRACKET_T1_R,
        "target2R": BRACKET_T2_R,
    }

    if direction not in ("long", "short") or entry is None or structural_stop is None:
        return {
            "status": "none",
            "entry": None,
            "stop": None,
            "target1": None,
            "target2": None,
            **base,
            "legT1QtyFrac": None,
            "legT2QtyFrac": None,
            "why": ["missing_inputs"],
        }

    try:
        e = float(entry)
        stop = float(structural_stop)
    except (TypeError, ValueError):
        return {
            "status": "none",
            "entry": None,
            "stop": None,
            "target1": None,
            "target2": None,
            **base,
            "legT1QtyFrac": None,
            "legT2QtyFrac": None,
            "why": ["missing_inputs"],
        }

    r = abs(e - stop)
    if r <= 0:
        return {
            "status": "none",
            "entry": None,
            "stop": None,
            "target1": None,
            "target2": None,
            **base,
            "legT1QtyFrac": None,
            "legT2QtyFrac": None,
            "why": ["missing_inputs"],
        }

    sign = 1.0 if direction == "long" else -1.0
    target1 = round(e + sign * BRACKET_T1_R * r, 4)
    target2 = round(e + sign * BRACKET_T2_R * r, 4)

    return {
        "status": "picture",
        "entry": round(e, 4),
        "stop": round(stop, 4),
        "target1": target1,
        "target2": target2,
        **base,
        "legT1QtyFrac": BRACKET_LEG_T1_FRAC,
        "legT2QtyFrac": BRACKET_LEG_T2_FRAC,
        "why": [
            "aligned_protect_t1",
            "display_only",
            "not_permission",
            "hint_only",
            "no_broker_oco",
        ],
    }


def build_bracket_plan_dict(
    *,
    direction: str | None = None,
    entry: float | None = None,
    structural_stop: float | None = None,
) -> dict[str, Any]:
    return map_bracket_plan(
        direction=direction,
        entry=entry,
        structural_stop=structural_stop,
    )
