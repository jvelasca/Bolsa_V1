"""PortfolioReconciliation — detect/report integrity paper (ADR-034 OI-6).

Ledger ↔ holdings ↔ PositionState ↔ cash. No auto-heal.
≠ broker ≠ ADR-021 DÍA D ≠ PaperOrder durable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ReconciliationCheckOutcome = Literal["ok", "mismatch", "expected", "unknown"]
ReconciliationCheckId = Literal[
    "cash_ledger",
    "holding_qty_vs_position",
    "open_without_holding",
    "holding_without_open",
    "open_tx_link",
]
PortfolioReconciliationStatus = Literal["clean", "drift"]

PORTFOLIO_RECONCILIATION_KEY = "portfolioReconciliation"

_CASH_EPS = 1e-6
_QTY_EPS = 1e-9


def _non_empty(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    trimmed = value.strip()
    return trimmed or None


@dataclass(frozen=True, slots=True)
class ReconciliationCheck:
    id: ReconciliationCheckId
    outcome: ReconciliationCheckOutcome
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
class PortfolioReconciliation:
    account_id: str
    status: PortfolioReconciliationStatus
    checks: tuple[ReconciliationCheck, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "accountId": self.account_id,
            "status": self.status,
            "checks": [c.to_dict() for c in self.checks],
        }


@dataclass(frozen=True, slots=True)
class HoldingSnap:
    instrument_id: str
    quantity: float


@dataclass(frozen=True, slots=True)
class OpenPositionSnap:
    instrument_id: str
    remaining_quantity: float
    open_transaction_id: str | None
    status: str


def _check(
    check_id: ReconciliationCheckId,
    outcome: ReconciliationCheckOutcome,
    detail: str | None = None,
    instrument_id: str | None = None,
) -> ReconciliationCheck:
    return ReconciliationCheck(
        id=check_id,
        outcome=outcome,
        detail=detail,
        instrument_id=instrument_id,
    )


def build_portfolio_reconciliation(
    *,
    account_id: str,
    portfolio_cash: float,
    ledger_cash_sum: float,
    holdings: list[HoldingSnap] | tuple[HoldingSnap, ...],
    open_positions: list[OpenPositionSnap] | tuple[OpenPositionSnap, ...],
    known_transaction_ids: list[str] | tuple[str, ...] | None = None,
) -> PortfolioReconciliation:
    """Pure detect/report. No mutates."""
    acc = account_id.strip() if isinstance(account_id, str) else ""
    checks: list[ReconciliationCheck] = []

    try:
        cash_delta = abs(float(portfolio_cash) - float(ledger_cash_sum))
    except (TypeError, ValueError):
        cash_delta = float("inf")
    if cash_delta == cash_delta and cash_delta < _CASH_EPS:
        checks.append(_check("cash_ledger", "ok", "portfolioCash == Σ ledger"))
    else:
        checks.append(
            _check(
                "cash_ledger",
                "mismatch",
                f"portfolioCash={portfolio_cash} ledgerSum={ledger_cash_sum}",
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

    open_by: dict[str, OpenPositionSnap] = {}
    for p in open_positions:
        iid = _non_empty(p.instrument_id)
        if not iid:
            continue
        if p.status == "CLOSED":
            continue
        open_by[iid] = p

    known: set[str] | None
    if known_transaction_ids is None:
        known = None
    else:
        known = {x for tid in known_transaction_ids if (x := _non_empty(tid))}

    for iid, pos in open_by.items():
        try:
            remaining = float(pos.remaining_quantity)
        except (TypeError, ValueError):
            continue
        if remaining != remaining or remaining <= _QTY_EPS:
            continue

        holding_qty = holding_by.get(iid, 0.0)
        if holding_qty <= _QTY_EPS:
            checks.append(
                _check(
                    "open_without_holding",
                    "mismatch",
                    f"OPEN remaining={remaining} without holding",
                    iid,
                )
            )
        elif abs(holding_qty - remaining) < _QTY_EPS:
            checks.append(
                _check(
                    "holding_qty_vs_position",
                    "ok",
                    f"qty={holding_qty} remaining={remaining}",
                    iid,
                )
            )
        elif holding_qty > remaining + _QTY_EPS:
            checks.append(
                _check(
                    "holding_qty_vs_position",
                    "expected",
                    f"addon holding={holding_qty} > remaining={remaining}",
                    iid,
                )
            )
        else:
            checks.append(
                _check(
                    "holding_qty_vs_position",
                    "mismatch",
                    f"holding={holding_qty} < remaining={remaining}",
                    iid,
                )
            )

        tx_id = _non_empty(pos.open_transaction_id)
        if known is None:
            checks.append(
                _check(
                    "open_tx_link",
                    "unknown",
                    "knownTransactionIds omitted",
                    iid,
                )
            )
        elif not tx_id:
            checks.append(
                _check(
                    "open_tx_link",
                    "mismatch",
                    "openTransactionId missing",
                    iid,
                )
            )
        elif tx_id in known:
            checks.append(_check("open_tx_link", "ok", f"tx={tx_id}", iid))
        else:
            checks.append(
                _check(
                    "open_tx_link",
                    "mismatch",
                    f"tx={tx_id} not in known transactions",
                    iid,
                )
            )

    for iid, qty in holding_by.items():
        if iid in open_by:
            continue
        checks.append(
            _check(
                "holding_without_open",
                "expected",
                f"holding qty={qty} without OPEN PositionState (legacy/orphan)",
                iid,
            )
        )

    status: PortfolioReconciliationStatus = (
        "drift" if any(c.outcome == "mismatch" for c in checks) else "clean"
    )
    return PortfolioReconciliation(
        account_id=acc,
        status=status,
        checks=tuple(checks),
    )


def reconciliation_status_copy(status: PortfolioReconciliationStatus) -> str:
    if status == "drift":
        return "Deriva paper detectada — no auto-heal"
    return "Capas paper alineadas (o solo expected)"
