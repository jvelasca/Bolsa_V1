"""MFE/MAE excursion advisory (ADR-031 Ciclo 5.3).

Read-only metrics: peak favorable/adverse in R. No protect/exit tips, no fill gate.
"""

from __future__ import annotations

from typing import Any, Literal, Sequence

MfeMaeStatus = Literal["none", "observe", "favorable", "adverse"]
MfeMaeWhy = Literal[
    "peak_from_bars",
    "close_proxy",
    "mae_ge_1r",
    "mfe_ge_1_5r",
    "missing_inputs",
]

MFE_MAE_KEY = "mfeMae"


def map_mfe_mae(
    *,
    direction: str | None = None,
    entry: float | None = None,
    structural_stop: float | None = None,
    last_close: float | None = None,
    bars: Sequence[dict[str, Any] | Any] | None = None,
) -> dict[str, Any]:
    """Peak MFE/MAE in R from bars when available; else lastClose proxy."""
    if direction not in ("long", "short") or entry is None or structural_stop is None:
        return {
            "status": "none",
            "mfeR": None,
            "maeR": None,
            "currentR": None,
            "why": ["missing_inputs"],
        }

    try:
        e = float(entry)
        stop = float(structural_stop)
    except (TypeError, ValueError):
        return {
            "status": "none",
            "mfeR": None,
            "maeR": None,
            "currentR": None,
            "why": ["missing_inputs"],
        }

    r = abs(e - stop)
    if r <= 0:
        return {
            "status": "none",
            "mfeR": None,
            "maeR": None,
            "currentR": None,
            "why": ["missing_inputs"],
        }

    sign = 1.0 if direction == "long" else -1.0
    why: list[str] = []

    current_r: float | None = None
    if last_close is not None:
        try:
            close = float(last_close)
            current_r = round(((close - e) / r) * sign, 4)
        except (TypeError, ValueError):
            current_r = None

    used_bars = False
    peak_fav = 0.0
    peak_adv = 0.0

    if bars:
        for bar in bars:
            try:
                if isinstance(bar, dict):
                    high = float(bar["high"])
                    low = float(bar["low"])
                else:
                    high = float(getattr(bar, "high"))
                    low = float(getattr(bar, "low"))
            except (KeyError, TypeError, ValueError, AttributeError):
                continue
            used_bars = True
            if direction == "long":
                peak_fav = max(peak_fav, high - e)
                peak_adv = max(peak_adv, e - low)
            else:
                peak_fav = max(peak_fav, e - low)
                peak_adv = max(peak_adv, high - e)

    if used_bars:
        why.append("peak_from_bars")
        mfe_r = round(max(peak_fav, 0.0) / r, 4)
        mae_r = round(max(peak_adv, 0.0) / r, 4)
    elif current_r is not None:
        why.append("close_proxy")
        mfe_r = round(max(current_r, 0.0), 4)
        mae_r = round(max(-current_r, 0.0), 4)
    else:
        return {
            "status": "none",
            "mfeR": None,
            "maeR": None,
            "currentR": None,
            "why": ["missing_inputs"],
        }

    if mae_r >= 1.0:
        why.append("mae_ge_1r")
    if mfe_r >= 1.5:
        why.append("mfe_ge_1_5r")

    status: MfeMaeStatus = "observe"
    if mae_r >= 1.0:
        status = "adverse"
    elif mfe_r >= 1.5:
        status = "favorable"

    return {
        "status": status,
        "mfeR": mfe_r,
        "maeR": mae_r,
        "currentR": current_r,
        "why": why,
    }


def build_mfe_mae_dict(
    *,
    direction: str | None = None,
    entry: float | None = None,
    structural_stop: float | None = None,
    last_close: float | None = None,
    bars: Sequence[dict[str, Any] | Any] | None = None,
) -> dict[str, Any]:
    return map_mfe_mae(
        direction=direction,
        entry=entry,
        structural_stop=structural_stop,
        last_close=last_close,
        bars=bars,
    )
