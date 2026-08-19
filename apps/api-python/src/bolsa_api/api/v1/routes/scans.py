"""API: escáneres y jobs en cola."""

import logging
from typing import Annotated

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
    ScanJobResponseDto,
    ScanJobsListResponseDto,
    ScanRunRequestDto,
    ScanRunResponseDto,
    to_scan_job_dto,
    to_scan_run_result_dto,
)
from bolsa_application.scan_jobs import EnqueueScanJob, GetScanJob, ListScanJobs
from bolsa_application.scan_manifests import GetScanManifest, PersistScanManifest
from bolsa_application.scans import RunScan
from bolsa_domain.platform_kernel import (
    validate_kernel_timeframe,
    validate_scan_bar_limit,
    validate_scan_max_results,
)

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

    result_dto = to_scan_run_result_dto(result)
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
    return ScanJobResponseDto(data=to_scan_job_dto(job))


@router.get("/scans/jobs", response_model=ScanJobsListResponseDto)
async def list_scan_jobs(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ScanJobsListResponseDto:
    use_case: ListScanJobs = get_list_scan_jobs_use_case(session)
    jobs = await use_case.execute(limit=20)
    return ScanJobsListResponseDto(data=[to_scan_job_dto(job) for job in jobs])


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
    return ScanJobResponseDto(data=to_scan_job_dto(job))
