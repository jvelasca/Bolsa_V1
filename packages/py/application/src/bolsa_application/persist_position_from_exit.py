"""P3 — aplicar reduce/cierre a Position persistida tras fill (ADR-033 §4; OI-1 Lab/HTTP/pending).

No muta el ledger. Factory H2 intacta. Protect vía ``PersistPositionFromProtect`` (OI-1).
Bookkeeping ``_lastExitTransactionId`` no es campo F2.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from bolsa_analytics.cognitive.position_state import (
    apply_position_reduce,
    position_state_from_dict,
)

LAST_EXIT_TRANSACTION_KEY = "_lastExitTransactionId"


class PositionStateExitStore(Protocol):
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
class PersistPositionFromExitInput:
    account_id: str
    instrument_id: str
    fill_quantity: float
    fill_price: float
    exit_transaction_id: str
    filled_at: str | None = None


def last_exit_transaction_id(row: Any) -> str | None:
    state = getattr(row, "position_state", None)
    if isinstance(row, dict):
        state = row.get("position_state") or row.get("positionState") or state
    if not isinstance(state, dict):
        return None
    raw = state.get(LAST_EXIT_TRANSACTION_KEY)
    return raw.strip() if isinstance(raw, str) and raw.strip() else None


def row_position_id(row: Any) -> str | None:
    if isinstance(row, dict):
        pid = row.get("position_id") or row.get("id") or row.get("positionId")
    else:
        pid = getattr(row, "id", None) or getattr(row, "position_id", None)
    return pid.strip() if isinstance(pid, str) and pid.strip() else None


def row_position_state(row: Any) -> dict[str, Any] | None:
    if isinstance(row, dict):
        state = row.get("position_state") or row.get("positionState")
    else:
        state = getattr(row, "position_state", None)
    return dict(state) if isinstance(state, dict) else None


class PersistPositionFromExit:
    """Reduce/cierra PositionState si hay fila abierta; idempotente por tx de salida."""

    def __init__(self, store: PositionStateExitStore) -> None:
        self._store = store

    async def get_open(self, account_id: str, instrument_id: str) -> Any | None:
        acc = account_id.strip() if account_id else ""
        inst = instrument_id.strip() if instrument_id else ""
        if not acc or not inst:
            return None
        return await self._store.get_open_for_instrument(acc, inst)

    async def persist(self, inp: PersistPositionFromExitInput) -> Any | None:
        tx_id = inp.exit_transaction_id.strip() if inp.exit_transaction_id else ""
        account_id = inp.account_id.strip() if inp.account_id else ""
        instrument_id = inp.instrument_id.strip() if inp.instrument_id else ""
        if not tx_id or not account_id or not instrument_id:
            return None

        existing = await self._store.get_open_for_instrument(account_id, instrument_id)
        if existing is None:
            return None
        if last_exit_transaction_id(existing) == tx_id:
            return existing

        pid = row_position_id(existing)
        blob = row_position_state(existing)
        if pid is None or blob is None:
            return None
        pos = position_state_from_dict(blob)
        updated = apply_position_reduce(
            pos,
            inp.fill_quantity,
            exit_price=inp.fill_price,
            at=inp.filled_at,
            origin="reduce",
        )
        if updated is None:
            return None
        next_blob = dict(updated.to_dict())
        next_blob[LAST_EXIT_TRANSACTION_KEY] = tx_id
        return await self._store.update_state(
            position_id=pid,
            status=updated.status,
            position_state=next_blob,
        )
