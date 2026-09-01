"""V1.49 — EntryTick real: Estudio → Ranking → TradePlan → OpeningGate.

Adapta ``ProposeEstudioAutoOpenings`` al puerto ``PaperDeskEntryPort``.
Paper-D Composite queda fuera (Router rechaza ``autoSource=paper_d``).
"""

from __future__ import annotations

from datetime import date
from typing import Any, Protocol

from bolsa_application.daily_ops_report import (
    ESTUDIO_LIST_ID,
    ESTUDIO_STATUS_EMPTY,
    ESTUDIO_STATUS_OK,
    ESTUDIO_STATUS_UNAVAILABLE,
    EstudioUniverseResolution,
)
from bolsa_application.paper_desk_cycle import (
    PaperDeskEntryTickResult,
)

_EXECUTED_ACTION_STATUSES = frozenset({"trade_executed", "executed"})


class EstudioListPort(Protocol):
    async def execute(self, list_id: str) -> Any: ...


class EstudioAutoProposePort(Protocol):
    async def execute(self, payload: dict[str, Any]) -> dict[str, Any]: ...


async def resolve_estudio_universe(
    estudio_list: EstudioListPort | None,
) -> EstudioUniverseResolution:
    """Resuelve universo Estudio (≠ confundir empty con unavailable)."""
    if estudio_list is None:
        return EstudioUniverseResolution(status=ESTUDIO_STATUS_UNAVAILABLE)
    try:
        detail = await estudio_list.execute(ESTUDIO_LIST_ID)
    except Exception:
        return EstudioUniverseResolution(status=ESTUDIO_STATUS_UNAVAILABLE)
    if detail is None:
        return EstudioUniverseResolution(status=ESTUDIO_STATUS_UNAVAILABLE)
    raw = getattr(detail, "instrument_ids", None)
    if not isinstance(raw, list):
        return EstudioUniverseResolution(status=ESTUDIO_STATUS_UNAVAILABLE)
    ids = [str(i) for i in raw if i]
    if not ids:
        return EstudioUniverseResolution(status=ESTUDIO_STATUS_EMPTY)
    return EstudioUniverseResolution(status=ESTUDIO_STATUS_OK, instrument_ids=ids)


def _count_executed_actions(execution: dict[str, Any] | None) -> int:
    if not execution:
        return 0
    actions = execution.get("actions") or []
    return sum(
        1
        for action in actions
        if str(action.get("status") or "") in _EXECUTED_ACTION_STATUSES
    )


def map_estudio_propose_to_entry_tick(
    out: dict[str, Any],
    *,
    dry_run: bool,
) -> PaperDeskEntryTickResult:
    """Mapea salida ``ProposeEstudioAutoOpenings`` → ``PaperDeskEntryTickResult``."""
    hit_count = int(out.get("hitCount") or 0)
    skipped = out.get("skipped") or []
    skipped_count = len(skipped) if isinstance(skipped, list) else 0
    execute_status = str(out.get("executeStatus") or "dry_run")
    notes = tuple(str(n) for n in (out.get("notes") or []))

    if execute_status == "blocked_env":
        return PaperDeskEntryTickResult(
            status="blocked",
            reason="paper_auto_env_blocked",
            proposed_count=hit_count,
            skipped_count=skipped_count,
            notes=notes,
        )

    if dry_run or execute_status == "dry_run":
        return PaperDeskEntryTickResult(
            status="dry_run",
            proposed_count=hit_count,
            skipped_count=skipped_count,
            notes=notes,
        )

    execution = out.get("execution")
    executed_count = _count_executed_actions(
        execution if isinstance(execution, dict) else None
    )
    return PaperDeskEntryTickResult(
        status="executed",
        proposed_count=hit_count,
        executed_count=executed_count,
        skipped_count=skipped_count,
        notes=notes,
    )


class EstudioPaperDeskEntry:
    """EntryTick PAPER: lista Estudio → rank → TradePlan TRIGGERED → Router/check_opening."""

    def __init__(
        self,
        *,
        propose: EstudioAutoProposePort,
        estudio_list: EstudioListPort | None = None,
        max_candidates: int = 25,
    ) -> None:
        self._propose = propose
        self._estudio_list = estudio_list
        self._max_candidates = max_candidates

    async def run_entry_tick(
        self,
        *,
        account_id: str,
        as_of: str | None,
        dry_run: bool,
        paper_d_execute: bool,
        execution_policy_id: str | None,
        template_id: str | None,
    ) -> PaperDeskEntryTickResult:
        _ = template_id
        if not dry_run and not paper_d_execute:
            return PaperDeskEntryTickResult(
                status="blocked",
                reason="paper_auto_env_blocked",
                notes=("EntryTick blocked: PAPER_D_EXECUTE off.",),
            )

        universe = await resolve_estudio_universe(self._estudio_list)
        if universe.status == ESTUDIO_STATUS_UNAVAILABLE:
            return PaperDeskEntryTickResult(
                status="skipped",
                reason="estudio_universe_unavailable",
                notes=("Estudio list unavailable — 0 propuestas.",),
            )
        if universe.status == ESTUDIO_STATUS_EMPTY:
            return PaperDeskEntryTickResult(
                status="dry_run" if dry_run else "proposed",
                proposed_count=0,
                notes=("Estudio list empty — 0 candidatos.",),
            )

        as_of_bar: date | str | None = None
        if as_of:
            try:
                as_of_bar = date.fromisoformat(as_of.strip()[:10])
            except ValueError:
                as_of_bar = as_of.strip()[:10]

        payload: dict[str, Any] = {
            "instrumentIds": universe.instrument_ids,
            "accountId": account_id,
            "maxCandidates": self._max_candidates,
            "execute": (not dry_run) and paper_d_execute,
        }
        if as_of_bar is not None:
            payload["asOfBarDate"] = as_of_bar
        if execution_policy_id:
            payload["executionPolicyId"] = execution_policy_id

        if payload["execute"] and not execution_policy_id:
            return PaperDeskEntryTickResult(
                status="blocked",
                reason="execution_policy_required",
                notes=("executionPolicyId requerido cuando dryRun=false.",),
            )

        try:
            out = await self._propose.execute(payload)
        except ValueError as exc:
            return PaperDeskEntryTickResult(
                status="blocked",
                reason="entry_propose_failed",
                notes=(str(exc),),
            )

        return map_estudio_propose_to_entry_tick(out, dry_run=dry_run)
