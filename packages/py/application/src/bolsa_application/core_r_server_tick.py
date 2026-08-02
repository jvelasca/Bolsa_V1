"""CORE-R server tick (Q3.4 cron) — re-encola desde informe BD + PnL DEMO.

Espejo ligero de ``syncFromReport`` + prefs scheduler del cliente.
No pisa TOP · no auto-paper · no re-ejecuta Lista AUTO.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlencode
from uuid import uuid4

CORE_R_QUEUE_MAX = 40
CORE_R_PNL_LIST_CAP = 40
_ACTION_VERDICTS_SKIP = frozenset({"keep", "fresh_ok"})


def core_r_needs_action(verdict: object) -> bool:
    if not isinstance(verdict, str) or not verdict:
        return False
    return verdict not in _ACTION_VERDICTS_SKIP


def account_return_pct(initial_deposit: float, total_equity: float) -> float | None:
    if not isinstance(initial_deposit, (int, float)) or initial_deposit <= 0:
        return None
    if not isinstance(total_equity, (int, float)):
        return None
    return ((float(total_equity) - float(initial_deposit)) / float(initial_deposit)) * 100.0


def paper_pnl_degradation(return_pct: float | None) -> dict[str, str] | None:
    """Umbrales cliente: ≤−10 consider_replace · ≤−5 review_lab."""
    if return_pct is None or not isinstance(return_pct, (int, float)):
        return None
    pct = float(return_pct)
    if pct <= -10:
        return {
            "level": "consider_replace",
            "reason": f"Demo/paper PnL {pct:.1f}% vs depósito · valorar cambio",
        }
    if pct <= -5:
        return {
            "level": "review_lab",
            "reason": f"Demo/paper PnL {pct:.1f}% · revisar Lab / checklist",
        }
    return None


def find_paper_for_top_slots(
    accounts: list[dict[str, Any]],
    strategy_ids: list[str],
) -> dict[str, Any] | None:
    """Prefer ``simulated`` over ``paper``; ignora cerradas. Espejo TS."""
    id_set = {s for s in strategy_ids if isinstance(s, str) and s}
    if not id_set:
        return None
    linked = [
        a
        for a in accounts
        if isinstance(a, dict)
        and a.get("type") in ("simulated", "paper")
        and a.get("status") != "closed"
        and isinstance(a.get("strategyDefinitionId"), str)
        and a.get("strategyDefinitionId")
    ]
    for a in linked:
        if a.get("type") == "simulated" and a["strategyDefinitionId"] in id_set:
            return a
    for a in linked:
        if a["strategyDefinitionId"] in id_set:
            return a
    return None


def _paper_pnl_actions(
    *,
    verdict: str,
    instrument_id: str,
    timeframe: str,
    symbol: str,
    slot1_run_id: str | None,
) -> list[dict[str, str]]:
    finalists = "/backtests?" + urlencode(
        {
            "tab": "run",
            "instrumentId": instrument_id,
            "focus": "finalists",
            "timeframe": timeframe,
        }
    )
    lab = "/backtests?" + urlencode(
        {
            "tab": "jobs",
            "instrumentId": instrument_id,
            "timeframe": timeframe,
        }
    )
    propose = "/help?" + urlencode(
        {
            "section": "ai-platform",
            "focus": "supervised-f3",
            "symbol": symbol,
        }
    )
    actions: list[dict[str, str]] = [
        {"id": "lab", "label": "Lab", "href": lab},
        {"id": "finalists", "label": "Finalistas", "href": finalists},
    ]
    if verdict == "consider_replace":
        actions.append({"id": "propose_f3", "label": "Proponer F3", "href": propose})
        if slot1_run_id:
            actions.append(
                {
                    "id": "checklist",
                    "label": "Checklist",
                    "href": "/backtests?"
                    + urlencode(
                        {
                            "tab": "run",
                            "instrumentId": instrument_id,
                            "runId": slot1_run_id,
                            "focus": "detail",
                            "openAnalysis": "1",
                            "timeframe": timeframe,
                        }
                    ),
                }
            )
    return actions


def build_paper_pnl_review_row(
    *,
    instrument_id: str,
    symbol: str,
    timeframe: str,
    return_pct: float,
    slot1_run_id: str | None = None,
) -> dict[str, Any] | None:
    hit = paper_pnl_degradation(return_pct)
    if hit is None:
        return None
    verdict = hit["level"]
    return {
        "instrumentId": instrument_id,
        "symbol": symbol,
        "verdict": verdict,
        "reason": hit["reason"],
        "actions": _paper_pnl_actions(
            verdict=verdict,
            instrument_id=instrument_id,
            timeframe=timeframe,
            symbol=symbol,
            slot1_run_id=slot1_run_id,
        ),
    }


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
    extra_rows: list[dict[str, Any]] | None = None,
    now_iso: str | None = None,
) -> tuple[list[dict[str, Any]], int]:
    """Devuelve (queue_nueva, added). Dedup open por listId+instrumentId."""
    action_rows = _action_rows_from_report(report)
    extras = [r for r in (extra_rows or []) if isinstance(r, dict) and core_r_needs_action(r.get("verdict"))]
    merged = [*action_rows, *extras]
    if not merged:
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
    for row in merged:
        instrument_id = str(row.get("instrumentId") or "")
        if not instrument_id:
            continue
        key = f"{list_id}:{instrument_id}"
        if key in open_keys:
            continue
        open_keys.add(key)
        actions = row.get("actions") if isinstance(row.get("actions"), list) else []
        row_tf = row.get("timeframe") if isinstance(row.get("timeframe"), str) else timeframe
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
                "timeframe": row_tf or "1d",
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
    extra_rows: list[dict[str, Any]] | None = None,
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
    new_queue, added = enqueue_from_report(
        queue,
        list_id=list_id,
        report=report,
        extra_rows=extra_rows,
        now_iso=now_iso,
    )
    scheduler["lastTickAt"] = now_iso
    scheduler["lastTickSource"] = "server_cron"
    # Señal multi-dispositivo: clientes con app abierta hacen toast al hidratar.
    if added > 0:
        scheduler["lastRemoteEnqueueAt"] = now_iso
        scheduler["lastRemoteEnqueueAdded"] = added

    meta = {"skipped": False, "added": added, "listId": list_id, "reason": "ok"}
    return {
        "queue": new_queue,
        "reports": reports,
        "scheduler": scheduler,
    }, meta
