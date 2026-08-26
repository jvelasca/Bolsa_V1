"""LR-1 — ReconcileLiveLedger (detect/report live↔ledger, ADR-034).

Carga cash+holdings del ledger y compara con venue live. No muta.
Nunca execute_trade / submit_order.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from bolsa_analytics.cognitive.live_ledger_reconciliation import (
    LiveHoldingSnap,
    LiveLedgerReconciliation,
    LivePositionSnap,
    build_live_ledger_reconciliation,
)


class PortfolioCashPort(Protocol):
    async def get_cash(self, account_id: str) -> float: ...


class HoldingsPort(Protocol):
    async def list_holdings(self, account_id: str) -> list[dict[str, Any]]: ...


class LiveVenuePort(Protocol):
    async def fetch_cash(self) -> float: ...

    async def fetch_positions(self) -> list[dict[str, Any]]: ...


@dataclass(frozen=True, slots=True)
class ReconcileLiveLedgerInput:
    account_id: str


def _row_instrument_id(row: Any) -> str | None:
    if isinstance(row, dict):
        raw = row.get("instrument_id") or row.get("instrumentId")
    else:
        raw = getattr(row, "instrument_id", None)
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return None


def _row_quantity(row: Any) -> float:
    if isinstance(row, dict):
        raw = row.get("quantity")
    else:
        raw = getattr(row, "quantity", 0)
    if raw is None:
        return 0.0
    try:
        return float(raw)
    except (TypeError, ValueError):
        return 0.0


class ReconcileLiveLedger:
    """Detect/report live↔ledger. No heal. No trade."""

    def __init__(
        self,
        *,
        cash: PortfolioCashPort,
        holdings: HoldingsPort,
        live: LiveVenuePort | None = None,
    ) -> None:
        self._cash = cash
        self._holdings = holdings
        self._live = live

    async def reconcile(
        self, inp: ReconcileLiveLedgerInput
    ) -> LiveLedgerReconciliation | None:
        account_id = inp.account_id.strip() if inp.account_id else ""
        if not account_id:
            return None

        ledger_cash = float(await self._cash.get_cash(account_id))
        holding_rows = await self._holdings.list_holdings(account_id)
        holdings = [
            LiveHoldingSnap(iid, _row_quantity(row))
            for row in holding_rows
            if (iid := _row_instrument_id(row))
        ]

        if self._live is None:
            return build_live_ledger_reconciliation(
                account_id=account_id,
                ledger_cash=ledger_cash,
                live_cash=0.0,
                holdings=holdings,
                live_positions=[],
                unavailable=True,
            )

        try:
            live_cash = float(await self._live.fetch_cash())
            live_rows = await self._live.fetch_positions()
        except Exception:
            return build_live_ledger_reconciliation(
                account_id=account_id,
                ledger_cash=ledger_cash,
                live_cash=0.0,
                holdings=holdings,
                live_positions=[],
                unavailable=True,
            )

        live_positions = [
            LivePositionSnap(iid, _row_quantity(row))
            for row in live_rows
            if (iid := _row_instrument_id(row))
        ]

        return build_live_ledger_reconciliation(
            account_id=account_id,
            ledger_cash=ledger_cash,
            live_cash=live_cash,
            holdings=holdings,
            live_positions=live_positions,
            unavailable=False,
        )
