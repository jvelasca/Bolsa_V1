"""API: escáneres y jobs en cola."""

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_analytics.signals.preset_catalog import is_valid_preset_key
from bolsa_api.api.dependencies import (
    get_db_session,
    get_enqueue_scan_job_use_case,
    get_list_scan_jobs_use_case,
    get_persist_scan_manifest_use_case,
    get_run_scan_use_case,
    get_scan_job_use_case,
    get_scan_manifest_use_case,
)
from bolsa_api.schemas.scans import (
    ScanHitDto,
    ScanJobDto,
    ScanJobResponseDto,
    ScanJobsListResponseDto,
    ScanRunRequestDto,
    ScanRunResponseDto,
    ScanRunResultDto,
    ScanSkippedInstrumentDto,
)
from bolsa_api.schemas.signals_evaluate import SignalEventV1Dto
from bolsa_application.scan_jobs import EnqueueScanJob, GetScanJob, ListScanJobs
from bolsa_application.scan_manifests import GetScanManifest, PersistScanManifest
from bolsa_application.scans import RunScan
from bolsa_domain.platform_kernel import (
    validate_kernel_timeframe,
    validate_scan_bar_limit,
    validate_scan_max_results,
)
from bolsa_infrastructure.database.repositories.scan_job_repository import ScanJobRecord

router = APIRouter()
logger = logging.getLogger(__name__)


def _validate_scan_request(body: ScanRunRequestDto) -> None:
    if body.preset_key is not None and not is_valid_preset_key(body.preset_key):
        raise HTTPException(status_code=400, detail="Invalid presetKey")
    try:
        validate_kernel_timeframe(body.timeframe)
        validate_scan_bar_limit(body.bar_limit)
        validate_scan_max_results(body.max_results)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _to_signal_dto(event) -> SignalEventV1Dto:
    return SignalEventV1Dto(
        id=event.id,
        instrument_id=event.instrument_id,
        timestamp=event.timestamp,
        kind=event.kind,
        strategy_definition_id=event.strategy_definition_id,
        strategy_version=event.strategy_version,
        bar_index=event.bar_index,
        price=event.price,
        data_version=event.data_version,
        indicator_snapshot_hash=event.indicator_snapshot_hash,
        preset_key=event.preset_key,
    )


def _run_result_dto(result, *, alarm_route: dict | None = None) -> ScanRunResultDto:
    return ScanRunResultDto(
        scan_id=result.scan_id,
        scanned_count=result.scanned_count,
        hit_count=result.hit_count,
        hits=[
            ScanHitDto(
                instrument_id=hit.instrument_id,
                symbol=hit.symbol,
                name=hit.name,
                signal=_to_signal_dto(hit.signal),
            )
            for hit in result.hits
        ],
        skipped=[
            ScanSkippedInstrumentDto(instrument_id=item.instrument_id, reason=item.reason)
            for item in result.skipped
        ],
        strategy_definition_id=result.strategy_definition_id,
        list_id=result.list_id,
        timeframe=result.timeframe,
        alarm_route=alarm_route,
    )


def _result_from_dict(raw: dict[str, Any]) -> ScanRunResultDto:
    return ScanRunResultDto.model_validate(raw)


def _job_dto(job: ScanJobRecord) -> ScanJobDto:
    result = _result_from_dict(job.result) if job.result is not None else None
    return ScanJobDto(
        id=job.id,
        status=job.status,
        payload=job.payload,
        result=result,
        error=job.error,
        cache_hits=job.cache_hits,
        cache_misses=job.cache_misses,
        tracker_definition_id=job.tracker_definition_id,
        created_at=job.created_at,
        updated_at=job.updated_at,
        completed_at=job.completed_at,
    )


@router.post("/scans/run", response_model=ScanRunResponseDto)
async def run_scan(
    body: ScanRunRequestDto,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ScanRunResponseDto:
    _validate_scan_request(body)
    use_case: RunScan = get_run_scan_use_case(session)
    try:
        result = await use_case.execute(
            universe_list_id=body.universe.list_id,
            universe_instrument_ids=body.universe.instrument_ids,
            strategy_definition_id=body.strategy_definition_id,
            definition=body.definition,
            preset_key=body.preset_key,
            timeframe=body.timeframe,
            bar_limit=body.bar_limit,
            max_results=body.max_results,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    result_dto = _run_result_dto(result)
    persist: PersistScanManifest = get_persist_scan_manifest_use_case(session)
    result_dict = {
        **result_dto.model_dump(by_alias=True),
        "instrumentSnapshots": result.instrument_snapshots,
        "strategyVersion": result.strategy_version,
    }
    try:
        await persist.execute(
            scan_id=result.scan_id,
            result=result_dict,
            payload=body.model_dump(by_alias=True, exclude_none=True),
        )
    except Exception:
        logger.exception("No se pudo persistir ScanManifest (scan %s)", result.scan_id)

    return ScanRunResponseDto(data=result_dto)


@router.post("/scans/jobs", response_model=ScanJobResponseDto, status_code=202)
async def enqueue_scan_job(
    body: ScanRunRequestDto,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ScanJobResponseDto:
    _validate_scan_request(body)
    use_case: EnqueueScanJob = get_enqueue_scan_job_use_case(session)
    try:
        job = await use_case.execute(body.model_dump(by_alias=True, exclude_none=True))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ScanJobResponseDto(data=_job_dto(job))


@router.get("/scans/jobs", response_model=ScanJobsListResponseDto)
async def list_scan_jobs(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ScanJobsListResponseDto:
    use_case: ListScanJobs = get_list_scan_jobs_use_case(session)
    jobs = await use_case.execute(limit=20)
    return ScanJobsListResponseDto(data=[_job_dto(job) for job in jobs])


@router.get("/scans/manifests/{scan_id}")
async def get_scan_manifest(
    scan_id: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, object]:
    use_case: GetScanManifest = get_scan_manifest_use_case(session)
    manifest = await use_case.execute(scan_id)
    if manifest is None:
        raise HTTPException(status_code=404, detail="Scan manifest not found")
    return {"data": manifest}


@router.get("/scans/jobs/{job_id}", response_model=ScanJobResponseDto)
async def get_scan_job(
    job_id: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ScanJobResponseDto:
    use_case: GetScanJob = get_scan_job_use_case(session)
    job = await use_case.execute(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Scan job not found")
    return ScanJobResponseDto(data=_job_dto(job))
