"""Trail Plan advisory thin (ADR-031 Ciclo 8.1).

Continuous ratchet from peak MFE; hint only.
Does not mutate structuralStop, call broker, or auto-exit.
At peakMfeR=1.5 → lockedR=0.5 (aligned with Exit Radar 5.2 tip) with medium width.
V1.29: trailWidth from ExitPolicy; clamp vs currentStop (trail no empeora riesgo).
"""

from __future__ import annotations

from typing import Any, Literal

from bolsa_analytics.cognitive.exit_policy import trail_distance_r_from_width
from bolsa_analytics.cognitive.position_state import clamp_stop_not_worsen

TrailPlanStatus = Literal["none", "tip", "ratchet"]
TrailPlanWhy = Literal[
    "missing_inputs",
    "mfe_lt_1_5r",
    "aligned_exit_radar_tip",
    "ratchet_lock",
    "not_permission",
    "hint_only",
    "clamped_not_worsen",
]

TRAIL_PLAN_KEY = "trailPlan"
TRAIL_DISTANCE_R = 1.0
_TIP_MIN_MFE_R = 1.5
_RATCHET_MIN_MFE_R = 2.0


def map_trail_plan(
    *,
    direction: str | None = None,
    entry: float | None = None,
    structural_stop: float | None = None,
    peak_mfe_r: float | None = None,
    current_r: float | None = None,
    trail_width: str | None = None,
    current_stop: float | None = None,
) -> dict[str, Any]:
    """Advisory continuous trail ratchet. Never writes stops."""
    trail_distance_r = trail_distance_r_from_width(trail_width)
    base: dict[str, Any] = {
        "trailDistanceR": trail_distance_r,
        "currentR": float(current_r) if current_r is not None else None,
    }

    if direction not in ("long", "short") or entry is None or structural_stop is None:
        return {
            "status": "none",
            "suggestedTrailStop": None,
            "lockedR": None,
            "peakMfeR": None,
            **base,
            "why": ["missing_inputs"],
        }

    try:
        e = float(entry)
        stop = float(structural_stop)
    except (TypeError, ValueError):
        return {
            "status": "none",
            "suggestedTrailStop": None,
            "lockedR": None,
            "peakMfeR": None,
            **base,
            "why": ["missing_inputs"],
        }

    r = abs(e - stop)
    if r <= 0:
        return {
            "status": "none",
            "suggestedTrailStop": None,
            "lockedR": None,
            "peakMfeR": None,
            **base,
            "why": ["missing_inputs"],
        }

    peak: float | None = float(peak_mfe_r) if peak_mfe_r is not None else None
    if peak is None and current_r is not None:
        try:
            peak = max(float(current_r), 0.0)
        except (TypeError, ValueError):
            peak = None

    if peak is None:
        return {
            "status": "none",
            "suggestedTrailStop": None,
            "lockedR": None,
            "peakMfeR": None,
            **base,
            "why": ["missing_inputs"],
        }

    peak = round(max(peak, 0.0), 4)

    if peak < _TIP_MIN_MFE_R:
        return {
            "status": "none",
            "suggestedTrailStop": None,
            "lockedR": None,
            "peakMfeR": peak,
            **base,
            "why": ["mfe_lt_1_5r", "not_permission", "hint_only"],
        }

    locked_r = round(peak - trail_distance_r, 4)
    sign = 1.0 if direction == "long" else -1.0
    suggested = round(e + sign * locked_r * r, 4)
    why: list[str] = ["not_permission", "hint_only"]

    if current_stop is not None:
        try:
            cur = float(current_stop)
        except (TypeError, ValueError):
            cur = None
        else:
            if cur > 0:
                clamped = clamp_stop_not_worsen(direction, cur, suggested)
                if abs(clamped - suggested) > 1e-9:
                    why.append("clamped_not_worsen")
                    suggested = clamped

    if peak >= _RATCHET_MIN_MFE_R:
        status: TrailPlanStatus = "ratchet"
        why.append("ratchet_lock")
    else:
        status = "tip"
        why.append("aligned_exit_radar_tip")

    return {
        "status": status,
        "suggestedTrailStop": suggested,
        "lockedR": locked_r,
        "peakMfeR": peak,
        **base,
        "why": why,
    }


def build_trail_plan_dict(
    *,
    direction: str | None = None,
    entry: float | None = None,
    structural_stop: float | None = None,
    peak_mfe_r: float | None = None,
    current_r: float | None = None,
    trail_width: str | None = None,
    current_stop: float | None = None,
) -> dict[str, Any]:
    return map_trail_plan(
        direction=direction,
        entry=entry,
        structural_stop=structural_stop,
        peak_mfe_r=peak_mfe_r,
        current_r=current_r,
        trail_width=trail_width,
        current_stop=current_stop,
    )
