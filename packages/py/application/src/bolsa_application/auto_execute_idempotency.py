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


def make_position_event_idempotency_key(
    *,
    position_id: str,
    event_type: str,
    event_as_of: date | str,
    action: str,
    sequence: int = 1,
) -> str:
    """Legacy day-composite key (tests / diagnóstico).

    V1.48: el sell PAPER usa ``eventId`` persistido, no esta clave.
    ``sequence`` default 1 es un landmine si se usara para TRAIL — no usarla
    como autoridad de AUTO.
    """
    as_of_s = (
        event_as_of.isoformat()
        if isinstance(event_as_of, date)
        else as_of_from_iso(str(event_as_of) if event_as_of else None)
    )
    pos = (position_id or "").strip() or "pos"
    ev = (event_type or "").strip() or "UNKNOWN"
    act = (action or "").strip() or "exit"
    seq = max(int(sequence), 1)
    return f"{pos}|{ev}|{as_of_s}|{seq}|{act}"


def as_of_from_iso(ts: str | None) -> str:
    """YYYY-MM-DD desde timestamp ISO; fallback hoy UTC."""
    from datetime import UTC, datetime

    if ts:
        raw = str(ts).strip()
        if len(raw) >= 10 and raw[4] == "-" and raw[7] == "-":
            return raw[:10]
    return datetime.now(tz=UTC).date().isoformat()
