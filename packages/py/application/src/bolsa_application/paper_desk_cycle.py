"""V1.46/V1.47 — PaperDeskCycle: EntryTick stub + PositionTick (sesión PAPER).

V1.47: OperationalContext es la fuente de mark/session/freshness/drift/riesgo.
dry_run default true. Sin cron / multi-día. EntryTick = HonestStub.
PAPER_D_EXECUTE default off; execute real solo si env + !dry_run.
"""

from __future__ import annotations

from dataclasses import dataclass
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
from bolsa_application.operational_context import (
    OperationalContext,
    OperationalContextBuilder,
    PaperDeskNextAction,
    PortfolioSnapshot,
    resolve_paper_desk_next_action,
)
from bolsa_application.paper_d_propose import paper_d_execute_allowed
from bolsa_application.persist_position_from_exit import row_position_state
from bolsa_market.market_calendar import SessionState

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
    next_action: PaperDeskNextAction = "MANTENER"

    def to_dict(self) -> dict[str, Any]:
        return {
            "instrumentId": self.instrument_id,
            "status": self.status,
            "reason": self.reason,
            "decisionVerdict": self.decision_verdict,
            "permissionReasons": list(self.permission_reasons),
            "nextAction": self.next_action,
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
    context: OperationalContext | None = None
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


def _row_with_next(
    instrument_id: str,
    status: PaperDeskPositionRowStatus,
    *,
    reason: str | None = None,
    decision_verdict: str | None = None,
    permission_reasons: tuple[str, ...] = (),
    session: SessionState = "OPEN",
) -> PaperDeskPositionTickRow:
    next_action = resolve_paper_desk_next_action(
        status=status,
        decision_verdict=decision_verdict,
        permission_reasons=permission_reasons,
        reason=reason,
        session=session,
    )
    return PaperDeskPositionTickRow(
        instrument_id=instrument_id,
        status=status,
        reason=reason,
        decision_verdict=decision_verdict,
        permission_reasons=permission_reasons,
        next_action=next_action,
    )


def _row_from_auto_result(
    instrument_id: str,
    result: ExecutePositionPolicyAutoResult,
    *,
    session: SessionState,
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
    return _row_with_next(
        instrument_id,
        status,
        reason=result.reason,
        decision_verdict=verdict,
        permission_reasons=perm_reasons,
        session=session,
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
    session: SessionState,
) -> PaperDeskPositionTickRow:
    from bolsa_analytics.cognitive.position_policy_decision import decide_position_policy
    from bolsa_application.evaluate_exit_plan import auto_exit_permission

    session_flag: Literal["open", "closed"] = (
        "closed" if (market_closed or session != "OPEN") else "open"
    )
    decision = decide_position_policy(
        position,
        exit_plan,
        policy,
        session=session_flag,
        stale=data_stale,
        stop_touched=immediate_risk,
    )
    if decision.verdict == "HOLD":
        return _row_with_next(
            instrument_id,
            "held",
            reason=decision.defer_reason,
            decision_verdict=decision.verdict,
            session=session,
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
        return _row_with_next(
            instrument_id,
            "denied",
            reason=",".join(perm.reasons) or "denied",
            decision_verdict=decision.verdict,
            permission_reasons=tuple(perm.reasons),
            session=session,
        )
    mapped: PaperDeskPositionRowStatus
    if decision.verdict in ("PROTECT", "TRAIL"):
        mapped = "protected"
    elif decision.verdict == "REDUCE":
        mapped = "reduced"
    elif decision.verdict == "EXIT":
        mapped = "exited"
    else:
        mapped = "held"
    return _row_with_next(
        instrument_id,
        mapped,
        reason="dry_run",
        decision_verdict=decision.verdict,
        permission_reasons=tuple(perm.reasons),
        session=session,
    )


class PaperDeskCycle:
    """Orquestador de un ciclo de sesión PAPER (Entry + Position)."""

    def __init__(
        self,
        *,
        entry: PaperDeskEntryPort,
        open_positions: PaperDeskOpenPositionsPort,
        execute_auto: ExecutePositionPolicyAuto | None = None,
        context_builder: OperationalContextBuilder | None = None,
    ) -> None:
        self._entry = entry
        self._open = open_positions
        self._execute_auto = execute_auto
        self._builder = context_builder

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

        open_rows = await self._open.list_open(account_id)
        iids = [i for i in (_instrument_id_from_row(r) for r in open_rows) if i]
        ctx = inp.context
        if ctx is None and self._builder is not None:
            ctx = await self._builder.build(account_id, iids, as_of=inp.as_of)
        if ctx is None:
            ctx = OperationalContext(
                account_id=account_id,
                as_of=inp.as_of,
                session="OPEN",
                portfolio=PortfolioSnapshot(account_id=account_id, drift=False),
                markets={},
            )
            notes.append("operational_context_missing — fail-closed marks.")

        if ctx.portfolio.drift:
            notes.append("portfolio_drift")

        if ctx.portfolio.drift and not inp.dry_run:
            entry = PaperDeskEntryTickResult(
                status="blocked",
                reason="portfolio_drift",
                notes=("EntryTick blocked: portfolio_drift (OR-4).",),
            )
        else:
            entry = await self._entry.run_entry_tick(
                account_id=account_id,
                as_of=inp.as_of,
                dry_run=inp.dry_run,
                paper_d_execute=env_ok,
                execution_policy_id=inp.execution_policy_id,
                template_id=inp.template_id,
            )

        policy = resolve_operating_policy(inp.template_id)
        session = ctx.session
        market_closed = ctx.market_closed()
        session_flag: Literal["open", "closed"] = (
            "closed" if market_closed else "open"
        )
        rows_out: list[PaperDeskPositionTickRow] = []

        for row in open_rows:
            iid = _instrument_id_from_row(row)
            if not iid:
                continue
            pos = _position_from_row(row)
            if pos is None:
                rows_out.append(
                    _row_with_next(
                        iid,
                        "error",
                        reason="position_state_invalid",
                        session=session,
                    )
                )
                continue

            mark = ctx.mark_price(iid)
            snap = ctx.market_for(iid)
            if mark is None:
                rows_out.append(
                    _row_with_next(
                        iid,
                        "denied",
                        reason="data_unavailable",
                        permission_reasons=("data_unavailable",),
                        session=session,
                    )
                )
                continue

            data_stale = snap.is_stale() if snap is not None else True
            immediate_risk = ctx.stop_touched(iid, pos)
            portfolio_drift = ctx.portfolio.drift

            exit_plan = build_exit_plan_from_position(
                pos,
                mark_price=float(mark),
                exit_policy=policy.exit,
                trail_hint=ctx.trail_hint,
                trail_stop=ctx.trail_stop,
            )
            if exit_plan is None:
                rows_out.append(
                    _row_with_next(
                        iid,
                        "no_plan",
                        reason="no_exit_plan",
                        decision_verdict="HOLD",
                        session=session,
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
                        paper_d_execute=env_ok,
                        data_stale=data_stale,
                        market_closed=market_closed,
                        portfolio_drift=portfolio_drift,
                        immediate_risk=immediate_risk,
                        session=session,
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
                    data_stale=data_stale,
                    market_closed=market_closed,
                    portfolio_drift=portfolio_drift,
                    immediate_risk=immediate_risk,
                    session=session_flag,
                    stale=data_stale,
                    stop_touched=immediate_risk,
                    as_of=inp.as_of,
                )
            )
            rows_out.append(_row_from_auto_result(iid, result, session=session))

        return PaperDeskCycleResult(
            account_id=account_id,
            as_of=inp.as_of,
            dry_run=inp.dry_run,
            paper_d_execute=env_ok,
            entry=entry,
            positions=tuple(rows_out),
            notes=tuple(notes),
        )
