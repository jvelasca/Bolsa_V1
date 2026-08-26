"""LiveLedgerReconciliation — detect/report live venue ↔ ledger (ADR-034 LR-1).

Live cash/positions vs portfolio cash/holdings. No auto-heal.
≠ execute_trade ≠ submit_order ≠ PAPER_D_EXECUTE.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

LiveReconciliationCheckOutcome = Literal["ok", "mismatch", "expected", "unknown"]
LiveReconciliationCheckId = Literal[
    "live_cash_vs_ledger",
    "live_qty_vs_holding",
    "live_without_holding",
    "holding_without_live",
]
LiveLedgerReconciliationStatus = Literal["clean", "drift", "unavailable"]

LIVE_LEDGER_RECONCILIATION_KEY = "liveLedgerReconciliation"

_CASH_EPS = 1e-6
_QTY_EPS = 1e-9


def _non_empty(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    trimmed = value.strip()
    return trimmed or None


@dataclass(frozen=True, slots=True)
class LiveReconciliationCheck:
    id: LiveReconciliationCheckId
    outcome: LiveReconciliationCheckOutcome
    detail: str | None
    instrument_id: str | None

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "outcome": self.outcome,
            "detail": self.detail,
            "instrumentId": self.instrument_id,
        }


@dataclass(frozen=True, slots=True)
class LiveLedgerReconciliation:
    account_id: str
    status: LiveLedgerReconciliationStatus
    checks: tuple[LiveReconciliationCheck, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "accountId": self.account_id,
            "status": self.status,
            "checks": [c.to_dict() for c in self.checks],
        }


@dataclass(frozen=True, slots=True)
class LiveHoldingSnap:
    instrument_id: str
    quantity: float


@dataclass(frozen=True, slots=True)
class LivePositionSnap:
    instrument_id: str
    quantity: float


def _check(
    check_id: LiveReconciliationCheckId,
    outcome: LiveReconciliationCheckOutcome,
    detail: str | None = None,
    instrument_id: str | None = None,
) -> LiveReconciliationCheck:
    return LiveReconciliationCheck(
        id=check_id,
        outcome=outcome,
        detail=detail,
        instrument_id=instrument_id,
    )


def build_live_ledger_reconciliation(
    *,
    account_id: str,
    ledger_cash: float,
    live_cash: float,
    holdings: list[LiveHoldingSnap] | tuple[LiveHoldingSnap, ...],
    live_positions: list[LivePositionSnap] | tuple[LivePositionSnap, ...],
    unavailable: bool = False,
) -> LiveLedgerReconciliation:
    """Pure detect/report. No mutates."""
    acc = account_id.strip() if isinstance(account_id, str) else ""

    if unavailable:
        return LiveLedgerReconciliation(
            account_id=acc,
            status="unavailable",
            checks=(
                _check(
                    "live_cash_vs_ledger",
                    "unknown",
                    "live venue unavailable",
                ),
            ),
        )

    checks: list[LiveReconciliationCheck] = []

    try:
        cash_delta = abs(float(live_cash) - float(ledger_cash))
    except (TypeError, ValueError):
        cash_delta = float("inf")
    if cash_delta == cash_delta and cash_delta < _CASH_EPS:
        checks.append(
            _check("live_cash_vs_ledger", "ok", "liveCash == ledgerCash")
        )
    else:
        checks.append(
            _check(
                "live_cash_vs_ledger",
                "mismatch",
                f"liveCash={live_cash} ledgerCash={ledger_cash}",
            )
        )

    holding_by: dict[str, float] = {}
    for h in holdings:
        iid = _non_empty(h.instrument_id)
        if not iid:
            continue
        try:
            qty = float(h.quantity)
        except (TypeError, ValueError):
            continue
        if qty != qty or qty <= _QTY_EPS:
            continue
        holding_by[iid] = holding_by.get(iid, 0.0) + qty

    live_by: dict[str, float] = {}
    for p in live_positions:
        iid = _non_empty(p.instrument_id)
        if not iid:
            continue
        try:
            qty = float(p.quantity)
        except (TypeError, ValueError):
            continue
        if qty != qty or qty <= _QTY_EPS:
            continue
        live_by[iid] = live_by.get(iid, 0.0) + qty

    for iid, live_qty in live_by.items():
        holding_qty = holding_by.get(iid, 0.0)
        if holding_qty <= _QTY_EPS:
            checks.append(
                _check(
                    "live_without_holding",
                    "mismatch",
                    f"live qty={live_qty} without holding",
                    iid,
                )
            )
        elif abs(holding_qty - live_qty) < _QTY_EPS:
            checks.append(
                _check(
                    "live_qty_vs_holding",
                    "ok",
                    f"qty={live_qty} holding={holding_qty}",
                    iid,
                )
            )
        else:
            checks.append(
                _check(
                    "live_qty_vs_holding",
                    "mismatch",
                    f"live={live_qty} holding={holding_qty}",
                    iid,
                )
            )

    for iid, qty in holding_by.items():
        if iid in live_by:
            continue
        checks.append(
            _check(
                "holding_without_live",
                "expected",
                f"holding qty={qty} without live position",
                iid,
            )
        )

    status: LiveLedgerReconciliationStatus = (
        "drift" if any(c.outcome == "mismatch" for c in checks) else "clean"
    )
    return LiveLedgerReconciliation(
        account_id=acc,
        status=status,
        checks=tuple(checks),
    )


def live_ledger_reconciliation_status_copy(
    status: LiveLedgerReconciliationStatus,
) -> str:
    if status == "unavailable":
        return "Venue live no disponible — sin reconcile"
    if status == "drift":
        return "Deriva live↔ledger detectada — no auto-heal"
    return "Live y ledger alineados (o solo expected)"
