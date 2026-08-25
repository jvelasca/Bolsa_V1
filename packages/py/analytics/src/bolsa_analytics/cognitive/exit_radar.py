"""Exit Radar advisory (ADR-031 Ciclo 5.2).

Read-only: no auto-exit, no muta structuralStop, no check_opening.
Priority: exit_hint > time_stop_hint > trail_hint > none.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

ExitRadarStatus = Literal["none", "trail_hint", "time_stop_hint", "exit_hint"]
ExitRadarWhy = Literal[
    "thesis_exit",
    "beyond_target1",
    "expired",
    "mfe_ge_1_5r",
    "missing_inputs",
]

EXIT_RADAR_KEY = "exitRadar"


def _parse_iso(value: str | None) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    raw = value.strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt


def _is_expired(expires_at: str | None, now_iso: str | None = None) -> bool:
    exp = _parse_iso(expires_at)
    if exp is None:
        return False
    now = _parse_iso(now_iso) if now_iso else datetime.now(UTC)
    if now is None:
        return False
    return now >= exp


def map_exit_radar(
    *,
    direction: str | None = None,
    entry: float | None = None,
    structural_stop: float | None = None,
    last_close: float | None = None,
    expires_at: str | None = None,
    now_iso: str | None = None,
    thesis_hint: str | None = None,
    target1: float | None = None,
    r_multiple: float | None = None,
) -> dict[str, Any]:
    """Composes exit/trail/time-stop advisory. Does not execute."""
    why: list[str] = []
    r_mult = float(r_multiple) if r_multiple is not None else None
    explicit_t1: float | None = float(target1) if target1 is not None else None
    t1 = explicit_t1
    suggested_trail: float | None = None

    has_geometry = direction in ("long", "short") and entry is not None and structural_stop is not None
    if has_geometry:
        try:
            e = float(entry)
            stop = float(structural_stop)
        except (TypeError, ValueError):
            has_geometry = False
            e = 0.0
            stop = 0.0
        else:
            r = abs(e - stop)
            if r > 0:
                sign = 1.0 if direction == "long" else -1.0
                if t1 is None:
                    t1 = e + sign * r
                if r_mult is None and last_close is not None:
                    try:
                        close = float(last_close)
                        r_mult = round(((close - e) / r) * sign, 4)
                    except (TypeError, ValueError):
                        pass
                if r_mult is not None and r_mult >= 1.5:
                    why.append("mfe_ge_1_5r")
                    suggested_trail = e + sign * 0.5 * r

    thesis_exit = thesis_hint in ("exit", "reduce")
    if thesis_exit:
        why.append("thesis_exit")

    # Beyond T1 only when target1 came from protectPlan (explicit).
    beyond = False
    if explicit_t1 is not None and direction in ("long", "short") and last_close is not None:
        try:
            close = float(last_close)
            beyond = close >= explicit_t1 if direction == "long" else close <= explicit_t1
        except (TypeError, ValueError):
            beyond = False
        if beyond:
            why.append("beyond_target1")

    expired = _is_expired(expires_at, now_iso)
    if expired:
        why.append("expired")

    if thesis_exit or beyond:
        return {
            "status": "exit_hint",
            "suggestedTrailStop": suggested_trail,
            "target1": t1,
            "rMultiple": r_mult,
            "why": why,
        }
    if expired:
        return {
            "status": "time_stop_hint",
            "suggestedTrailStop": suggested_trail,
            "target1": t1,
            "rMultiple": r_mult,
            "why": why,
        }
    if suggested_trail is not None:
        return {
            "status": "trail_hint",
            "suggestedTrailStop": suggested_trail,
            "target1": t1,
            "rMultiple": r_mult,
            "why": why,
        }

    if not has_geometry and not thesis_exit and not expired:
        why.append("missing_inputs")

    return {
        "status": "none",
        "suggestedTrailStop": None,
        "target1": t1,
        "rMultiple": r_mult,
        "why": why,
    }


def build_exit_radar_dict(
    *,
    direction: str | None = None,
    entry: float | None = None,
    structural_stop: float | None = None,
    last_close: float | None = None,
    expires_at: str | None = None,
    now_iso: str | None = None,
    thesis_hint: str | None = None,
    target1: float | None = None,
    r_multiple: float | None = None,
) -> dict[str, Any]:
    return map_exit_radar(
        direction=direction,
        entry=entry,
        structural_stop=structural_stop,
        last_close=last_close,
        expires_at=expires_at,
        now_iso=now_iso,
        thesis_hint=thesis_hint,
        target1=target1,
        r_multiple=r_multiple,
    )
