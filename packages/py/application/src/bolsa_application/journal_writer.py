"""DecisionJournal — puerto append-only + helper best-effort (ADR-029 F1)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import uuid4

from bolsa_domain.entities.cognitive_artifacts import DecisionJournalEntryRecord


class JournalWriter(Protocol):
    """Puerto append-only para eventos del spine."""

    async def append(self, entry: DecisionJournalEntryRecord) -> DecisionJournalEntryRecord: ...


def attribution_setup_payload(
    trade_plan: dict[str, Any] | None = None,
    *,
    session_payload: dict[str, Any] | None = None,
    anchor: dict[str, Any] | None = None,
    base: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Ciclo 6 — snapshot thin de setup para payloads journal (JSONB libre).

    Copia ``entrySetup`` / ``tradePlanStatus`` / phase / effort cuando existen.
    No inventa campos; no es MFE ni expectancy.
    """
    out: dict[str, Any] = dict(base or {})
    plan = trade_plan if isinstance(trade_plan, dict) else None
    runtime: dict[str, Any] | None = None
    if isinstance(session_payload, dict):
        raw_rt = session_payload.get("runtime")
        if isinstance(raw_rt, dict):
            runtime = raw_rt
            if plan is None:
                candidate = raw_rt.get("tradePlan")
                if not isinstance(candidate, dict):
                    candidate = raw_rt.get("trade_plan")
                if isinstance(candidate, dict):
                    plan = candidate

    if isinstance(plan, dict):
        setup = plan.get("entrySetup")
        if not isinstance(setup, str):
            setup = plan.get("entry_setup")
        if isinstance(setup, str) and setup.strip():
            out.setdefault("entrySetup", setup.strip())
        status = plan.get("status")
        if isinstance(status, str) and status.strip():
            out.setdefault("tradePlanStatus", status.strip())

    resolved_anchor = anchor if isinstance(anchor, dict) else None
    if resolved_anchor is None and isinstance(runtime, dict):
        raw_a = runtime.get("wyckoffSpringAnchor")
        if not isinstance(raw_a, dict):
            raw_a = runtime.get("wyckoff_spring_anchor")
        if isinstance(raw_a, dict):
            resolved_anchor = raw_a
    if isinstance(resolved_anchor, dict):
        phase = resolved_anchor.get("phase")
        if isinstance(phase, str) and phase.strip():
            out.setdefault("phase", phase.strip())
        effort = resolved_anchor.get("effort")
        if isinstance(effort, str) and effort.strip():
            out.setdefault("effort", effort.strip())
    return out


async def append_journal_event(
    writer: JournalWriter | None,
    *,
    event_type: str,
    decision_id: str,
    actor: str = "system",
    session_id: str | None = None,
    account_id: str | None = None,
    instrument_id: str | None = None,
    payload: dict[str, Any] | None = None,
) -> None:
    """Best-effort: nunca tumba propose/confirm/router."""
    if writer is None or not decision_id:
        return
    try:
        now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        entry = DecisionJournalEntryRecord(
            id=f"JNL-{uuid4().hex[:12]}",
            decision_id=decision_id,
            event_type=event_type,
            actor=actor,
            created_at=now,
            session_id=session_id,
            account_id=account_id,
            instrument_id=instrument_id,
            payload=payload,
        )
        await writer.append(entry)
    except Exception:  # noqa: BLE001 — audit best-effort
        pass
