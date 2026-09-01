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
        "data_unavailable",
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
    entry_candidates: list[dict[str, Any]] = field(default_factory=list)
    entry_skipped: list[dict[str, Any]] = field(default_factory=list)
    exception_facts: list[dict[str, Any]] = field(default_factory=list)
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
        entry: dict[str, Any] = {
            "status": self.entry_status,
            "proposed": self.entry_proposed,
            "executed": self.entry_executed,
        }
        if self.entry_candidates:
            entry["candidates"] = list(self.entry_candidates)
        if self.entry_skipped:
            entry["skipped"] = list(self.entry_skipped)

        out: dict[str, Any] = {
            "schemaVersion": self.schema_version,
            "accountId": self.account_id,
            "asOf": self.as_of,
            "dryRun": self.dry_run,
            "paperDExecute": self.paper_d_execute,
            "blocked": self.blocked,
            "blockReason": self.block_reason,
            "entry": entry,
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
        if self.exception_facts:
            out["exceptionFacts"] = list(self.exception_facts)
        sections = _build_report_sections(self)
        if sections:
            out["sections"] = sections
        return out


def _build_report_sections(report: PaperDailyReportV1) -> dict[str, Any]:
    """V1.55 — DECISIONES / OPERATIVA / RESULTADO / NO OPERADAS."""
    trails = sum(
        1
        for row in report.position_rows
        if row.get("decisionAction") == "TRAIL"
        or row.get("decisionVerdict") == "TRAIL"
    )
    proposed = report.entry_proposed
    executed = report.entry_executed
    return {
        "decisiones": {
            "candidates": proposed,
            "proposed": proposed,
            "authorized": 1 if executed > 0 else 0,
            "executed": executed,
        },
        "operativa": {
            "entries": executed,
            "t1": report.position_reduced,
            "trails": trails,
            "exits": report.position_exited,
        },
        "resultado": {
            "realizedR": None,
            "dayPct": None,
        },
        "noOperadas": {
            "skipped": max(0, proposed - executed),
            "reasonCodes": {},
        },
    }


def _collect_exception_facts(cycle: PaperDeskCycleResult) -> list[dict[str, Any]]:
    """V1.54 — hechos operativos para proyección Desk (notes + entry)."""
    facts: list[dict[str, Any]] = []
    seen: set[str] = set()
    all_notes = list(cycle.notes) + list(cycle.entry.notes)

    def _add(kind: str, **fields: Any) -> None:
        if kind in seen:
            return
        seen.add(kind)
        fact: dict[str, Any] = {"kind": kind}
        for key, value in fields.items():
            if value is not None:
                fact[key] = value
        facts.append(fact)

    birth_note = any("position_birth_failed" in n for n in all_notes)
    birth_reason = cycle.entry.reason == "position_birth_failed"
    if birth_note or birth_reason:
        ctx: dict[str, Any] = {}
        for cand in cycle.entry.candidates:
            ctx = {
                "instrumentId": cand.instrument_id,
                "symbol": cand.symbol,
                "decisionId": cand.decision_id,
            }
            break
        _add("position_birth_failed", **ctx)

    if any(n == "portfolio_drift" or "portfolio_drift" in n for n in all_notes):
        _add("portfolio_recon_drift")

    if any(n == "recon_unavailable" or "recon_unavailable" in n for n in all_notes):
        _add("portfolio_recon_unavailable")

    return facts


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
        entry_candidates=[c.to_dict() for c in cycle.entry.candidates],
        entry_skipped=[s.to_dict() for s in cycle.entry.skipped],
        exception_facts=_collect_exception_facts(cycle),
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
