"""API: políticas de ejecución."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_api.api.dependencies import (
    get_create_execution_policy_use_case,
    get_db_session,
    get_delete_execution_policy_use_case,
    get_execute_scan_job_hits_use_case,
    get_execution_policy_use_case,
    get_execution_router_use_case,
    get_list_execution_policies_use_case,
    get_update_execution_policy_use_case,
)
from bolsa_api.schemas.execution_policies import (
    CreateExecutionPolicyRequestDto,
    ExecuteScanJobRequestDto,
    ExecutionActionResultDto,
    ExecutionPoliciesListResponseDto,
    ExecutionPolicyDetailDto,
    ExecutionPolicyResponseDto,
    ExecutionPolicySummaryDto,
    RouteSignalsRequestDto,
    RouteSignalsResponseDto,
    UpdateExecutionPolicyRequestDto,
)
from bolsa_application.execution_policies import (
    CreateExecutionPolicy,
    DeleteExecutionPolicy,
    GetExecutionPolicy,
    ListExecutionPolicies,
    UpdateExecutionPolicy,
)
from bolsa_application.execution_router import (
    ExecuteScanJobHits,
    ExecutionActionResult,
    ExecutionRouter,
)
from bolsa_domain.entities.execution_policy import ExecutionPolicyRecord

router = APIRouter()


def _summary(record: ExecutionPolicyRecord) -> ExecutionPolicySummaryDto:
    definition = record.definition
    return ExecutionPolicySummaryDto(
        id=record.id,
        name=record.name,
        mode=record.mode,
        account_id=record.account_id,
        strategy_definition_id=record.strategy_definition_id,
        signal_kinds=[str(kind) for kind in definition.get("signalKinds") or []],
        require_validated_backtest=bool(definition.get("requireValidatedBacktest", False)),
        enabled=record.enabled,
        updated_at=record.updated_at,
        created_at=record.created_at,
    )


def _detail(record: ExecutionPolicyRecord) -> ExecutionPolicyDetailDto:
    return ExecutionPolicyDetailDto(
        **_summary(record).model_dump(),
        definition=record.definition,
    )


def _action_dto(action: ExecutionActionResult) -> ExecutionActionResultDto:
    dispatches = None
    if action.dispatches:
        dispatches = [
            {
                "channel": item.channel,
                "ok": item.ok,
                "error": item.error,
            }
            for item in action.dispatches
        ]
    return ExecutionActionResultDto(
        instrument_id=action.instrument_id,
        signal_kind=action.signal_kind,
        status=action.status,
        reason=action.reason,
        transaction_id=action.transaction_id,
        dispatches=dispatches,
    )


@router.get("/execution-policies", response_model=ExecutionPoliciesListResponseDto)
async def list_execution_policies(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    enabled_only: bool = False,
) -> ExecutionPoliciesListResponseDto:
    use_case: ListExecutionPolicies = get_list_execution_policies_use_case(session)
    records = await use_case.execute(limit=50, enabled_only=enabled_only)
    return ExecutionPoliciesListResponseDto(data=[_summary(r) for r in records])


@router.get("/execution-policies/{policy_id}", response_model=ExecutionPolicyResponseDto)
async def get_execution_policy(
    policy_id: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ExecutionPolicyResponseDto:
    use_case: GetExecutionPolicy = get_execution_policy_use_case(session)
    record = await use_case.execute(policy_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Execution policy not found")
    return ExecutionPolicyResponseDto(data=_detail(record))


@router.post("/execution-policies", response_model=ExecutionPolicyResponseDto, status_code=201)
async def create_execution_policy(
    body: CreateExecutionPolicyRequestDto,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ExecutionPolicyResponseDto:
    use_case: CreateExecutionPolicy = get_create_execution_policy_use_case(session)
    try:
        record = await use_case.execute(
            name=body.name,
            mode=body.mode,
            account_id=body.account_id,
            strategy_definition_id=body.strategy_definition_id,
            signal_kinds=body.signal_kinds,
            channels=body.channels,
            webhook_url=body.webhook_url,
            email_to=body.email_to,
            require_validated_backtest=body.require_validated_backtest,
            origin=body.origin,
            enabled=body.enabled,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ExecutionPolicyResponseDto(data=_detail(record))


@router.patch("/execution-policies/{policy_id}", response_model=ExecutionPolicyResponseDto)
async def update_execution_policy(
    policy_id: str,
    body: UpdateExecutionPolicyRequestDto,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ExecutionPolicyResponseDto:
    use_case: UpdateExecutionPolicy = get_update_execution_policy_use_case(session)
    try:
        record = await use_case.execute(
            policy_id,
            name=body.name,
            mode=body.mode,
            account_id=body.account_id,
            strategy_definition_id=body.strategy_definition_id,
            signal_kinds=body.signal_kinds,
            channels=body.channels,
            webhook_url=body.webhook_url,
            email_to=body.email_to,
            require_validated_backtest=body.require_validated_backtest,
            enabled=body.enabled,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if record is None:
        raise HTTPException(status_code=404, detail="Execution policy not found")
    return ExecutionPolicyResponseDto(data=_detail(record))


@router.delete("/execution-policies/{policy_id}", status_code=204)
async def delete_execution_policy(
    policy_id: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> None:
    use_case: DeleteExecutionPolicy = get_delete_execution_policy_use_case(session)
    deleted = await use_case.execute(policy_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Execution policy not found")


@router.post("/execution-policies/{policy_id}/route", response_model=RouteSignalsResponseDto)
async def route_signals_through_policy(
    policy_id: str,
    body: RouteSignalsRequestDto,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> RouteSignalsResponseDto:
    use_case: ExecutionRouter = get_execution_router_use_case(session)
    try:
        result = await use_case.execute(policy_id, body.hits)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RouteSignalsResponseDto(
        data={
            "policyId": result.policy_id,
            "mode": result.mode,
            "actions": [_action_dto(action).model_dump(by_alias=True) for action in result.actions],
        }
    )


@router.post("/scans/jobs/{job_id}/execute", response_model=RouteSignalsResponseDto)
async def execute_scan_job_hits(
    job_id: str,
    body: ExecuteScanJobRequestDto,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> RouteSignalsResponseDto:
    use_case: ExecuteScanJobHits = get_execute_scan_job_hits_use_case(session)
    try:
        result = await use_case.execute(job_id, body.policy_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RouteSignalsResponseDto(
        data={
            "policyId": result.policy_id,
            "mode": result.mode,
            "actions": [_action_dto(action).model_dump(by_alias=True) for action in result.actions],
        }
    )
