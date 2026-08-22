"""API: trackers de producto (Ayuda/Config)."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_api.api.dependencies import (
    get_create_tracker_use_case,
    get_db_session,
    get_delete_tracker_use_case,
    get_enqueue_tracker_scan_job_use_case,
    get_list_trackers_use_case,
    get_process_tracker_schedules_use_case,
    get_run_tracker_scan_use_case,
    get_tracker_definition_use_case,
    get_update_tracker_use_case,
)
from bolsa_api.auth.principal import account_visible_to_principal
from bolsa_api.auth.request_principal import get_request_principal
from bolsa_api.schemas.scans import (
    ScanJobResponseDto,
    ScanRunResponseDto,
    to_scan_job_dto,
    to_scan_run_result_dto,
)
from bolsa_api.schemas.trackers import (
    CreateTrackerDefinitionRequestDto,
    EvaluateTrackerSchedulesResponseDto,
    TrackerDefinitionDetailDto,
    TrackerDefinitionResponseDto,
    TrackerDefinitionsListResponseDto,
    TrackerDefinitionSummaryDto,
    TrackerScheduleRunResultDto,
    UpdateTrackerDefinitionRequestDto,
)
from bolsa_application.tracker_schedule import ProcessTrackerSchedules
from bolsa_application.trackers import (
    CreateTrackerDefinition,
    DeleteTrackerDefinition,
    EnqueueTrackerScanJob,
    GetTrackerDefinition,
    ListTrackerDefinitions,
    RunTrackerScan,
    UpdateTrackerDefinition,
)
from bolsa_domain.entities.tracker_definition import TrackerDefinitionRecord

router = APIRouter()


def _require_tracker_access(
    record: TrackerDefinitionRecord | None,
    principal: str,
) -> TrackerDefinitionRecord:
    if record is None or not account_visible_to_principal(record.user_id, principal):
        raise HTTPException(status_code=404, detail="Tracker not found")
    return record


def _summary(record: TrackerDefinitionRecord) -> TrackerDefinitionSummaryDto:
    return TrackerDefinitionSummaryDto(
        id=record.id,
        name=record.name,
        strategy_definition_id=record.strategy_definition_id,
        strategy_version=record.strategy_version,
        timeframe=record.timeframe,
        evaluation_mode=record.evaluation_mode,
        origin=record.origin,
        enabled=record.enabled,
        updated_at=record.updated_at,
        created_at=record.created_at,
    )


def _detail(record: TrackerDefinitionRecord) -> TrackerDefinitionDetailDto:
    return TrackerDefinitionDetailDto(
        **_summary(record).model_dump(),
        definition=record.definition,
    )


@router.get("/trackers", response_model=TrackerDefinitionsListResponseDto)
async def list_trackers(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    enabled_only: bool = False,
) -> TrackerDefinitionsListResponseDto:
    principal = get_request_principal(request)
    use_case: ListTrackerDefinitions = get_list_trackers_use_case(session)
    records = await use_case.execute(
        limit=50,
        enabled_only=enabled_only,
        owner_user_id=principal,
    )
    return TrackerDefinitionsListResponseDto(data=[_summary(r) for r in records])


@router.post("/trackers/schedules/evaluate", response_model=EvaluateTrackerSchedulesResponseDto)
async def evaluate_tracker_schedules(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    tracker_id: str | None = Query(default=None, alias="trackerId"),
    force: bool = False,
) -> EvaluateTrackerSchedulesResponseDto:
    principal = get_request_principal(request)
    if tracker_id is not None:
        get_use_case: GetTrackerDefinition = get_tracker_definition_use_case(session)
        existing = await get_use_case.execute(tracker_id)
        _require_tracker_access(existing, principal)
    use_case: ProcessTrackerSchedules = get_process_tracker_schedules_use_case(session)
    result = await use_case.execute(
        tracker_id=tracker_id,
        force=force,
        owner_user_id=principal,
    )
    return EvaluateTrackerSchedulesResponseDto(
        data={
            "checkedCount": result.checked_count,
            "enqueuedCount": result.enqueued_count,
            "runs": [
                TrackerScheduleRunResultDto(
                    tracker_id=run.tracker_id,
                    tracker_name=run.tracker_name,
                    status=run.status,
                    scan_job_id=run.scan_job_id,
                    latest_bar_timestamp=run.latest_bar_timestamp,
                    reason=run.reason,
                )
                for run in result.runs
            ],
        }
    )


@router.get("/trackers/{tracker_id}", response_model=TrackerDefinitionResponseDto)
async def get_tracker(
    tracker_id: str,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> TrackerDefinitionResponseDto:
    principal = get_request_principal(request)
    use_case: GetTrackerDefinition = get_tracker_definition_use_case(session)
    record = await use_case.execute(tracker_id)
    record = _require_tracker_access(record, principal)
    return TrackerDefinitionResponseDto(data=_detail(record))


@router.post("/trackers", response_model=TrackerDefinitionResponseDto, status_code=201)
async def create_tracker(
    body: CreateTrackerDefinitionRequestDto,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> TrackerDefinitionResponseDto:
    use_case: CreateTrackerDefinition = get_create_tracker_use_case(session)
    try:
        record = await use_case.execute(
            name=body.name,
            strategy_definition_id=body.strategy_definition_id,
            universe=body.universe.model_dump(by_alias=True, exclude_none=True),
            strategy_version=body.strategy_version,
            timeframe=body.timeframe,
            bar_limit=body.bar_limit,
            max_results=body.max_results,
            evaluation_mode=body.evaluation_mode,
            rank_by=body.rank_by,
            default_execution_policy_id=body.default_execution_policy_id,
            schedule=body.schedule,
            origin=body.origin,
            source_prompt=body.source_prompt,
            enabled=body.enabled,
            user_id=get_request_principal(request),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return TrackerDefinitionResponseDto(data=_detail(record))


@router.patch("/trackers/{tracker_id}", response_model=TrackerDefinitionResponseDto)
async def update_tracker(
    tracker_id: str,
    body: UpdateTrackerDefinitionRequestDto,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> TrackerDefinitionResponseDto:
    principal = get_request_principal(request)
    get_use_case: GetTrackerDefinition = get_tracker_definition_use_case(session)
    existing = await get_use_case.execute(tracker_id)
    _require_tracker_access(existing, principal)
    use_case: UpdateTrackerDefinition = get_update_tracker_use_case(session)
    universe = (
        body.universe.model_dump(by_alias=True, exclude_none=True)
        if body.universe is not None
        else None
    )
    try:
        record = await use_case.execute(
            tracker_id,
            name=body.name,
            strategy_definition_id=body.strategy_definition_id,
            strategy_version=body.strategy_version,
            universe=universe,
            timeframe=body.timeframe,
            bar_limit=body.bar_limit,
            max_results=body.max_results,
            evaluation_mode=body.evaluation_mode,
            rank_by=body.rank_by,
            default_execution_policy_id=body.default_execution_policy_id,
            schedule=body.schedule,
            origin=body.origin,
            source_prompt=body.source_prompt,
            enabled=body.enabled,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if record is None:
        raise HTTPException(status_code=404, detail="Tracker not found")
    return TrackerDefinitionResponseDto(data=_detail(record))


@router.delete("/trackers/{tracker_id}", status_code=204)
async def delete_tracker(
    tracker_id: str,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> None:
    principal = get_request_principal(request)
    get_use_case: GetTrackerDefinition = get_tracker_definition_use_case(session)
    existing = await get_use_case.execute(tracker_id)
    _require_tracker_access(existing, principal)
    use_case: DeleteTrackerDefinition = get_delete_tracker_use_case(session)
    deleted = await use_case.execute(tracker_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Tracker not found")


@router.post("/trackers/{tracker_id}/scan", response_model=ScanRunResponseDto)
async def run_tracker_scan(
    tracker_id: str,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ScanRunResponseDto:
    principal = get_request_principal(request)
    get_use_case: GetTrackerDefinition = get_tracker_definition_use_case(session)
    existing = await get_use_case.execute(tracker_id)
    _require_tracker_access(existing, principal)
    use_case: RunTrackerScan = get_run_tracker_scan_use_case(session)
    try:
        outcome = await use_case.execute(tracker_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ScanRunResponseDto(
        data=to_scan_run_result_dto(outcome.scan, alarm_route=outcome.alarm_route),
    )


@router.post("/trackers/{tracker_id}/scan-jobs", response_model=ScanJobResponseDto, status_code=202)
async def enqueue_tracker_scan_job(
    tracker_id: str,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ScanJobResponseDto:
    principal = get_request_principal(request)
    get_use_case: GetTrackerDefinition = get_tracker_definition_use_case(session)
    existing = await get_use_case.execute(tracker_id)
    _require_tracker_access(existing, principal)
    use_case: EnqueueTrackerScanJob = get_enqueue_tracker_scan_job_use_case(session)
    try:
        job = await use_case.execute(tracker_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ScanJobResponseDto(data=to_scan_job_dto(job))
