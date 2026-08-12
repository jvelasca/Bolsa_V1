"""API: alertas disparadas por señal."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_analytics.signals.preset_catalog import is_valid_preset_key
from bolsa_analytics.signals.strategy import SignalEventV1
from bolsa_api.api.dependencies import (
    get_create_signal_alert_use_case,
    get_db_session,
    get_delete_signal_alert_use_case,
    get_evaluate_signal_alerts_use_case,
    get_list_signal_alerts_use_case,
    get_reset_signal_alert_use_case,
)
from bolsa_api.schemas.signal_alerts import (
    AlertChannelDispatchDto,
    CreateSignalAlertSubscriptionRequestDto,
    EvaluateSignalAlertsResponseDto,
    SignalAlertSubscriptionDto,
    SignalAlertSubscriptionResponseDto,
    SignalAlertSubscriptionsResponseDto,
    TriggeredSignalAlertDto,
)
from bolsa_api.schemas.signals_evaluate import SignalEventV1Dto
from bolsa_application.signal_alerts import (
    CreateSignalAlertSubscription,
    DeleteSignalAlertSubscription,
    EvaluateSignalAlertSubscriptions,
    ListSignalAlertSubscriptions,
    ResetSignalAlertDedupe,
)
from bolsa_infrastructure.alerts.alert_channels import AlertChannelDispatchResult
from bolsa_infrastructure.database.repositories.signal_alert_repository import (
    SignalAlertSubscriptionRecord,
)

router = APIRouter()


def _subscription_dto(item: SignalAlertSubscriptionRecord) -> SignalAlertSubscriptionDto:
    return SignalAlertSubscriptionDto(
        id=item.id,
        instrument_id=item.instrument_id,
        symbol=item.symbol,
        strategy_definition_id=item.strategy_definition_id,
        preset_key=item.preset_key,
        timeframe=item.timeframe,
        signal_kinds=item.signal_kinds,
        channels=item.channels,
        webhook_url=item.webhook_url,
        email_to=item.email_to,
        is_active=item.is_active,
        last_triggered_at=item.last_triggered_at,
        last_bar_timestamp=item.last_bar_timestamp,
        last_signal_kind=item.last_signal_kind,
        last_signal_price=item.last_signal_price,
        note=item.note,
        created_at=item.created_at,
    )


def _dispatch_dto(item: AlertChannelDispatchResult) -> AlertChannelDispatchDto:
    return AlertChannelDispatchDto(
        subscription_id=item.subscription_id,
        channel=item.channel,
        ok=item.ok,
        error=item.error,
    )


def _signal_dto(event: SignalEventV1) -> SignalEventV1Dto:
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


@router.get("/signal-alerts", response_model=SignalAlertSubscriptionsResponseDto)
async def list_signal_alerts(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    active_only: Annotated[bool, Query(alias="activeOnly")] = False,
) -> SignalAlertSubscriptionsResponseDto:
    use_case: ListSignalAlertSubscriptions = get_list_signal_alerts_use_case(session)
    items = await use_case.execute(active_only=active_only)
    return SignalAlertSubscriptionsResponseDto(data=[_subscription_dto(item) for item in items])


@router.post("/signal-alerts", response_model=SignalAlertSubscriptionResponseDto, status_code=201)
async def create_signal_alert(
    body: CreateSignalAlertSubscriptionRequestDto,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> SignalAlertSubscriptionResponseDto:
    if body.preset_key is not None and not is_valid_preset_key(body.preset_key):
        raise HTTPException(status_code=400, detail="Invalid presetKey")
    if body.signal_kinds is not None:
        allowed = {"entry_long", "entry_short", "exit", "watch"}
        if not all(kind in allowed for kind in body.signal_kinds):
            raise HTTPException(status_code=400, detail="Invalid signalKinds")
    if body.channels is not None:
        allowed_channels = {"toast", "webhook", "email"}
        if not all(channel in allowed_channels for channel in body.channels):
            raise HTTPException(status_code=400, detail="Invalid channels")

    use_case: CreateSignalAlertSubscription = get_create_signal_alert_use_case(session)
    try:
        item = await use_case.execute(
            instrument_id=body.instrument_id,
            strategy_definition_id=body.strategy_definition_id,
            preset_key=body.preset_key,  # type: ignore[arg-type]
            timeframe=body.timeframe,
            signal_kinds=body.signal_kinds,
            channels=body.channels,
            webhook_url=body.webhook_url,
            email_to=body.email_to,
            note=body.note,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return SignalAlertSubscriptionResponseDto(data=_subscription_dto(item))


@router.delete("/signal-alerts/{subscription_id}", status_code=204)
async def delete_signal_alert(
    subscription_id: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> None:
    use_case: DeleteSignalAlertSubscription = get_delete_signal_alert_use_case(session)
    try:
        await use_case.execute(subscription_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/signal-alerts/{subscription_id}/reset-dedupe",
    response_model=SignalAlertSubscriptionResponseDto,
)
async def reset_signal_alert_dedupe(
    subscription_id: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> SignalAlertSubscriptionResponseDto:
    use_case: ResetSignalAlertDedupe = get_reset_signal_alert_use_case(session)
    try:
        item = await use_case.execute(subscription_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return SignalAlertSubscriptionResponseDto(data=_subscription_dto(item))


@router.post("/signal-alerts/evaluate", response_model=EvaluateSignalAlertsResponseDto)
async def evaluate_signal_alerts(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> EvaluateSignalAlertsResponseDto:
    use_case: EvaluateSignalAlertSubscriptions = get_evaluate_signal_alerts_use_case(session)
    result = await use_case.execute()
    return EvaluateSignalAlertsResponseDto(
        data=[
            TriggeredSignalAlertDto(
                subscription=_subscription_dto(item.subscription),
                signal=_signal_dto(item.signal),
                dispatches=[_dispatch_dto(dispatch) for dispatch in item.dispatches],
            )
            for item in result.triggered
        ],
        dispatches=[_dispatch_dto(dispatch) for dispatch in result.dispatches],
    )
