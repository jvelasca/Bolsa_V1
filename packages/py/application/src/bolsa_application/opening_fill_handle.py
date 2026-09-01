"""V1.52 — handle durable de fill de apertura sin Position (GP-CRASH-01).

No es ExecutionIntent. El ledger ya tiene el fill; esto solo rehidrata
TradePlan para el mismo ``PersistPositionFromFill``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from bolsa_application.journal_writer import append_journal_event
from bolsa_application.persist_position_from_fill import (
    PersistPositionFromFill,
    PersistPositionFromFillInput,
)

OPENING_FILL_HANDLE_EVENT = "opening_fill_handle"


@dataclass(frozen=True, slots=True)
class OpeningFillHandle:
    account_id: str
    open_transaction_id: str
    instrument_id: str
    fill_price: float
    fill_quantity: float
    trade_plan: dict[str, Any]
    filled_at: str | None = None
    ledger_position_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "accountId": self.account_id,
            "openTransactionId": self.open_transaction_id,
            "instrumentId": self.instrument_id,
            "fillPrice": self.fill_price,
            "fillQuantity": self.fill_quantity,
            "tradePlan": dict(self.trade_plan),
            "filledAt": self.filled_at,
            "ledgerPositionId": self.ledger_position_id,
        }


def opening_fill_handle_from_payload(raw: object) -> OpeningFillHandle | None:
    if not isinstance(raw, dict):
        return None
    account_id = raw.get("accountId") or raw.get("account_id")
    tx = raw.get("openTransactionId") or raw.get("open_transaction_id")
    instrument_id = raw.get("instrumentId") or raw.get("instrument_id")
    plan = raw.get("tradePlan") or raw.get("trade_plan")
    if not isinstance(account_id, str) or not account_id.strip():
        return None
    if not isinstance(tx, str) or not tx.strip():
        return None
    if not isinstance(instrument_id, str) or not instrument_id.strip():
        return None
    if not isinstance(plan, dict):
        return None
    price_raw = raw.get("fillPrice")
    if price_raw is None:
        price_raw = raw.get("fill_price")
    qty_raw = raw.get("fillQuantity")
    if qty_raw is None:
        qty_raw = raw.get("fill_quantity")
    if not isinstance(price_raw, (int, float)) or isinstance(price_raw, bool):
        return None
    if not isinstance(qty_raw, (int, float)) or isinstance(qty_raw, bool):
        return None
    try:
        price = float(price_raw)
        qty = float(qty_raw)
    except (TypeError, ValueError):
        return None
    if price != price or qty != qty or price <= 0 or qty <= 0:
        return None
    filled = raw.get("filledAt") or raw.get("filled_at")
    ledger_pid = raw.get("ledgerPositionId") or raw.get("ledger_position_id")
    return OpeningFillHandle(
        account_id=account_id.strip(),
        open_transaction_id=tx.strip(),
        instrument_id=instrument_id.strip(),
        fill_price=price,
        fill_quantity=qty,
        trade_plan=dict(plan),
        filled_at=filled.strip() if isinstance(filled, str) and filled.strip() else None,
        ledger_position_id=(
            ledger_pid.strip()
            if isinstance(ledger_pid, str) and ledger_pid.strip()
            else None
        ),
    )


class OpeningFillHandleStore(Protocol):
    async def record(self, handle: OpeningFillHandle) -> None: ...

    async def list_for_account(self, account_id: str) -> list[OpeningFillHandle]: ...


class MemoryOpeningFillHandleStore:
    """Tests / in-process. Durable en prod = journal."""

    def __init__(self) -> None:
        self._by_tx: dict[str, OpeningFillHandle] = {}

    async def record(self, handle: OpeningFillHandle) -> None:
        self._by_tx[handle.open_transaction_id] = handle

    async def list_for_account(self, account_id: str) -> list[OpeningFillHandle]:
        acc = account_id.strip()
        return [h for h in self._by_tx.values() if h.account_id == acc]


class JournalOpeningFillHandleStore:
    """Persiste el handle en Decision Journal (sin Alembic)."""

    def __init__(self, writer: Any, reader: Any | None = None) -> None:
        self._writer = writer
        self._reader = reader

    async def record(self, handle: OpeningFillHandle) -> None:
        plan_id = handle.trade_plan.get("decisionId") or handle.trade_plan.get("decision_id")
        decision_id = (
            plan_id.strip()
            if isinstance(plan_id, str) and plan_id.strip()
            else handle.open_transaction_id
        )
        await append_journal_event(
            self._writer,
            event_type=OPENING_FILL_HANDLE_EVENT,
            decision_id=decision_id,
            account_id=handle.account_id,
            instrument_id=handle.instrument_id,
            payload=handle.to_dict(),
        )

    async def list_for_account(self, account_id: str) -> list[OpeningFillHandle]:
        if self._reader is None:
            return []
        try:
            entries, _total = await self._reader.list_entries(
                account_id=account_id,
                event_type=OPENING_FILL_HANDLE_EVENT,
                limit=200,
                offset=0,
            )
        except Exception:  # noqa: BLE001 — fail-closed: no inventar Position
            return []
        out: list[OpeningFillHandle] = []
        seen: set[str] = set()
        for entry in entries:
            payload = getattr(entry, "payload", None)
            handle = opening_fill_handle_from_payload(payload)
            if handle is None or handle.open_transaction_id in seen:
                continue
            seen.add(handle.open_transaction_id)
            out.append(handle)
        return out


class RecoverOrphanOpeningFills:
    """Reconstruye Position desde fill huérfano. Mismo factory V1.51."""

    def __init__(
        self,
        *,
        handles: OpeningFillHandleStore,
        persist: PersistPositionFromFill,
    ) -> None:
        self._handles = handles
        self._persist = persist

    async def recover(self, account_id: str) -> int:
        acc = account_id.strip() if account_id else ""
        if not acc:
            return 0
        recovered = 0
        for handle in await self._handles.list_for_account(acc):
            if not handle.trade_plan:
                continue
            try:
                row = await self._persist.persist(
                    PersistPositionFromFillInput(
                        account_id=handle.account_id,
                        trade_plan=handle.trade_plan,
                        fill_price=handle.fill_price,
                        fill_quantity=handle.fill_quantity,
                        filled_at=handle.filled_at,
                        open_transaction_id=handle.open_transaction_id,
                        ledger_position_id=handle.ledger_position_id,
                    )
                )
            except Exception:  # noqa: BLE001 — fill permanece; no fingir Position
                continue
            if row is not None:
                recovered += 1
        return recovered
