"""API: eventos de plataforma."""

from typing import Annotated

from bolsa_application.platform_events import ListPlatformEvents
from bolsa_domain.entities.platform_event import PlatformEventRecord
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_api.api.dependencies import get_db_session, get_list_platform_events_use_case
from bolsa_api.auth.request_principal import get_request_principal
from bolsa_api.schemas.platform_events import PlatformEventDto, PlatformEventsListResponseDto

router = APIRouter()


def _to_dto(record: PlatformEventRecord) -> PlatformEventDto:
    return PlatformEventDto(
        id=record.id,
        type=record.type,
        timestamp=record.created_at,
        payload=record.payload,
        correlation_id=record.correlation_id,
    )


@router.get("/platform-events", response_model=PlatformEventsListResponseDto)
async def list_platform_events(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    limit: int = Query(default=50, ge=1, le=200),
    type: str | None = Query(default=None, alias="type"),
    correlation_id: str | None = Query(default=None, alias="correlationId"),
) -> PlatformEventsListResponseDto:
    principal = get_request_principal(request)
    use_case: ListPlatformEvents = get_list_platform_events_use_case(session)
    records = await use_case.execute(
        limit=limit,
        event_type=type,
        correlation_id=correlation_id,
        owner_user_id=principal,
    )
    return PlatformEventsListResponseDto(data=[_to_dto(record) for record in records])
