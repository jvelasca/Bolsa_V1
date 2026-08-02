from typing import Annotated

from bolsa_application.alerts import (
    CreatePriceAlert,
    DeletePriceAlert,
    ListPriceAlerts,
    ReactivatePriceAlert,
)
from bolsa_infrastructure.database.repositories.alert_repository import (
    PriceAlertRecord,
    SqlAlchemyAlertRepository,
)
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_api.api.dependencies import (
    get_alert_repository,
    get_db_session,
    get_evaluate_alerts_use_case,
)
from bolsa_api.schemas.alerts import (
    CreatePriceAlertRequestDto,
    EvaluateAlertsResponseDto,
    PriceAlertDto,
    PriceAlertResponseDto,
    PriceAlertsResponseDto,
)

router = APIRouter()


def _to_dto(item: PriceAlertRecord) -> PriceAlertDto:
    return PriceAlertDto(
        id=item.id,
        instrument_id=item.instrument_id,
        symbol=item.symbol,
        condition=item.condition,
        price_source=item.price_source,
        target_price=item.target_price,
        is_active=item.is_active,
        triggered_at=item.triggered_at,
        triggered_price=item.triggered_price,
        note=item.note,
        created_at=item.created_at,
    )


@router.get("/alerts", response_model=PriceAlertsResponseDto)
async def list_alerts(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    active_only: Annotated[bool, Query(alias="activeOnly")] = False,
) -> PriceAlertsResponseDto:
    repo = get_alert_repository(session)
    items = await ListPriceAlerts(repo).execute(active_only=active_only)
    return PriceAlertsResponseDto(data=[_to_dto(item) for item in items])


@router.post("/alerts", response_model=PriceAlertResponseDto, status_code=201)
async def create_alert(
    body: CreatePriceAlertRequestDto,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> PriceAlertResponseDto:
    if body.condition not in ("above", "below"):
        raise HTTPException(status_code=400, detail="condition debe ser 'above' o 'below'")
    if body.price_source not in ("daily_close", "xtb_last"):
        raise HTTPException(
            status_code=400,
            detail="priceSource debe ser 'daily_close' o 'xtb_last'",
        )
    repo = get_alert_repository(session)
    try:
        alert = await CreatePriceAlert(repo).execute(
            instrument_id=body.instrument_id,
            condition=body.condition,
            target_price=body.target_price,
            price_source=body.price_source,
            note=body.note,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return PriceAlertResponseDto(data=_to_dto(alert))


@router.delete("/alerts/{alert_id}", status_code=204)
async def delete_alert(
    alert_id: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> None:
    repo: SqlAlchemyAlertRepository = get_alert_repository(session)
    try:
        await DeletePriceAlert(repo).execute(alert_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/alerts/{alert_id}/reactivate", response_model=PriceAlertResponseDto)
async def reactivate_alert(
    alert_id: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> PriceAlertResponseDto:
    repo = get_alert_repository(session)
    try:
        alert = await ReactivatePriceAlert(repo).execute(alert_id)
    except ValueError as exc:
        status = 404 if "no encontrada" in str(exc).lower() else 400
        raise HTTPException(status_code=status, detail=str(exc)) from exc
    return PriceAlertResponseDto(data=_to_dto(alert))


@router.post("/alerts/evaluate", response_model=EvaluateAlertsResponseDto)
async def evaluate_alerts(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> EvaluateAlertsResponseDto:
    result = await get_evaluate_alerts_use_case(session).execute()
    return EvaluateAlertsResponseDto(data=[_to_dto(item) for item in result.triggered])
