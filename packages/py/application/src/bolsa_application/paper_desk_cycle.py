"""V1.46 — PaperDeskCycle: EntryTick + PositionTick (sesión PAPER).

Un ciclo por asOf. dry_run default true. Sin cron / multi-día.
PAPER_D_EXECUTE default off; execute real solo si env + !dry_run.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from bolsa_analytics.cognitive.exit_plan import ExitPlan, build_exit_plan_from_position
from bolsa_analytics.cognitive.operating_policy import (
    OperatingPolicy,
    resolve_operating_policy,
)
from bolsa_analytics.cognitive.position_state import (
    PositionState,
    position_state_from_dict,
)
from bolsa_application.execute_position_policy_auto import (
    ExecutePositionPolicyAuto,
    ExecutePositionPolicyAutoInput,
    ExecutePositionPolicyAutoResult,
)
from bolsa_application.paper_d_propose import paper_d_execute_allowed
from bolsa_application.persist_position_from_exit import row_position_state

PaperDeskEntryStatus = Literal[
    "proposed",
    "executed",
    "blocked",
    "skipped",
    "dry_run",
]

PaperDeskPositionRowStatus = Literal[
    "held",
    "denied",
    "protected",
    "reduced",
    "exited",
    "sell_skipped",
    "error",
    "no_plan",
    "skipped",
]


@dataclass(frozen=True, slots=True)
class PaperDeskEntryTickResult:
    status: PaperDeskEntryStatus
    proposed_count: int = 0
    executed_count: int = 0
    skipped_count: int = 0
    reason: str | None = None
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "proposedCount": self.proposed_count,
            "executedCount": self.executed_count,
            "skippedCount": self.skipped_count,
            "reason": self.reason,
            "notes": list(self.notes),
        }


@dataclass(frozen=True, slots=True)
class PaperDeskPositionTickRow:
    instrument_id: str
    status: PaperDeskPositionRowStatus
    reason: str | None = None
    decision_verdict: str | None = None
    permission_reasons: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "instrumentId": self.instrument_id,
            "status": self.status,
            "reason": self.reason,
            "decisionVerdict": self.decision_verdict,
            "permissionReasons": list(self.permission_reasons),
        }


@dataclass(frozen=True, slots=True)
class PaperDeskCycleResult:
    account_id: str
    as_of: str | None
    dry_run: bool
    paper_d_execute: bool
    entry: PaperDeskEntryTickResult
    positions: tuple[PaperDeskPositionTickRow, ...]
    notes: tuple[str, ...] = ()
    blocked: bool = False
    block_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "accountId": self.account_id,
            "asOf": self.as_of,
            "dryRun": self.dry_run,
            "paperDExecute": self.paper_d_execute,
            "blocked": self.blocked,
            "blockReason": self.block_reason,
            "entry": self.entry.to_dict(),
            "positions": [p.to_dict() for p in self.positions],
            "counts": {
                "held": sum(1 for p in self.positions if p.status == "held"),
                "denied": sum(1 for p in self.positions if p.status == "denied"),
                "protected": sum(1 for p in self.positions if p.status == "protected"),
                "reduced": sum(1 for p in self.positions if p.status == "reduced"),
                "exited": sum(1 for p in self.positions if p.status == "exited"),
                "sellSkipped": sum(
                    1 for p in self.positions if p.status == "sell_skipped"
                ),
                "error": sum(1 for p in self.positions if p.status == "error"),
                "noPlan": sum(1 for p in self.positions if p.status == "no_plan"),
            },
            "notes": list(self.notes),
        }


class PaperDeskEntryPort(Protocol):
    """Puerto EntryTick — Estudio AUTO / Paper-D propose (dry-run por defecto)."""

    async def run_entry_tick(
        self,
        *,
        account_id: str,
        as_of: str | None,
        dry_run: bool,
        paper_d_execute: bool,
        execution_policy_id: str | None,
        template_id: str | None,
    ) -> PaperDeskEntryTickResult: ...


class PaperDeskOpenPositionsPort(Protocol):
    async def list_open(self, account_id: str) -> list[Any]: ...


@dataclass(frozen=True, slots=True)
class PaperDeskCycleInput:
    account_id: str
    as_of: str | None = None
    dry_run: bool = True
    execution_policy_id: str | None = None
    template_id: str | None = "moderate"
    mark_prices: dict[str, float] = field(default_factory=dict)
    default_mark_price: float | None = None
    data_stale: bool = False
    market_closed: bool = False
    portfolio_drift: bool = False
    immediate_risk: bool = False
    trail_hint: bool = False
    trail_stop: float | None = None
    # Si True y dry_run=False sin env → result blocked (HTTP 403 en capa ruta).
    require_env_for_execute: bool = True


class HonestStubPaperDeskEntry:
    """EntryTick honesto cuando no hay Estudio/Paper-D cableado en el ciclo."""

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
        _ = account_id, as_of, execution_policy_id, template_id
        if not dry_run and not paper_d_execute:
            return PaperDeskEntryTickResult(
                status="blocked",
                reason="paper_auto_env_blocked",
                notes=("EntryTick blocked: PAPER_D_EXECUTE off.",),
            )
        if dry_run:
            return PaperDeskEntryTickResult(
                status="dry_run",
                notes=(
                    "EntryTick dry_run: propose Estudio/Paper-D no muta ledger.",
                    "Stub: 0 propuestas (wire ProposeEstudioAuto / Paper-D para counts).",
                ),
            )
        return PaperDeskEntryTickResult(
            status="skipped",
            notes=("EntryTick execute path stub — wire Estudio/Paper-D.",),
        )


def _instrument_id_from_row(row: Any) -> str | None:
    if isinstance(row, dict):
        raw = row.get("instrument_id") or row.get("instrumentId")
    else:
        raw = getattr(row, "instrument_id", None)
    if raw is None:
        return None
    s = str(raw).strip()
    return s or None


def _position_from_row(row: Any) -> PositionState | None:
    blob = row_position_state(row) if not isinstance(row, PositionState) else None
    if isinstance(row, PositionState):
        return row
    if blob is None and isinstance(row, dict):
        blob = row.get("position_state") or row.get("positionState")
        if isinstance(blob, dict):
            return position_state_from_dict(blob)
        return None
    if isinstance(blob, dict):
        return position_state_from_dict(blob)
    return None


def _row_from_auto_result(
    instrument_id: str,
    result: ExecutePositionPolicyAutoResult,
) -> PaperDeskPositionTickRow:
    verdict = result.decision.verdict if result.decision else None
    perm_reasons: tuple[str, ...] = ()
    if result.permission is not None:
        perm_reasons = tuple(result.permission.reasons)
    status: PaperDeskPositionRowStatus
    if result.status in (
        "held",
        "denied",
        "protected",
        "reduced",
        "exited",
        "sell_skipped",
        "error",
    ):
        status = result.status  # type: ignore[assignment]
    else:
        status = "error"
    return PaperDeskPositionTickRow(
        instrument_id=instrument_id,
        status=status,
        reason=result.reason,
        decision_verdict=verdict,
        permission_reasons=perm_reasons,
    )


def _dry_run_position_row(
    instrument_id: str,
    position: PositionState,
    exit_plan: ExitPlan,
    policy: OperatingPolicy,
    *,
    paper_d_execute: bool,
    data_stale: bool,
    market_closed: bool,
    portfolio_drift: bool,
    immediate_risk: bool,
    session_flag: Literal["open", "closed"],
) -> PaperDeskPositionTickRow:
    from bolsa_analytics.cognitive.position_policy_decision import decide_position_policy
    from bolsa_application.evaluate_exit_plan import auto_exit_permission

    decision = decide_position_policy(
        position,
        exit_plan,
        policy,
        session=session_flag,
        stale=data_stale,
        stop_touched=immediate_risk,
    )
    if decision.verdict == "HOLD":
        return PaperDeskPositionTickRow(
            instrument_id=instrument_id,
            status="held",
            reason=decision.defer_reason,
            decision_verdict=decision.verdict,
        )
    perm = auto_exit_permission(
        exit_plan,
        paper_d_execute=paper_d_execute,
        data_stale=data_stale,
        market_closed=market_closed,
        portfolio_drift=portfolio_drift,
        immediate_risk=immediate_risk,
        position_closed=position.status == "CLOSED",
    )
    if not perm.allowed:
        return PaperDeskPositionTickRow(
            instrument_id=instrument_id,
            status="denied",
            reason=",".join(perm.reasons) or "denied",
            decision_verdict=decision.verdict,
            permission_reasons=tuple(perm.reasons),
        )
    # dry_run: map verdict to intended mutation without persist
    mapped: PaperDeskPositionRowStatus
    if decision.verdict in ("PROTECT", "TRAIL"):
        mapped = "protected"
    elif decision.verdict == "REDUCE":
        mapped = "reduced"
    elif decision.verdict == "EXIT":
        mapped = "exited"
    else:
        mapped = "held"
    return PaperDeskPositionTickRow(
        instrument_id=instrument_id,
        status=mapped,
        reason="dry_run",
        decision_verdict=decision.verdict,
        permission_reasons=tuple(perm.reasons),
    )


class PaperDeskCycle:
    """Orquestador de un ciclo de sesión PAPER (Entry + Position)."""

    def __init__(
        self,
        *,
        entry: PaperDeskEntryPort,
        open_positions: PaperDeskOpenPositionsPort,
        execute_auto: ExecutePositionPolicyAuto | None = None,
    ) -> None:
        self._entry = entry
        self._open = open_positions
        self._execute_auto = execute_auto

    async def execute(self, inp: PaperDeskCycleInput) -> PaperDeskCycleResult:
        account_id = (inp.account_id or "").strip()
        env_ok = paper_d_execute_allowed()
        notes: list[str] = []
        if inp.dry_run:
            notes.append("dryRun=true — no ledger mutate.")
        if not env_ok:
            notes.append("PAPER_D_EXECUTE off.")

        if (
            not inp.dry_run
            and inp.require_env_for_execute
            and not env_ok
        ):
            entry = PaperDeskEntryTickResult(
                status="blocked",
                reason="paper_auto_env_blocked",
                notes=("paper_auto_env_blocked",),
            )
            return PaperDeskCycleResult(
                account_id=account_id,
                as_of=inp.as_of,
                dry_run=False,
                paper_d_execute=False,
                entry=entry,
                positions=(),
                notes=tuple(notes + ["paper_auto_env_blocked"]),
                blocked=True,
                block_reason="paper_auto_env_blocked",
            )

        entry = await self._entry.run_entry_tick(
            account_id=account_id,
            as_of=inp.as_of,
            dry_run=inp.dry_run,
            paper_d_execute=env_ok,
            execution_policy_id=inp.execution_policy_id,
            template_id=inp.template_id,
        )

        policy = resolve_operating_policy(inp.template_id)
        session_flag: Literal["open", "closed"] = (
            "closed" if inp.market_closed else "open"
        )
        rows_out: list[PaperDeskPositionTickRow] = []
        open_rows = await self._open.list_open(account_id)

        for row in open_rows:
            iid = _instrument_id_from_row(row)
            if not iid:
                continue
            pos = _position_from_row(row)
            if pos is None:
                rows_out.append(
                    PaperDeskPositionTickRow(
                        instrument_id=iid,
                        status="error",
                        reason="position_state_invalid",
                    )
                )
                continue

            mark = inp.mark_prices.get(iid)
            if mark is None:
                mark = inp.default_mark_price
            if mark is None and pos.actual_entry is not None:
                mark = float(pos.actual_entry)
            if mark is None or mark <= 0:
                rows_out.append(
                    PaperDeskPositionTickRow(
                        instrument_id=iid,
                        status="error",
                        reason="missing_mark_price",
                    )
                )
                continue

            exit_plan = build_exit_plan_from_position(
                pos,
                mark_price=float(mark),
                exit_policy=policy.exit,
                trail_hint=inp.trail_hint,
                trail_stop=inp.trail_stop,
            )
            if exit_plan is None:
                rows_out.append(
                    PaperDeskPositionTickRow(
                        instrument_id=iid,
                        status="no_plan",
                        reason="no_exit_plan",
                        decision_verdict="HOLD",
                    )
                )
                continue

            if inp.dry_run or self._execute_auto is None:
                rows_out.append(
                    _dry_run_position_row(
                        iid,
                        pos,
                        exit_plan,
                        policy,
                        paper_d_execute=env_ok if not inp.dry_run else env_ok,
                        data_stale=inp.data_stale,
                        market_closed=inp.market_closed,
                        portfolio_drift=inp.portfolio_drift,
                        immediate_risk=inp.immediate_risk,
                        session_flag=session_flag,
                    )
                )
                continue

            result = await self._execute_auto.execute(
                ExecutePositionPolicyAutoInput(
                    account_id=account_id,
                    instrument_id=iid,
                    position=pos,
                    exit_plan=exit_plan,
                    operating_policy=policy,
                    mark_price=float(mark),
                    paper_d_execute=env_ok,
                    data_stale=inp.data_stale,
                    market_closed=inp.market_closed,
                    portfolio_drift=inp.portfolio_drift,
                    immediate_risk=inp.immediate_risk,
                    session=session_flag,
                    stale=inp.data_stale,
                    as_of=inp.as_of,
                )
            )
            rows_out.append(_row_from_auto_result(iid, result))

        return PaperDeskCycleResult(
            account_id=account_id,
            as_of=inp.as_of,
            dry_run=inp.dry_run,
            paper_d_execute=env_ok,
            entry=entry,
            positions=tuple(rows_out),
            notes=tuple(notes),
        )
