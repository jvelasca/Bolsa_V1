"""V1.26 — geometría operativa única (fail-closed).

LONG: stop < entry [< T1 < T2]. SHORT: [T2 < T1 <] entry < stop.
No es ``check_opening``. No es OrderIntent.
"""

from __future__ import annotations

from typing import Any, Literal

from bolsa_analytics.cognitive.operational_invariants import adverse_exposure

OperationalLevelsDirection = Literal["long", "short"]
OperationalLevelsReason = Literal[
    "stop_wrong_side", "targets_invalid", "risk_non_positive"
]

EPS = 1e-9


def _finite(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    n = float(value)
    if n != n or abs(n) == float("inf"):
        return None
    return n


def _direction(raw: object) -> OperationalLevelsDirection | None:
    return raw if raw in ("long", "short") else None


def validate_operational_levels(
    *,
    direction: object,
    entry: object,
    stop: object,
    target1: object = None,
    target2: object = None,
) -> dict[str, Any]:
    """Predicado puro. ``ok`` + ``reason`` canónico + ``riskDistance``."""
    side = _direction(direction)
    px = _finite(entry)
    sl = _finite(stop)
    if side is None or px is None or px <= 0 or sl is None or sl <= 0:
        return {"ok": False, "reason": "risk_non_positive", "riskDistance": None}

    side_ok = sl < px - EPS if side == "long" else sl > px + EPS
    if not side_ok:
        return {"ok": False, "reason": "stop_wrong_side", "riskDistance": None}

    risk_distance = adverse_exposure(side, px, sl)
    if risk_distance <= EPS:
        return {"ok": False, "reason": "risk_non_positive", "riskDistance": 0.0}

    t1 = _finite(target1)
    t2 = _finite(target2)
    if t1 is not None:
        t1_ok = t1 > px + EPS if side == "long" else t1 < px - EPS
        if not t1_ok:
            return {
                "ok": False,
                "reason": "targets_invalid",
                "riskDistance": risk_distance,
            }
    if t2 is not None:
        t2_ok = t2 > px + EPS if side == "long" else t2 < px - EPS
        if not t2_ok:
            return {
                "ok": False,
                "reason": "targets_invalid",
                "riskDistance": risk_distance,
            }
    if t1 is not None and t2 is not None:
        ordered = t2 > t1 + EPS if side == "long" else t2 < t1 - EPS
        if not ordered:
            return {
                "ok": False,
                "reason": "targets_invalid",
                "riskDistance": risk_distance,
            }

    return {"ok": True, "reason": None, "riskDistance": risk_distance}
