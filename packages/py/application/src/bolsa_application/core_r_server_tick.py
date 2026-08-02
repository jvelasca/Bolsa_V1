"""CORE-R server tick (Q3.4 cron) — re-encola desde informe BD sin app abierta.

Espejo ligero de ``syncFromReport`` + prefs scheduler del cliente.
No pisa TOP · no auto-paper · no re-ejecuta Lista AUTO (solo lee ``reports_json``).
"""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

CORE_R_QUEUE_MAX = 40
_ACTION_VERDICTS_SKIP = frozenset({"keep", "fresh_ok"})


def core_r_needs_action(verdict: object) -> bool:
    if not isinstance(verdict, str) or not verdict:
        return False
    return verdict not in _ACTION_VERDICTS_SKIP


def scheduler_due(scheduler: dict[str, Any], *, now: datetime | None = None) -> bool:
    if not scheduler.get("enabled"):
        return False
    list_id = scheduler.get("listId")
    if not isinstance(list_id, str) or not list_id.strip():
        return False
    interval = scheduler.get("intervalMinutes", 60)
    try:
        minutes = int(interval)
    except (TypeError, ValueError):
        minutes = 60
    minutes = max(5, min(24 * 60, minutes))
    last = scheduler.get("lastTickAt")
    if not isinstance(last, str) or not last.strip():
        return True
    try:
        last_dt = datetime.fromisoformat(last.replace("Z", "+00:00"))
    except ValueError:
        return True
    if last_dt.tzinfo is None:
        last_dt = last_dt.replace(tzinfo=UTC)
    now_dt = now or datetime.now(tz=UTC)
    return (now_dt - last_dt.astimezone(UTC)).total_seconds() >= minutes * 60


def _action_rows_from_report(report: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(report, dict):
        return []
    rows = report.get("rows")
    if not isinstance(rows, list):
        return []
    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        if not core_r_needs_action(row.get("verdict")):
            continue
        out.append(row)
    return out


def enqueue_from_report(
    queue: list[dict[str, Any]],
    *,
    list_id: str,
    report: dict[str, Any] | None,
    now_iso: str | None = None,
) -> tuple[list[dict[str, Any]], int]:
    """Devuelve (queue_nueva, added). Dedup open por listId+instrumentId."""
    action_rows = _action_rows_from_report(report)
    if not action_rows:
        return list(queue), 0

    timeframe = "1d"
    if isinstance(report, dict) and isinstance(report.get("timeframe"), str):
        timeframe = report["timeframe"] or "1d"
    now = now_iso or datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")
    open_keys = {
        f"{item.get('listId')}:{item.get('instrumentId')}"
        for item in queue
        if isinstance(item, dict) and item.get("status") == "open"
    }
    next_items = list(queue)
    added = 0
    for row in action_rows:
        instrument_id = str(row.get("instrumentId") or "")
        if not instrument_id:
            continue
        key = f"{list_id}:{instrument_id}"
        if key in open_keys:
            continue
        open_keys.add(key)
        actions = row.get("actions") if isinstance(row.get("actions"), list) else []
        next_items.insert(
            0,
            {
                "id": f"crq-srv-{list_id[:8]}-{instrument_id[:8]}-{uuid4().hex[:8]}",
                "listId": list_id,
                "instrumentId": instrument_id,
                "symbol": str(row.get("symbol") or instrument_id[:8]),
                "verdict": row.get("verdict"),
                "reason": str(row.get("reason") or ""),
                "actions": actions,
                "timeframe": timeframe,
                "enqueuedAt": now,
                "status": "open",
                "source": "server_cron",
            },
        )
        added += 1

    open_items = [i for i in next_items if isinstance(i, dict) and i.get("status") == "open"]
    done_items = [i for i in next_items if isinstance(i, dict) and i.get("status") != "open"]
    trimmed = [*open_items, *done_items][:CORE_R_QUEUE_MAX]
    return trimmed, added


def apply_server_tick(
    state: dict[str, Any],
    *,
    force: bool = False,
    now: datetime | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """
    Aplica un tick sobre un blob account state.
    Returns (new_state, meta) where meta has skipped/added/listId/reason.
    """
    scheduler = deepcopy(state.get("scheduler") if isinstance(state.get("scheduler"), dict) else {})
    queue = list(state.get("queue") if isinstance(state.get("queue"), list) else [])
    reports = state.get("reports") if isinstance(state.get("reports"), dict) else {}

    meta: dict[str, Any] = {"skipped": True, "added": 0, "listId": "", "reason": "disabled"}
    if not scheduler.get("enabled") and not force:
        return state, meta

    list_id = scheduler.get("listId")
    if not isinstance(list_id, str) or not list_id.strip():
        meta["reason"] = "no_list"
        return state, meta
    list_id = list_id.strip()
    meta["listId"] = list_id

    if not force and not scheduler_due(scheduler, now=now):
        meta["reason"] = "not_due"
        return state, meta

    report = reports.get(list_id) if isinstance(reports.get(list_id), dict) else None
    now_dt = now or datetime.now(tz=UTC)
    now_iso = now_dt.astimezone(UTC).isoformat().replace("+00:00", "Z")
    new_queue, added = enqueue_from_report(queue, list_id=list_id, report=report, now_iso=now_iso)
    scheduler["lastTickAt"] = now_iso
    # Server ticks keep prefs; scope may stay shell/monitor for UI.
    scheduler["lastTickSource"] = "server_cron"

    meta = {"skipped": False, "added": added, "listId": list_id, "reason": "ok"}
    return {
        "queue": new_queue,
        "reports": reports,
        "scheduler": scheduler,
    }, meta
