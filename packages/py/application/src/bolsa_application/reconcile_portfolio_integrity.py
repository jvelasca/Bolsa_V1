"""OI-6 — ReconcilePortfolioIntegrity (detect/report, ADR-034).

Carga snapshot paper y construye PortfolioReconciliation. No muta.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from bolsa_analytics.cognitive.portfolio_reconciliation import (
    HoldingSnap,
    OpenPositionSnap,
    PortfolioReconciliation,
    build_portfolio_reconciliation,
)
from bolsa_analytics.cognitive.position_state import position_state_from_dict


class PortfolioCashPort(Protocol):
    async def get_cash(self, account_id: str) -> float: ...


class LedgerCashPort(Protocol):
    async def sum_cash_amounts(self, account_id: str) -> float: ...


class HoldingsPort(Protocol):
    async def list_holdings(self, account_id: str) -> list[dict[str, Any]]: ...


class OpenPositionsPort(Protocol):
    async def list_open(self, account_id: str) -> list[Any]: ...


class TransactionIdsPort(Protocol):
    async def list_transaction_ids(self, account_id: str) -> list[str]: ...


@dataclass(frozen=True, slots=True)
class ReconcilePortfolioIntegrityInput:
    account_id: str
    include_tx_links: bool = True


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


def _row_position_blob(row: Any) -> dict[str, Any] | None:
    if isinstance(row, dict):
        blob = row.get("position_state") or row.get("positionState")
    else:
        blob = getattr(row, "position_state", None)
    return blob if isinstance(blob, dict) else None


def _row_open_tx(row: Any, blob: dict[str, Any] | None) -> str | None:
    if isinstance(row, dict):
        raw = row.get("open_transaction_id") or row.get("openTransactionId")
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
    else:
        raw = getattr(row, "open_transaction_id", None)
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
    if blob:
        raw2 = blob.get("openTransactionId") or blob.get("open_transaction_id")
        if isinstance(raw2, str) and raw2.strip():
            return raw2.strip()
    return None


def _row_status(row: Any, blob: dict[str, Any] | None, pos_status: str) -> str:
    if pos_status:
        return pos_status
    if isinstance(row, dict):
        raw = row.get("status")
    else:
        raw = getattr(row, "status", None)
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    if blob and isinstance(blob.get("status"), str):
        return str(blob["status"])
    return "OPEN"


class ReconcilePortfolioIntegrity:
    """Detect/report. No heal."""

    def __init__(
        self,
        *,
        cash: PortfolioCashPort,
        ledger: LedgerCashPort,
        holdings: HoldingsPort,
        open_positions: OpenPositionsPort,
        transactions: TransactionIdsPort | None = None,
    ) -> None:
        self._cash = cash
        self._ledger = ledger
        self._holdings = holdings
        self._open_positions = open_positions
        self._transactions = transactions

    async def reconcile(
        self, inp: ReconcilePortfolioIntegrityInput
    ) -> PortfolioReconciliation | None:
        account_id = inp.account_id.strip() if inp.account_id else ""
        if not account_id:
            return None

        portfolio_cash = float(await self._cash.get_cash(account_id))
        ledger_sum = float(await self._ledger.sum_cash_amounts(account_id))
        holding_rows = await self._holdings.list_holdings(account_id)
        open_rows = await self._open_positions.list_open(account_id)

        holdings = [
            HoldingSnap(iid, _row_quantity(row))
            for row in holding_rows
            if (iid := _row_instrument_id(row))
        ]

        opens: list[OpenPositionSnap] = []
        for row in open_rows:
            iid = _row_instrument_id(row)
            if not iid:
                continue
            blob = _row_position_blob(row)
            pos = position_state_from_dict(blob) if blob else None
            remaining = (
                float(pos.remaining_quantity)
                if pos is not None
                else _row_quantity(row)
            )
            status = _row_status(row, blob, pos.status if pos else "")
            opens.append(
                OpenPositionSnap(
                    instrument_id=iid,
                    remaining_quantity=remaining,
                    open_transaction_id=_row_open_tx(row, blob),
                    status=status,
                )
            )

        known: list[str] | None = None
        if inp.include_tx_links and self._transactions is not None:
            known = list(await self._transactions.list_transaction_ids(account_id))

        return build_portfolio_reconciliation(
            account_id=account_id,
            portfolio_cash=portfolio_cash,
            ledger_cash_sum=ledger_sum,
            holdings=holdings,
            open_positions=opens,
            known_transaction_ids=known,
        )
