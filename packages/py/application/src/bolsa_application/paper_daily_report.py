"""V1.46 — PaperDailyReport / autoDesk projection from PaperDeskCycleResult."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from bolsa_application.paper_desk_cycle import PaperDeskCycleResult

PAPER_DAILY_REPORT_SCHEMA = "paper_daily_report_v1"

_JIT_DENY_CODES = frozenset(
    {
        "data_stale",
        "market_closed",
        "portfolio_drift",
        "paper_auto_env_blocked",
    }
)


@dataclass
class PaperDailyReportV1:
    schema_version: str = PAPER_DAILY_REPORT_SCHEMA
    account_id: str = ""
    as_of: str | None = None
    dry_run: bool = True
    paper_d_execute: bool = False
    entry_proposed: int = 0
    entry_executed: int = 0
    entry_status: str = "skipped"
    position_held: int = 0
    position_denied: int = 0
    position_protected: int = 0
    position_reduced: int = 0
    position_exited: int = 0
    position_rows: list[dict[str, Any]] = field(default_factory=list)
    jit_denies: dict[str, int] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    blocked: bool = False
    block_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schemaVersion": self.schema_version,
            "accountId": self.account_id,
            "asOf": self.as_of,
            "dryRun": self.dry_run,
            "paperDExecute": self.paper_d_execute,
            "blocked": self.blocked,
            "blockReason": self.block_reason,
            "entry": {
                "status": self.entry_status,
                "proposed": self.entry_proposed,
                "executed": self.entry_executed,
            },
            "positions": {
                "held": self.position_held,
                "denied": self.position_denied,
                "protected": self.position_protected,
                "reduced": self.position_reduced,
                "exited": self.position_exited,
                "rows": list(self.position_rows),
            },
            "jitDenies": dict(self.jit_denies),
            "notes": list(self.notes),
        }


def build_paper_daily_report(cycle: PaperDeskCycleResult) -> PaperDailyReportV1:
    """Proyecta PaperDeskCycleResult → PaperDailyReportV1 (autoDesk)."""
    jit: dict[str, int] = {k: 0 for k in sorted(_JIT_DENY_CODES)}
    notes = list(cycle.notes)
    notes.extend(cycle.entry.notes)

    if cycle.blocked or cycle.block_reason == "paper_auto_env_blocked":
        jit["paper_auto_env_blocked"] = jit.get("paper_auto_env_blocked", 0) + 1
        if "paper_auto_env_blocked" not in notes:
            notes.append("paper_auto_env_blocked")

    if cycle.dry_run and "dryRun" not in "".join(notes):
        notes.append("dryRun")

    held = denied = protected = reduced = exited = 0
    rows: list[dict[str, Any]] = []
    for p in cycle.positions:
        rows.append(p.to_dict())
        if p.status == "held":
            held += 1
        elif p.status == "denied":
            denied += 1
            for code in p.permission_reasons:
                if code in _JIT_DENY_CODES:
                    jit[code] = jit.get(code, 0) + 1
            if p.reason and "paper_auto_env_blocked" in p.reason:
                jit["paper_auto_env_blocked"] = jit.get("paper_auto_env_blocked", 0) + 1
        elif p.status == "protected":
            protected += 1
        elif p.status == "reduced":
            reduced += 1
        elif p.status == "exited":
            exited += 1

    return PaperDailyReportV1(
        account_id=cycle.account_id,
        as_of=cycle.as_of,
        dry_run=cycle.dry_run,
        paper_d_execute=cycle.paper_d_execute,
        entry_proposed=cycle.entry.proposed_count,
        entry_executed=cycle.entry.executed_count,
        entry_status=cycle.entry.status,
        position_held=held,
        position_denied=denied,
        position_protected=protected,
        position_reduced=reduced,
        position_exited=exited,
        position_rows=rows,
        jit_denies=jit,
        notes=notes,
        blocked=cycle.blocked,
        block_reason=cycle.block_reason,
    )
