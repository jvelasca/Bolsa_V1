"""V2.0.3 SEMI Confirm protect to lifecycle TRAIL_APPLIED (sidecar).

Reuses AUTO mapping. Does NOT change TRANSITIONS.
Only emits when current stage already allows TRAIL_APPLIED
(t1_executed | trailing | t2_executed). Pre-T1 = fail-soft skip (no outbox poison).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from bolsa_application.lifecycle_from_auto import (
    append_lifecycle_from_auto,
    build_lifecycle_auto_mapping,
)
from bolsa_domain.lifecycle import reduce_lifecycle_events

logger = logging.getLogger(__name__)

TRAIL_ALLOWED_STAGES = frozenset({"t1_executed", "trailing", "t2_executed"})


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


async def _current_lifecycle_stage(
    lifecycle_append: Any | None,
    position_id: str,
) -> str | None:
    if lifecycle_append is None:
        return None
    store = getattr(lifecycle_append, "store", None)
    if store is None:
        return None
    try:
        events = await store.list_by_position(position_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("semi_protect trail stage lookup failed: %s", exc)
        return None
    if not events:
        return "candidate"
    stage, _lineage = reduce_lifecycle_events(events)
    return stage


async def maybe_append_lifecycle_semi_protect(
    *,
    lifecycle_append: Any | None,
    lifecycle_outbox: Any | None,
    account_id: str,
    instrument_id: str,
    position_id: str,
    previous_stop: float | None,
    new_stop: float,
    event_id: str,
    filled_at: str | None = None,
    decision_id: str | None = None,
    trade_plan_id: str | None = None,
    origin: str = "protect",
) -> dict[str, Any]:
    """Append TRAIL_APPLIED after SEMI protect when stage allows.

    Returns status skipped|pending|applied|error. Never raises to caller path
    when stage forbids (fail-soft); outbox enqueue errors still propagate when
    outbox is wired and stage is allowed (same TX discipline as AUTO).
    """
    if lifecycle_append is None and lifecycle_outbox is None:
        return {"status": "skipped", "reason": "lifecycle_append_not_wired"}

    pid = (position_id or "").strip()
    if not pid:
        return {"status": "skipped", "reason": "missing_position_id"}

    stage = await _current_lifecycle_stage(lifecycle_append, pid)
    if stage is None:
        # Cannot gate → fail-soft (avoid dead_head on open / unknown).
        return {"status": "skipped", "reason": "stage_unknown"}
    if stage not in TRAIL_ALLOWED_STAGES:
        return {
            "status": "skipped",
            "reason": "stage_forbids_trail",
            "stage": stage,
        }

    verdict = "TRAIL" if (origin or "").lower() == "trail" else "PROTECT"
    mapping = build_lifecycle_auto_mapping(
        verdict=verdict,
        reason_code="TRAIL" if verdict == "TRAIL" else "PROTECT",
        account_id=account_id,
        instrument_id=instrument_id,
        position_id=pid,
        event_id=event_id.strip(),
        previous_stop=previous_stop,
        new_stop=float(new_stop),
        filled_at=(filled_at or "").strip() or _now_iso(),
        decision_id=decision_id,
        trade_plan_id=trade_plan_id,
    )
    if mapping is None:
        return {"status": "skipped", "reason": "unmapped_or_missing_timestamp"}

    return await append_lifecycle_from_auto(
        lifecycle_append,
        mapping=mapping,
        outbox=lifecycle_outbox,
    )


__all__ = [
    "TRAIL_ALLOWED_STAGES",
    "maybe_append_lifecycle_semi_protect",
]
