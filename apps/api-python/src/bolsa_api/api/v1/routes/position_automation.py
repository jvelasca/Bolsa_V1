"""HTTP estrecho V1.47 — execute Position Policy AUTO (PAPER_D gate).

Mark / JIT se derivan de OperationalContext. El body no transporta hechos de mercado.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_analytics.cognitive.exit_plan import build_exit_plan_from_position
from bolsa_analytics.cognitive.operating_policy import resolve_operating_policy
from bolsa_analytics.cognitive.position_state import position_state_from_dict
from bolsa_api.api.dependencies import (
    get_db_session,
    get_execute_position_policy_auto_use_case,
    get_operational_context_builder,
)
from bolsa_application.execute_position_policy_auto import (
    ExecutePositionPolicyAuto,
    ExecutePositionPolicyAutoInput,
)
from bolsa_application.paper_d_propose import paper_d_execute_allowed
from bolsa_application.persist_position_from_exit import row_position_state

router = APIRouter()


class ExecutePositionPolicyAutoRequestDto(BaseModel):
    template_id: str | None = Field(default="moderate", alias="templateId")
    dry_run: bool = Field(default=False, alias="dryRun")

    model_config = {"populate_by_name": True}


class ExecutePositionPolicyAutoResponseDto(BaseModel):
    status: str
    reason: str | None = None
    decision: dict[str, Any] | None = None
    permission: dict[str, Any] | None = None
    dry_run: bool = Field(alias="dryRun")

    model_config = {"populate_by_name": True}


@router.post(
    "/position-automation/execute-auto",
    response_model=ExecutePositionPolicyAutoResponseDto,
)
async def execute_position_policy_auto(
    body: ExecutePositionPolicyAutoRequestDto,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    account_id: str = Query(alias="accountId"),
    instrument_id: str = Query(alias="instrumentId"),
    execution_policy_id: str | None = Query(default=None, alias="executionPolicyId"),
) -> ExecutePositionPolicyAutoResponseDto:
    """V1.47 — Policy → JIT Permission → protect|reduce|exit. Contexto servidor."""
    if not paper_d_execute_allowed() and not body.dry_run:
        raise HTTPException(
            status_code=403,
            detail={"code": "paper_auto_env_blocked", "message": "PAPER_D_EXECUTE off"},
        )

    uc, protect = get_execute_position_policy_auto_use_case(
        session, execution_policy_id=execution_policy_id
    )
    row = await protect.get_open(account_id, instrument_id)
    if row is None:
        raise HTTPException(status_code=404, detail="position_not_open")
    state = row_position_state(row)
    pos = position_state_from_dict(state)
    if pos is None:
        raise HTTPException(status_code=404, detail="position_state_invalid")

    builder = get_operational_context_builder(session)
    ctx = await builder.build(account_id, [instrument_id])
    mark = ctx.mark_price(instrument_id)
    if mark is None:
        raise HTTPException(
            status_code=409,
            detail={"code": "data_unavailable", "message": "NO MARKET DATA"},
        )

    snap = ctx.market_for(instrument_id)
    data_stale = snap.is_stale() if snap is not None else True
    market_closed = ctx.market_closed()
    portfolio_drift = ctx.portfolio.drift
    immediate_risk = ctx.stop_touched(instrument_id, pos)

    policy = resolve_operating_policy(body.template_id)
    exit_plan = build_exit_plan_from_position(
        pos,
        mark_price=float(mark),
        exit_policy=policy.exit,
        trail_hint=ctx.trail_hint,
        trail_stop=ctx.trail_stop,
    )
    if exit_plan is None:
        raise HTTPException(status_code=409, detail="no_exit_plan")

    session_flag: Literal["open", "closed"] = (
        "closed" if market_closed else "open"
    )
    inp = ExecutePositionPolicyAutoInput(
        account_id=account_id,
        instrument_id=instrument_id,
        position=pos,
        exit_plan=exit_plan,
        operating_policy=policy,
        mark_price=float(mark),
        paper_d_execute=paper_d_execute_allowed(),
        data_stale=data_stale,
        market_closed=market_closed,
        portfolio_drift=portfolio_drift,
        immediate_risk=immediate_risk,
        session=session_flag,
        stale=data_stale,
        stop_touched=immediate_risk,
    )

    if body.dry_run:
        from bolsa_analytics.cognitive.position_policy_decision import (
            decide_position_policy,
        )
        from bolsa_application.evaluate_exit_plan import auto_exit_permission

        decision = decide_position_policy(
            pos,
            exit_plan,
            policy,
            session=session_flag,
            stale=data_stale,
            stop_touched=immediate_risk,
        )
        if decision.verdict == "HOLD":
            return ExecutePositionPolicyAutoResponseDto(
                status="held",
                reason=decision.defer_reason,
                decision=decision.to_dict(),
                permission=None,
                dry_run=True,
            )
        perm = auto_exit_permission(
            exit_plan,
            paper_d_execute=paper_d_execute_allowed(),
            data_stale=data_stale,
            market_closed=market_closed,
            portfolio_drift=portfolio_drift,
            immediate_risk=immediate_risk,
            position_closed=pos.status == "CLOSED",
        )
        return ExecutePositionPolicyAutoResponseDto(
            status="allowed" if perm.allowed else "denied",
            reason=None if perm.allowed else ",".join(perm.reasons),
            decision=decision.to_dict(),
            permission=perm.to_dict(),
            dry_run=True,
        )

    if execution_policy_id is None or not str(execution_policy_id).strip():
        from bolsa_analytics.cognitive.position_policy_decision import (
            decide_position_policy,
        )

        preview = decide_position_policy(
            pos, exit_plan, policy, session=session_flag, stale=data_stale
        )
        if preview.verdict in ("REDUCE", "EXIT"):
            raise HTTPException(
                status_code=400,
                detail="executionPolicyId_required_for_reduce_exit",
            )

    assert isinstance(uc, ExecutePositionPolicyAuto)
    result = await uc.execute(inp)
    return ExecutePositionPolicyAutoResponseDto(
        status=result.status,
        reason=result.reason,
        decision=result.decision.to_dict() if result.decision else None,
        permission=result.permission.to_dict() if result.permission else None,
        dry_run=False,
    )
