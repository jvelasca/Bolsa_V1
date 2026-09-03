"""V1.93/V1.94 — Reconcile PositionState ↔ Lifecycle Event Store / Outbox.

V1.94: bidirectional (orphan lifecycle), FIFO dead_head vs dead_non_head,
batch snapshots via list_events_for_account. Detect/report only. No heal.
Does NOT unify with cash ledger (OI-6 remains separate).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal, Protocol

LifecycleReconStatus = Literal["clean", "lag", "drift", "blocked"]
LifecycleReconIssueCode = Literal[
    "missing_open_event",
    "missing_close_event",
    "lifecycle_lag",
    "qty_mismatch",
    "dead_head",
    "dead_non_head",
    "orphan_lifecycle",
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
    open_transaction_id: str | None = None


@dataclass(frozen=True, slots=True)
class OutboxSnap:
    position_id: str
    kind: str
    status: str
    created_at: Any = None
    id: str | None = None


class PositionStatesPort(Protocol):
    async def list_for_account(self, account_id: str) -> list[Any]: ...


class LifecycleSnapshotPort(Protocol):
    async def execute(self, position_id: str) -> dict[str, Any]: ...


class LifecycleBatchSnapshotPort(Protocol):
    async def execute_for_account(
        self, account_id: str
    ) -> dict[str, dict[str, Any]]: ...


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
        open_tx = row.get("open_transaction_id") or row.get("openTransactionId")
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
        open_tx = getattr(row, "open_transaction_id", None)
    if not isinstance(pid, str) or not pid.strip():
        return None
    remaining: float | None
    try:
        remaining = float(rem) if rem is not None else None
    except (TypeError, ValueError):
        remaining = None
    ledger_s = ledger.strip() if isinstance(ledger, str) and ledger.strip() else None
    open_tx_s = (
        open_tx.strip() if isinstance(open_tx, str) and open_tx.strip() else None
    )
    return PositionStateSnap(
        position_id=pid.strip(),
        status=status.strip() or "OPEN",
        remaining=remaining,
        ledger_position_id=ledger_s,
        open_transaction_id=open_tx_s,
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


def _outbox_sort_key(row: OutboxSnap) -> tuple[Any, str]:
    created = row.created_at
    if created is None:
        created = datetime.min
    rid = row.id or ""
    return (created, rid)


def fifo_outbox_head(rows: list[OutboxSnap]) -> OutboxSnap | None:
    """Same head rule as claim_batch: earliest active among pending|processing|dead."""
    active = [r for r in rows if r.status in ("pending", "processing", "dead")]
    if not active:
        return None
    return sorted(active, key=_outbox_sort_key)[0]


def _collect_outbox(
    outbox_by_pos: dict[str, list[OutboxSnap]], keys: list[str]
) -> list[OutboxSnap]:
    active: list[OutboxSnap] = []
    for key in keys:
        active.extend(outbox_by_pos.get(key, []))
    return active


def _append_dead_issues(
    issues: list[LifecycleReconIssue],
    *,
    position_id: str,
    active_outbox: list[OutboxSnap],
) -> None:
    head = fifo_outbox_head(active_outbox)
    if head is not None and head.status == "dead":
        issues.append(
            LifecycleReconIssue(
                code="dead_head",
                position_id=position_id,
                detail="outbox dead blocks FIFO head for this position",
            )
        )
        return
    non_head_dead = any(o.status == "dead" for o in active_outbox)
    if non_head_dead:
        issues.append(
            LifecycleReconIssue(
                code="dead_non_head",
                position_id=position_id,
                detail="outbox has dead row that is not the FIFO head",
            )
        )


def build_lifecycle_reconciliation(
    *,
    account_id: str,
    positions: list[PositionStateSnap],
    snapshots_by_position: dict[str, dict[str, Any]],
    outbox: list[OutboxSnap],
    opening_fill_position_ids: set[str] | frozenset[str] | None = None,
) -> LifecycleReconciliation:
    """Pure detect/report. Prefer lag over drift when close/open is still in flight."""
    issues: list[LifecycleReconIssue] = []
    outbox_by_pos: dict[str, list[OutboxSnap]] = {}
    for row in outbox:
        outbox_by_pos.setdefault(row.position_id, []).append(row)

    handles = opening_fill_position_ids or frozenset()
    pos_ids: set[str] = set()
    for pos in positions:
        for key in _lifecycle_keys(pos):
            pos_ids.add(key)

    for pos in positions:
        keys = _lifecycle_keys(pos)
        kinds: set[str] = set()
        rem_lc: float | None = None
        for key in keys:
            snap = snapshots_by_position.get(key) or {}
            kinds |= _event_kinds(snap)
            if rem_lc is None:
                rem_lc = _snapshot_remaining(snap)

        active_outbox = _collect_outbox(outbox_by_pos, keys)
        _append_dead_issues(
            issues, position_id=pos.position_id, active_outbox=active_outbox
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

    # V1.94 — Lifecycle → PositionState (orphans).
    lifecycle_ids = set(snapshots_by_position.keys()) | set(outbox_by_pos.keys())
    for pid in sorted(lifecycle_ids - pos_ids):
        snap = snapshots_by_position.get(pid) or {}
        kinds = _event_kinds(snap)
        active_outbox = list(outbox_by_pos.get(pid, []))
        _append_dead_issues(issues, position_id=pid, active_outbox=active_outbox)
        if not kinds and not active_outbox:
            continue
        pending = any(o.status in ("pending", "processing") for o in active_outbox)
        if pending or pid in handles:
            issues.append(
                LifecycleReconIssue(
                    code="lifecycle_lag",
                    position_id=pid,
                    detail=(
                        "lifecycle/outbox without PositionState "
                        "(pending outbox or opening-fill handle)"
                    ),
                )
            )
        else:
            issues.append(
                LifecycleReconIssue(
                    code="orphan_lifecycle",
                    position_id=pid,
                    detail="lifecycle events/outbox without matching PositionState",
                )
            )

    drift_codes = {
        "missing_open_event",
        "missing_close_event",
        "qty_mismatch",
        "orphan_lifecycle",
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

    checked = len({*_lifecycle_union_ids(positions, snapshots_by_position, outbox)})
    return LifecycleReconciliation(
        account_id=account_id,
        status=status,
        checked=checked,
        drift_count=drift_count,
        lag_count=lag_count,
        blocked_count=blocked_count,
        issues=tuple(issues),
    )


def _lifecycle_union_ids(
    positions: list[PositionStateSnap],
    snapshots_by_position: dict[str, dict[str, Any]],
    outbox: list[OutboxSnap],
) -> set[str]:
    ids: set[str] = set()
    for pos in positions:
        ids.add(pos.position_id)
    ids.update(snapshots_by_position.keys())
    for row in outbox:
        ids.add(row.position_id)
    return ids


@dataclass(frozen=True, slots=True)
class ReconcileLifecycleIntegrityInput:
    account_id: str


class ReconcileLifecycleIntegrity:
    """Detect/report PositionState ↔ Lifecycle. No heal."""

    def __init__(
        self,
        *,
        positions: PositionStatesPort,
        snapshots: LifecycleSnapshotPort | LifecycleBatchSnapshotPort,
        outbox: OutboxListPort,
        opening_fill_position_ids: set[str] | frozenset[str] | None = None,
    ) -> None:
        self._positions = positions
        self._snapshots = snapshots
        self._outbox = outbox
        self._opening_fill_ids = opening_fill_position_ids

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
        batch = getattr(self._snapshots, "execute_for_account", None)
        if callable(batch):
            snapshots_by_position = dict(await batch(account_id))
        else:
            execute = getattr(self._snapshots, "execute")
            needed: set[str] = set()
            for pos in snaps:
                needed.update(_lifecycle_keys(pos))
            for key in needed:
                snapshots_by_position[key] = await execute(key)

        # Ensure PositionState keys without events still have empty snaps when
        # batch path omitted them (no events for that id).
        for pos in snaps:
            for key in _lifecycle_keys(pos):
                if key not in snapshots_by_position:
                    execute = getattr(self._snapshots, "execute", None)
                    if callable(execute):
                        snapshots_by_position[key] = await execute(key)
                    else:
                        snapshots_by_position[key] = {
                            "positionId": key,
                            "events": [],
                            "accounting": None,
                        }

        outbox_rows = await self._outbox.list_for_account(account_id)
        return build_lifecycle_reconciliation(
            account_id=account_id,
            positions=snaps,
            snapshots_by_position=snapshots_by_position,
            outbox=list(outbox_rows),
            opening_fill_position_ids=self._opening_fill_ids,
        )


__all__ = [
    "LifecycleReconIssue",
    "LifecycleReconciliation",
    "OutboxSnap",
    "PositionStateSnap",
    "ReconcileLifecycleIntegrity",
    "ReconcileLifecycleIntegrityInput",
    "build_lifecycle_reconciliation",
    "fifo_outbox_head",
]
