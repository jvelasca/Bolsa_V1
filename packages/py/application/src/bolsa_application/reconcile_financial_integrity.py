"""V1.94 — Financial Integrity: compose OI-6 + lifecycle recon + fill links.

Detect/report only. Does NOT mutate. Does NOT unify cash ledger with lifecycle
accounting. Fill PAPER identity = transactions.id (= lifecycle fill_id =
ledger reference_id = PositionState.open_transaction_id for opens).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from bolsa_application.reconcile_lifecycle_integrity import (
    LifecycleReconciliation,
    PositionStateSnap,
    ReconcileLifecycleIntegrity,
    ReconcileLifecycleIntegrityInput,
)

FinancialIntegrityStatus = Literal["clean", "lag", "drift", "blocked"]
OperationalState = Literal["OK", "DEGRADED", "BLOCKED"]
FillLinkIssueCode = Literal["open_tx_mismatch", "missing_fill_in_ledger"]


@dataclass(frozen=True, slots=True)
class FillLinkIssue:
    code: FillLinkIssueCode
    position_id: str
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "positionId": self.position_id,
            "detail": self.detail,
        }


@dataclass(frozen=True, slots=True)
class FinancialIntegrityReport:
    account_id: str
    status: FinancialIntegrityStatus
    operational_state: OperationalState
    portfolio_status: str | None
    lifecycle: LifecycleReconciliation
    fill_link_issues: tuple[FillLinkIssue, ...] = field(default_factory=tuple)
    outbox_dead: int = 0
    sla_breached: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "accountId": self.account_id,
            "status": self.status,
            "operationalState": self.operational_state,
            "portfolioStatus": self.portfolio_status,
            "lifecycle": self.lifecycle.to_dict(),
            "fillLinkIssues": [i.to_dict() for i in self.fill_link_issues],
            "outboxDead": self.outbox_dead,
            "slaBreached": self.sla_breached,
        }


def compute_operational_state(
    *,
    integrity_status: FinancialIntegrityStatus,
    outbox_dead: int = 0,
    sla_breached: bool = False,
) -> OperationalState:
    """SLA ok + dead=1 is DEGRADED, not OK. Drift/blocked → BLOCKED."""
    if integrity_status in ("drift", "blocked"):
        return "BLOCKED"
    if outbox_dead > 0 or sla_breached or integrity_status == "lag":
        return "DEGRADED"
    return "OK"


def build_fill_link_issues(
    *,
    positions: list[PositionStateSnap],
    snapshots_by_position: dict[str, dict[str, Any]],
    ledger_reference_ids: set[str] | frozenset[str],
) -> tuple[FillLinkIssue, ...]:
    """open_transaction_id ↔ POSITION_OPENED.fill_id ↔ ledger.reference_id."""
    issues: list[FillLinkIssue] = []
    for pos in positions:
        keys = [pos.position_id]
        if pos.ledger_position_id and pos.ledger_position_id not in keys:
            keys.append(pos.ledger_position_id)
        open_fill: str | None = None
        for key in keys:
            snap = snapshots_by_position.get(key) or {}
            events = snap.get("events") if isinstance(snap, dict) else None
            if not isinstance(events, list):
                continue
            for ev in events:
                if not isinstance(ev, dict):
                    continue
                if ev.get("kind") != "POSITION_OPENED":
                    continue
                raw = ev.get("fillId") or ev.get("fill_id")
                if isinstance(raw, str) and raw.strip():
                    open_fill = raw.strip()
                    break
            if open_fill:
                break

        if (
            pos.open_transaction_id
            and open_fill
            and pos.open_transaction_id != open_fill
        ):
            issues.append(
                FillLinkIssue(
                    code="open_tx_mismatch",
                    position_id=pos.position_id,
                    detail=(
                        f"open_transaction_id={pos.open_transaction_id} "
                        f"≠ POSITION_OPENED.fill_id={open_fill}"
                    ),
                )
            )

        # Applied open fill should appear in ledger references.
        check_id = open_fill or pos.open_transaction_id
        if check_id and check_id not in ledger_reference_ids:
            issues.append(
                FillLinkIssue(
                    code="missing_fill_in_ledger",
                    position_id=pos.position_id,
                    detail=f"fill/tx {check_id} missing from ledger references",
                )
            )
    return tuple(issues)


def compose_financial_integrity(
    *,
    account_id: str,
    lifecycle: LifecycleReconciliation,
    fill_link_issues: tuple[FillLinkIssue, ...] = (),
    portfolio_status: str | None = None,
    outbox_dead: int = 0,
    sla_breached: bool = False,
) -> FinancialIntegrityReport:
    fill_drift = len(fill_link_issues) > 0
    portfolio_drift = portfolio_status == "drift"

    if lifecycle.status == "blocked":
        status: FinancialIntegrityStatus = "blocked"
    elif lifecycle.status == "drift" or fill_drift or portfolio_drift:
        status = "drift"
    elif lifecycle.status == "lag":
        status = "lag"
    else:
        status = "clean"

    return FinancialIntegrityReport(
        account_id=account_id,
        status=status,
        operational_state=compute_operational_state(
            integrity_status=status,
            outbox_dead=outbox_dead,
            sla_breached=sla_breached,
        ),
        portfolio_status=portfolio_status,
        lifecycle=lifecycle,
        fill_link_issues=fill_link_issues,
        outbox_dead=outbox_dead,
        sla_breached=sla_breached,
    )


class LedgerReferencePort(Protocol):
    async def list_reference_ids(self, account_id: str) -> list[str]: ...


class PortfolioStatusPort(Protocol):
    async def portfolio_recon_status(self, account_id: str) -> str: ...


@dataclass(frozen=True, slots=True)
class ReconcileFinancialIntegrityInput:
    account_id: str
    outbox_dead: int = 0
    sla_breached: bool = False


class ReconcileFinancialIntegrity:
    """Compose OI-6 status + lifecycle recon + fill links. No heal."""

    def __init__(
        self,
        *,
        lifecycle: ReconcileLifecycleIntegrity,
        positions: Any,
        snapshots_by_account: Any,
        ledger_refs: LedgerReferencePort | None = None,
        portfolio: PortfolioStatusPort | None = None,
    ) -> None:
        self._lifecycle = lifecycle
        self._positions = positions
        self._snapshots = snapshots_by_account
        self._ledger_refs = ledger_refs
        self._portfolio = portfolio

    async def reconcile(
        self, inp: ReconcileFinancialIntegrityInput
    ) -> FinancialIntegrityReport | None:
        account_id = inp.account_id.strip() if inp.account_id else ""
        if not account_id:
            return None
        lc = await self._lifecycle.reconcile(
            ReconcileLifecycleIntegrityInput(account_id=account_id)
        )
        if lc is None:
            return None

        rows = await self._positions.list_for_account(account_id)
        pos_snaps: list[PositionStateSnap] = []
        from bolsa_application.reconcile_lifecycle_integrity import _row_to_snap

        for row in rows:
            snap = _row_to_snap(row)
            if snap is not None:
                pos_snaps.append(snap)

        batch = getattr(self._snapshots, "execute_for_account", None)
        if callable(batch):
            snapshots = dict(await batch(account_id))
        else:
            snapshots = {}
            execute = getattr(self._snapshots, "execute", None)
            if callable(execute):
                for pos in pos_snaps:
                    snapshots[pos.position_id] = await execute(pos.position_id)

        ref_ids: set[str] = set()
        if self._ledger_refs is not None:
            ref_ids = set(await self._ledger_refs.list_reference_ids(account_id))

        fill_issues = build_fill_link_issues(
            positions=pos_snaps,
            snapshots_by_position=snapshots,
            ledger_reference_ids=ref_ids,
        )

        portfolio_status: str | None = None
        if self._portfolio is not None:
            portfolio_status = await self._portfolio.portfolio_recon_status(account_id)

        return compose_financial_integrity(
            account_id=account_id,
            lifecycle=lc,
            fill_link_issues=fill_issues,
            portfolio_status=portfolio_status,
            outbox_dead=inp.outbox_dead,
            sla_breached=inp.sla_breached,
        )


__all__ = [
    "FillLinkIssue",
    "FinancialIntegrityReport",
    "OperationalState",
    "ReconcileFinancialIntegrity",
    "ReconcileFinancialIntegrityInput",
    "build_fill_link_issues",
    "compose_financial_integrity",
    "compute_operational_state",
]
