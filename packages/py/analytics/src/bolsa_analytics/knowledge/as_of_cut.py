"""Point-in-time cut helpers for FA / Composite (Backtesting DÍA D).

v1: no historical FA snapshots in DB — only the latest Yahoo pack.
Policy when ``as_of`` is in the past:

* ``snapshot`` — ``fetchedAt`` calendar day ≤ as_of → safe to use the pack.
* ``blocked`` — pack was fetched after as_of → do **not** score or show
  look-ahead fundamentals (scores/facts nulled; warning stamped).
* ``live`` — no as_of / as_of ≥ today → current behaviour.

TA legs use OHLCV ``date_to=as_of`` separately (caller).
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Literal

PointInTimeStatus = Literal["live", "snapshot", "blocked", "reconstructed"]


def today_iso_utc() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def normalize_as_of_date(value: str | None) -> str | None:
    """Return YYYY-MM-DD or None. Rejects empty / invalid / future (> today UTC)."""
    if not isinstance(value, str):
        return None
    raw = value.strip()[:10]
    if len(raw) < 10:
        return None
    try:
        d = date.fromisoformat(raw)
    except ValueError:
        return None
    today = datetime.now(timezone.utc).date()
    if d > today:
        return today.isoformat()
    return d.isoformat()


def fetched_at_calendar_day(fetched_at: str | None) -> str | None:
    if not isinstance(fetched_at, str) or not fetched_at.strip():
        return None
    text = fetched_at.strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        # allow bare YYYY-MM-DD
        try:
            return date.fromisoformat(fetched_at.strip()[:10]).isoformat()
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).date().isoformat()


def resolve_fundamentals_pit(
    *,
    as_of: str | None,
    fetched_at: str | None,
    reconstructed: bool = False,
) -> PointInTimeStatus:
    """Decide whether the FA pack is usable as-of D."""
    cut = normalize_as_of_date(as_of)
    if cut is None or cut >= today_iso_utc():
        return "live"
    if reconstructed:
        return "reconstructed"
    day = fetched_at_calendar_day(fetched_at)
    if day is None:
        return "blocked"
    if day <= cut:
        return "snapshot"
    return "blocked"


def strip_lookahead_fundamentals(raw: dict[str, Any] | None) -> dict[str, Any] | None:
    """Keep only non-price narrative fields when PIT is blocked (sector)."""
    if not isinstance(raw, dict):
        return None
    sector = raw.get("sector")
    out: dict[str, Any] = {
        "fetchedAt": raw.get("fetchedAt"),
        "sourceVersion": raw.get("sourceVersion"),
    }
    if isinstance(sector, str) and sector.strip():
        out["sector"] = sector.strip()
    return out


LOOKAHEAD_BLOCKED_WARNING = (
    "FA as-of: sin pack de estados ≤ DÍA D usable — scores/ratios bloqueados "
    "(sin look-ahead). Refresca FA del valor y reintenta."
)

RECONSTRUCTED_WARNING = (
    "FA as-of: reconstruida desde estados financieros ≤ DÍA D "
    "(sin TTM live Yahoo; marketCap vía precio×acciones si hay barra)."
)
