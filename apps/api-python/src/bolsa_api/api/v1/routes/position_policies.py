"""API: políticas de posición."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_api.api.dependencies import (
    get_create_position_policy_use_case,
    get_db_session,
    get_delete_position_policy_use_case,
    get_evaluate_position_exits_use_case,
    get_list_position_policies_use_case,
    get_position_policy_for_holding_use_case,
    get_position_policy_use_case,
    get_update_position_policy_use_case,
)
from bolsa_api.schemas.position_policies import (
    CreatePositionPolicyRequestDto,
    EvaluatePositionExitsResponseDto,
    PositionExitEvalResultDto,
    PositionPoliciesListResponseDto,
    PositionPolicyDetailDto,
    PositionPolicyResponseDto,
    PositionPolicySummaryDto,
    UpdatePositionPolicyRequestDto,
)
from bolsa_application.paper_auto_http_gate import (
    LabExitExecuteRetiredError,
    PaperAutoEnvBlockedError,
)
from bolsa_application.position_exit_evaluator import EvaluatePositionExits
from bolsa_application.position_policies import (
    CreatePositionPolicy,
    DeletePositionPolicy,
    GetPositionPolicy,
    GetPositionPolicyForHolding,
    ListPositionPolicies,
    UpdatePositionPolicy,
)
from bolsa_domain.entities.position_policy import PositionPolicyRecord

router = APIRouter()


def _summary(record: PositionPolicyRecord) -> PositionPolicySummaryDto:
    return PositionPolicySummaryDto(
        id=record.id,
        account_id=record.account_id,
        instrument_id=record.instrument_id,
        mode=record.mode,
        exit_strategy_definition_id=record.exit_strategy_definition_id,
        execution_policy_id=record.execution_policy_id,
        updated_at=record.updated_at,
        created_at=record.created_at,
    )


def _detail(record: PositionPolicyRecord) -> PositionPolicyDetailDto:
    return PositionPolicyDetailDto(
        **_summary(record).model_dump(),
        definition=record.definition,
    )


@router.get("/position-policies", response_model=PositionPoliciesListResponseDto)
async def list_position_policies(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    account_id: str | None = Query(default=None, alias="accountId"),
) -> PositionPoliciesListResponseDto:
    use_case: ListPositionPolicies = get_list_position_policies_use_case(session)
    records = await use_case.execute(account_id=account_id, limit=100)
    return PositionPoliciesListResponseDto(data=[_summary(r) for r in records])


@router.get("/position-policies/lookup", response_model=PositionPolicyResponseDto)
async def lookup_position_policy(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    account_id: str = Query(alias="accountId"),
    instrument_id: str = Query(alias="instrumentId"),
) -> PositionPolicyResponseDto:
    use_case: GetPositionPolicyForHolding = get_position_policy_for_holding_use_case(session)
    record = await use_case.execute(account_id, instrument_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Position policy not found")
    return PositionPolicyResponseDto(data=_detail(record))


@router.get("/position-policies/{policy_id}", response_model=PositionPolicyResponseDto)
async def get_position_policy(
    policy_id: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> PositionPolicyResponseDto:
    use_case: GetPositionPolicy = get_position_policy_use_case(session)
    record = await use_case.execute(policy_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Position policy not found")
    return PositionPolicyResponseDto(data=_detail(record))


@router.post("/position-policies", response_model=PositionPolicyResponseDto, status_code=201)
async def create_position_policy(
    body: CreatePositionPolicyRequestDto,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> PositionPolicyResponseDto:
    use_case: CreatePositionPolicy = get_create_position_policy_use_case(session)
    try:
        record = await use_case.execute(
            account_id=body.account_id,
            instrument_id=body.instrument_id,
            mode=body.mode,
            exit_strategy_definition_id=body.exit_strategy_definition_id,
            execution_policy_id=body.execution_policy_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return PositionPolicyResponseDto(data=_detail(record))


@router.patch("/position-policies/{policy_id}", response_model=PositionPolicyResponseDto)
async def update_position_policy(
    policy_id: str,
    body: UpdatePositionPolicyRequestDto,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> PositionPolicyResponseDto:
    use_case: UpdatePositionPolicy = get_update_position_policy_use_case(session)
    try:
        record = await use_case.execute(
            policy_id,
            mode=body.mode,
            exit_strategy_definition_id=body.exit_strategy_definition_id,
            execution_policy_id=body.execution_policy_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if record is None:
        raise HTTPException(status_code=404, detail="Position policy not found")
    return PositionPolicyResponseDto(data=_detail(record))


@router.delete("/position-policies/{policy_id}", status_code=204)
async def delete_position_policy(
    policy_id: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> None:
    use_case: DeletePositionPolicy = get_delete_position_policy_use_case(session)
    deleted = await use_case.execute(policy_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Position policy not found")


@router.post("/position-policies/evaluate-exits", response_model=EvaluatePositionExitsResponseDto)
async def evaluate_position_exits(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    account_id: str = Query(alias="accountId"),
    execute_trades: bool = Query(default=False, alias="executeTrades"),
    timeframe: str = Query(default="1d"),
) -> EvaluatePositionExitsResponseDto:
    if timeframe not in {"1d", "1wk"}:
        raise HTTPException(status_code=400, detail="timeframe must be 1d or 1wk")
    use_case: EvaluatePositionExits = get_evaluate_position_exits_use_case(session)
    try:
        result = await use_case.execute(
            account_id,
            execute_trades=execute_trades,
            timeframe=timeframe,
        )
    except (PaperAutoEnvBlockedError, LabExitExecuteRetiredError) as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return EvaluatePositionExitsResponseDto(
        data={
            "accountId": result.account_id,
            "evaluatedCount": result.evaluated_count,
            "results": [
                PositionExitEvalResultDto(
                    account_id=item.account_id,
                    instrument_id=item.instrument_id,
                    symbol=item.symbol,
                    quantity=item.quantity,
                    policy_id=item.policy_id,
                    mode=item.mode,
                    status=item.status,
                    signal=item.signal,
                    action=(
                        {
                            "instrumentId": item.action.instrument_id,
                            "signalKind": item.action.signal_kind,
                            "status": item.action.status,
                            "reason": item.action.reason,
                            "transactionId": item.action.transaction_id,
                        }
                        if item.action
                        else None
                    ),
                    reason=item.reason,
                )
                for item in result.results
            ],
        }
    )
