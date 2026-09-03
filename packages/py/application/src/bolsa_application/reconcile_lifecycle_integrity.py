"""V1.93 — Reconcile PositionState ↔ Lifecycle Event Store / Outbox (detect/report).

Does NOT mutate. Does NOT unify with cash ledger (OI-6 remains separate).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

LifecycleReconStatus = Literal["clean", "lag", "drift", "blocked"]
LifecycleReconIssueCode = Literal[
    "missing_open_event",
    "missing_close_event",
    "lifecycle_lag",
    "qty_mismatch",
    "dead_head",
]


@dataclass(frozen=True, slots=True)
class LifecycleReconIssue:
    code: LifecycleReconIssueCode
    position_id: str
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "positionId": self.position_id,
            "detail": self.detail,
        }


@dataclass(frozen=True, slots=True)
class LifecycleReconciliation:
    account_id: str
    status: LifecycleReconStatus
    checked: int
    drift_count: int
    lag_count: int
    blocked_count: int
    issues: tuple[LifecycleReconIssue, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "accountId": self.account_id,
            "status": self.status,
            "checked": self.checked,
            "driftCount": self.drift_count,
            "lagCount": self.lag_count,
            "blockedCount": self.blocked_count,
            "issues": [i.to_dict() for i in self.issues],
        }


@dataclass(frozen=True, slots=True)
class PositionStateSnap:
    position_id: str
    status: str
    remaining: float | None
    ledger_position_id: str | None = None


@dataclass(frozen=True, slots=True)
class OutboxSnap:
    position_id: str
    kind: str
    status: str
    created_at: Any = None


class PositionStatesPort(Protocol):
    async def list_for_account(self, account_id: str) -> list[Any]: ...


class LifecycleSnapshotPort(Protocol):
    async def execute(self, position_id: str) -> dict[str, Any]: ...


class OutboxListPort(Protocol):
    async def list_for_account(self, account_id: str) -> list[OutboxSnap]: ...


def _row_to_snap(row: Any) -> PositionStateSnap | None:
    if isinstance(row, PositionStateSnap):
        return row
    if isinstance(row, dict):
        pid = row.get("id") or row.get("position_id") or row.get("positionId")
        status = str(row.get("status") or "")
        rem = row.get("remaining_quantity")
        if rem is None:
            blob = row.get("position_state") or row.get("positionState") or {}
            if isinstance(blob, dict):
                rem = blob.get("remainingQuantity") or blob.get("remaining")
                if not pid:
                    pid = blob.get("positionId")
        ledger = row.get("ledger_position_id") or row.get("ledgerPositionId")
    else:
        pid = getattr(row, "id", None) or getattr(row, "position_id", None)
        status = str(getattr(row, "status", "") or "")
        rem = getattr(row, "remaining_quantity", None)
        blob = getattr(row, "position_state", None)
        if rem is None and isinstance(blob, dict):
            rem = blob.get("remainingQuantity") or blob.get("remaining")
            if not pid:
                pid = blob.get("positionId")
        ledger = getattr(row, "ledger_position_id", None)
    if not isinstance(pid, str) or not pid.strip():
        return None
    remaining: float | None
    try:
        remaining = float(rem) if rem is not None else None
    except (TypeError, ValueError):
        remaining = None
    ledger_s = ledger.strip() if isinstance(ledger, str) and ledger.strip() else None
    return PositionStateSnap(
        position_id=pid.strip(),
        status=status.strip() or "OPEN",
        remaining=remaining,
        ledger_position_id=ledger_s,
    )


def _event_kinds(snap: dict[str, Any]) -> set[str]:
    events = snap.get("events") if isinstance(snap, dict) else None
    if not isinstance(events, list):
        return set()
    kinds: set[str] = set()
    for ev in events:
        if isinstance(ev, dict):
            kind = ev.get("kind")
            if isinstance(kind, str) and kind.strip():
                kinds.add(kind.strip())
    return kinds


def _snapshot_remaining(snap: dict[str, Any]) -> float | None:
    acct = snap.get("accounting") if isinstance(snap, dict) else None
    if not isinstance(acct, dict):
        return None
    rem = acct.get("remaining")
    try:
        return float(rem) if rem is not None else None
    except (TypeError, ValueError):
        return None


def _lifecycle_keys(pos: PositionStateSnap) -> list[str]:
    keys: list[str] = [pos.position_id]
    if pos.ledger_position_id and pos.ledger_position_id not in keys:
        keys.append(pos.ledger_position_id)
    return keys


def build_lifecycle_reconciliation(
    *,
    account_id: str,
    positions: list[PositionStateSnap],
    snapshots_by_position: dict[str, dict[str, Any]],
    outbox: list[OutboxSnap],
) -> LifecycleReconciliation:
    """Pure detect/report. Prefer lag over drift when close is still in flight."""
    issues: list[LifecycleReconIssue] = []
    outbox_by_pos: dict[str, list[OutboxSnap]] = {}
    for row in outbox:
        outbox_by_pos.setdefault(row.position_id, []).append(row)

    for pos in positions:
        keys = _lifecycle_keys(pos)
        kinds: set[str] = set()
        rem_lc: float | None = None
        for key in keys:
            snap = snapshots_by_position.get(key) or {}
            kinds |= _event_kinds(snap)
            if rem_lc is None:
                rem_lc = _snapshot_remaining(snap)

        active_outbox: list[OutboxSnap] = []
        for key in keys:
            active_outbox.extend(outbox_by_pos.get(key, []))

        dead_head = any(o.status == "dead" for o in active_outbox)
        if dead_head:
            issues.append(
                LifecycleReconIssue(
                    code="dead_head",
                    position_id=pos.position_id,
                    detail="outbox dead blocks FIFO head for this position",
                )
            )

        open_statuses = {"OPEN", "PARTIAL", "PROTECTED"}
        if pos.status in open_statuses and "POSITION_OPENED" not in kinds:
            pending_open = any(
                o.kind == "POSITION_OPENED" and o.status in ("pending", "processing")
                for o in active_outbox
            )
            if pending_open:
                issues.append(
                    LifecycleReconIssue(
                        code="lifecycle_lag",
                        position_id=pos.position_id,
                        detail="POSITION_OPENED still pending/processing in outbox",
                    )
                )
            else:
                issues.append(
                    LifecycleReconIssue(
                        code="missing_open_event",
                        position_id=pos.position_id,
                        detail="PositionState open without POSITION_OPENED applied",
                    )
                )

        if pos.status == "CLOSED" and "POSITION_CLOSED" not in kinds:
            pending_close = any(
                o.kind == "POSITION_CLOSED" and o.status in ("pending", "processing")
                for o in active_outbox
            )
            if pending_close:
                issues.append(
                    LifecycleReconIssue(
                        code="lifecycle_lag",
                        position_id=pos.position_id,
                        detail="POSITION_CLOSED still pending/processing in outbox",
                    )
                )
            else:
                issues.append(
                    LifecycleReconIssue(
                        code="missing_close_event",
                        position_id=pos.position_id,
                        detail="PositionState CLOSED without POSITION_CLOSED applied",
                    )
                )

        if (
            pos.status in open_statuses
            and pos.remaining is not None
            and rem_lc is not None
            and abs(pos.remaining - rem_lc) > 1e-6
        ):
            issues.append(
                LifecycleReconIssue(
                    code="qty_mismatch",
                    position_id=pos.position_id,
                    detail=(
                        f"remaining PositionState={pos.remaining} "
                        f"lifecycle={rem_lc}"
                    ),
                )
            )

    drift_codes = {
        "missing_open_event",
        "missing_close_event",
        "qty_mismatch",
    }
    lag_count = sum(1 for i in issues if i.code == "lifecycle_lag")
    blocked_count = sum(1 for i in issues if i.code == "dead_head")
    drift_count = sum(1 for i in issues if i.code in drift_codes)
    if blocked_count:
        status: LifecycleReconStatus = "blocked"
    elif drift_count:
        status = "drift"
    elif lag_count:
        status = "lag"
    else:
        status = "clean"

    return LifecycleReconciliation(
        account_id=account_id,
        status=status,
        checked=len(positions),
        drift_count=drift_count,
        lag_count=lag_count,
        blocked_count=blocked_count,
        issues=tuple(issues),
    )


@dataclass(frozen=True, slots=True)
class ReconcileLifecycleIntegrityInput:
    account_id: str


class ReconcileLifecycleIntegrity:
    """Detect/report PositionState ↔ Lifecycle. No heal."""

    def __init__(
        self,
        *,
        positions: PositionStatesPort,
        snapshots: LifecycleSnapshotPort,
        outbox: OutboxListPort,
    ) -> None:
        self._positions = positions
        self._snapshots = snapshots
        self._outbox = outbox

    async def reconcile(
        self, inp: ReconcileLifecycleIntegrityInput
    ) -> LifecycleReconciliation | None:
        account_id = inp.account_id.strip() if inp.account_id else ""
        if not account_id:
            return None
        rows = await self._positions.list_for_account(account_id)
        snaps: list[PositionStateSnap] = []
        for row in rows:
            snap = _row_to_snap(row)
            if snap is not None:
                snaps.append(snap)
        snapshots_by_position: dict[str, dict[str, Any]] = {}
        for pos in snaps:
            for key in _lifecycle_keys(pos):
                if key not in snapshots_by_position:
                    snapshots_by_position[key] = await self._snapshots.execute(key)
        outbox_rows = await self._outbox.list_for_account(account_id)
        return build_lifecycle_reconciliation(
            account_id=account_id,
            positions=snaps,
            snapshots_by_position=snapshots_by_position,
            outbox=list(outbox_rows),
        )


__all__ = [
    "LifecycleReconIssue",
    "LifecycleReconciliation",
    "OutboxSnap",
    "PositionStateSnap",
    "ReconcileLifecycleIntegrity",
    "ReconcileLifecycleIntegrityInput",
    "build_lifecycle_reconciliation",
]
