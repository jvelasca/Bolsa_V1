"""OI-1 — persistir stop operativo tras Confirm protect (ADR-034).

No muta el ledger. Factory H2 intacta (no empeora stop sin override).
Stop operativo persistido ≠ orden stop de broker.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from bolsa_analytics.cognitive.position_state import (
    apply_position_current_stop,
    position_state_from_dict,
)
from bolsa_application.origin_decision_package import preserve_origin_decision_package
from bolsa_application.persist_position_from_exit import (
    row_position_id,
    row_position_state,
)


class PositionStateProtectStore(Protocol):
    async def get_open_for_instrument(
        self, account_id: str, instrument_id: str
    ) -> Any | None: ...

    async def update_state(
        self,
        *,
        position_id: str,
        status: str,
        position_state: dict[str, Any],
    ) -> Any | None: ...


@dataclass(frozen=True, slots=True)
class PersistPositionFromProtectInput:
    account_id: str
    instrument_id: str
    suggested_stop: float
    override_reason: str | None = None
    applied_at: str | None = None
    # OI-5 / V1.43 — ``protect`` (default) o ``trail`` cuando Confirm firma un TRAIL.
    origin: str = "protect"
    reason: str | None = None


def _resolve_protect_origin(raw: str | None) -> str:
    oid = (raw or "").strip().lower()
    if oid == "trail":
        return "trail"
    return "protect"


class PersistPositionFromProtect:
    """Aplica ``apply_position_current_stop`` a la fila OPEN; idempotente por stop.

    OI-5: origin=protect|trail deja huella en ``revisions``.
    """

    def __init__(self, store: PositionStateProtectStore) -> None:
        self._store = store

    async def get_open(self, account_id: str, instrument_id: str) -> Any | None:
        acc = account_id.strip() if account_id else ""
        inst = instrument_id.strip() if instrument_id else ""
        if not acc or not inst:
            return None
        return await self._store.get_open_for_instrument(acc, inst)

    async def persist(self, inp: PersistPositionFromProtectInput) -> Any | None:
        account_id = inp.account_id.strip() if inp.account_id else ""
        instrument_id = inp.instrument_id.strip() if inp.instrument_id else ""
        if not account_id or not instrument_id:
            return None

        existing = await self._store.get_open_for_instrument(account_id, instrument_id)
        if existing is None:
            return None

        pid = row_position_id(existing)
        blob = row_position_state(existing)
        if pid is None or blob is None:
            return None

        pos = position_state_from_dict(blob)
        override_reason = (inp.override_reason or "").strip()
        override: dict[str, object] | None = (
            {"reason": override_reason} if override_reason else None
        )
        origin = _resolve_protect_origin(inp.origin)
        reason = (inp.reason or "").strip() or override_reason or (
            "trail_confirm" if origin == "trail" else None
        )
        updated = apply_position_current_stop(
            pos,
            float(inp.suggested_stop),
            at=inp.applied_at,
            override=override,
            origin=origin,  # type: ignore[arg-type]
            reason=reason,
        )
        if updated is None:
            return None

        next_blob = preserve_origin_decision_package(blob, dict(updated.to_dict()))
        return await self._store.update_state(
            position_id=pid,
            status=updated.status,
            position_state=next_blob,
        )
