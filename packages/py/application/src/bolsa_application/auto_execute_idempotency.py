"""OR-T4 — clave de idempotencia para execute AUTO / paper_auto.

Evita doble fill del mismo instrumento×día×política×kind.
"""

from __future__ import annotations

from datetime import date


def make_auto_execute_idempotency_key(
    instrument_id: str,
    as_of: date | str,
    policy_id: str,
    kind: str = "entry_long",
) -> str:
    """Clave estable: instrument|asOf|policy|kind."""
    as_of_s = as_of.isoformat() if isinstance(as_of, date) else str(as_of).strip()[:10]
    return f"{instrument_id}|{as_of_s}|{policy_id}|{kind}"


def as_of_from_iso(ts: str | None) -> str:
    """YYYY-MM-DD desde timestamp ISO; fallback hoy UTC."""
    from datetime import UTC, datetime

    if ts:
        raw = str(ts).strip()
        if len(raw) >= 10 and raw[4] == "-" and raw[7] == "-":
            return raw[:10]
    return datetime.now(tz=UTC).date().isoformat()
