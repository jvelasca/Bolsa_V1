"""API: cola durable de trabajos operativos AUTO (``auto_ops_jobs``).

Una sola ruta de ejecución para el scheduler y para la UI: ambos encolan el MISMO job
(``estudio_daily`` o ``dia_d_replay``) y observan el mismo estado, progreso y desenlace.

Fail-closed por cuenta: una cuenta ajena es **indistinguible de inexistente** (404 sin
detalles). Sin cuenta activa no se encola ni se lee nada (404 ``no_account_scope``).

El índice único parcial de la migración 056 garantiza una sola corrida ACTIVA por
``(kind, cuenta, día)``: reencolar devuelve el job activo existente.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_api.api.dependencies import (
    get_account_id_header,
    get_db_session,
    resolve_account_scope_or_default,
)
from bolsa_application.auto_ops_jobs import (
    EnqueueAutoOpsJob,
    GetAutoOpsJob,
    ListAutoOpsJobs,
)
from bolsa_domain.entities.auto_ops_job import AutoOpsJob
from bolsa_infrastructure.database.repositories.auto_ops_job_repository import (
    SqlAlchemyAutoOpsJobRepository,
)

router = APIRouter()
logger = logging.getLogger(__name__)


class AutoOpsJobDto(BaseModel):
    """Foto de un job (progreso y resultado son datos; un hueco queda vacío, nunca en 0)."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    kind: str
    status: str
    day: str
    account_id: str | None = Field(default=None, alias="accountId")
    payload: dict[str, Any] = Field(default_factory=dict)
    progress: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    attempt: int = 0
    created_at: str | None = Field(default=None, alias="createdAt")
    started_at: str | None = Field(default=None, alias="startedAt")
    finished_at: str | None = Field(default=None, alias="finishedAt")
    heartbeat_at: str | None = Field(default=None, alias="heartbeatAt")


class AutoOpsJobListDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    jobs: list[AutoOpsJobDto] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class AutoOpsJobCreateDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    kind: str
    day: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


def job_to_dto(job: AutoOpsJob) -> AutoOpsJobDto:
    return AutoOpsJobDto(
        id=job.id,
        kind=job.kind,
        status=job.status,
        day=job.day,
        account_id=job.account_id,
        payload=dict(job.payload or {}),
        progress=dict(job.progress or {}),
        result=dict(job.result or {}),
        error=job.error,
        attempt=job.attempt,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
        heartbeat_at=job.heartbeat_at,
    )


def _no_scope() -> HTTPException:
    return HTTPException(
        status_code=404, detail="no_account_scope: no hay cuenta activa del principal"
    )


@router.post("/auto/ops-jobs", response_model=AutoOpsJobDto)
async def create_auto_ops_job(
    body: AutoOpsJobCreateDto,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    account_id: Annotated[str | None, Depends(get_account_id_header)] = None,
) -> AutoOpsJobDto:
    """Encola (o devuelve el activo) del job indicado para la cuenta activa."""
    scope = await resolve_account_scope_or_default(request, account_id)
    if scope is None:
        raise _no_scope()
    repo = SqlAlchemyAutoOpsJobRepository(session)
    try:
        job = await EnqueueAutoOpsJob(repo).execute(
            kind=body.kind,
            account_id=scope,
            day=body.day,
            payload=body.payload,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await session.commit()
    logger.info(
        "auto_ops_job encolado %s (%s · día %s · cuenta %s)",
        job.id,
        job.kind,
        job.day,
        job.account_id,
    )
    return job_to_dto(job)


@router.get("/auto/ops-jobs", response_model=AutoOpsJobListDto)
async def list_auto_ops_jobs(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    kind: Annotated[str | None, Query()] = None,
    day: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    account_id: Annotated[str | None, Depends(get_account_id_header)] = None,
) -> AutoOpsJobListDto:
    """Jobs de la cuenta activa, más recientes primero (opcionalmente de un día/tipo)."""
    scope = await resolve_account_scope_or_default(request, account_id)
    if scope is None:
        return AutoOpsJobListDto(jobs=[], notes=["no_account_scope"])
    repo = SqlAlchemyAutoOpsJobRepository(session)
    if day:
        if not kind:
            raise HTTPException(
                status_code=400, detail="kind requerido cuando se filtra por day"
            )
        jobs = await repo.list_for_day(
            kind=kind, day=day, account_id=scope, limit=limit
        )
        return AutoOpsJobListDto(jobs=[job_to_dto(j) for j in jobs])
    listed = await ListAutoOpsJobs(repo).execute(
        account_id=scope, kind=kind, limit=limit
    )
    return AutoOpsJobListDto(jobs=[job_to_dto(j) for j in listed])


@router.get("/auto/ops-jobs/{job_id}", response_model=AutoOpsJobDto)
async def get_auto_ops_job(
    job_id: str,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    account_id: Annotated[str | None, Depends(get_account_id_header)] = None,
) -> AutoOpsJobDto:
    """Job por id; el de otra cuenta es INDISTINGUIBLE de inexistente (404)."""
    scope = await resolve_account_scope_or_default(request, account_id)
    if scope is None:
        raise _no_scope()
    job = await GetAutoOpsJob(SqlAlchemyAutoOpsJobRepository(session)).execute(
        job_id, account_id=scope
    )
    if job is None:
        raise HTTPException(status_code=404, detail="job_not_found")
    return job_to_dto(job)


def today_utc() -> str:
    return datetime.now(UTC).date().isoformat()
