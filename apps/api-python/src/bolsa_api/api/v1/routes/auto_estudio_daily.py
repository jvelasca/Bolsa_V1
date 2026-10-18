"""API: operativa diaria AUTO por valor (universo ESTUDIO).

Read-only sobre la cola: este router NO calcula nada. Devuelve el parte durable que dejó
el job ``estudio_daily`` del día (``result``), con el estado del job y su progreso.

* Sin job del día ⇒ ``report = null`` (la UI declara «Sin dato todavía», no un cero).
* Universo ``unavailable``/``empty`` ⇒ el job está ``failed`` con ``result`` (el motivo).
* Fail-closed por cuenta: solo se leen jobs de la cuenta activa.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_api.api.dependencies import (
    get_account_id_header,
    get_db_session,
    resolve_account_scope_or_default,
)
from bolsa_api.api.v1.routes.auto_ops_jobs import AutoOpsJobDto, job_to_dto
from bolsa_domain.entities.auto_ops_job import JOB_KIND_ESTUDIO_DAILY
from bolsa_infrastructure.database.repositories.auto_ops_job_repository import (
    SqlAlchemyAutoOpsJobRepository,
)

router = APIRouter()
logger = logging.getLogger(__name__)


class EstudioDailyResponseDto(BaseModel):
    """Parte del día + estado del job que lo produjo (ambos pueden faltar)."""

    model_config = ConfigDict(populate_by_name=True)

    as_of: str = Field(alias="asOf")
    account_id: str | None = Field(default=None, alias="accountId")
    job: AutoOpsJobDto | None = None
    latest_job: AutoOpsJobDto | None = Field(default=None, alias="latestJob")
    report: dict[str, Any] | None = None
    notes: list[str] = Field(default_factory=list)


@router.get("/auto/estudio-daily", response_model=EstudioDailyResponseDto)
async def get_estudio_daily(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    as_of: Annotated[str | None, Query(alias="asOf")] = None,
    account_id: Annotated[str | None, Depends(get_account_id_header)] = None,
) -> EstudioDailyResponseDto:
    """Operativa diaria por valor de ``asOf`` (por defecto hoy UTC) para la cuenta activa."""
    day = (as_of or datetime.now(UTC).date().isoformat())[:10]
    scope = await resolve_account_scope_or_default(request, account_id)
    if scope is None:
        return EstudioDailyResponseDto(
            as_of=day, account_id=None, notes=["no_account_scope"]
        )

    repo = SqlAlchemyAutoOpsJobRepository(session)
    jobs = await repo.list_for_day(
        kind=JOB_KIND_ESTUDIO_DAILY, day=day, account_id=scope, limit=10
    )
    latest = await repo.list_for_account(
        account_id=scope, kind=JOB_KIND_ESTUDIO_DAILY, limit=1
    )
    job = jobs[0] if jobs else None
    latest_job = latest[0] if latest else None

    notes: list[str] = []
    report: dict[str, Any] | None = None
    if job is None:
        notes.append("no_job_for_day")
    elif job.result:
        report = dict(job.result)
    else:
        notes.append("job_without_result")
    if job is not None and job.status == "failed" and job.error:
        notes.append(f"job_failed: {job.error}")

    return EstudioDailyResponseDto(
        as_of=day,
        account_id=scope,
        job=job_to_dto(job) if job is not None else None,
        latest_job=job_to_dto(latest_job) if latest_job is not None else None,
        report=report,
        notes=notes,
    )
