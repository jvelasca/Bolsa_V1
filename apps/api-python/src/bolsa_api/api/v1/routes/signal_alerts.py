"""API: alertas disparadas por señal (v111: ownership por cuenta + OUTBOX)."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_analytics.signals.preset_catalog import is_valid_preset_key
from bolsa_api.api.dependencies import (
    get_account_id_header,
    get_create_signal_alert_use_case,
    get_db_session,
    get_delete_signal_alert_use_case,
    get_evaluate_signal_alerts_use_case,
    get_list_signal_alerts_use_case,
    get_process_alert_deliveries_use_case,
    get_reset_signal_alert_use_case,
    resolve_account_scope_or_default,
)
from bolsa_api.schemas.signal_alerts import (
    AlertChannelDispatchDto,
    CreateSignalAlertSubscriptionRequestDto,
    EvaluateSignalAlertsResponseDto,
    ProcessAlertDeliveriesResponseDto,
    SignalAlertSubscriptionDto,
    SignalAlertSubscriptionResponseDto,
    SignalAlertSubscriptionsResponseDto,
    TriggeredSignalAlertDto,
)
from bolsa_api.schemas.signals_evaluate import to_signal_event_v1_dto
from bolsa_application.signal_alerts import (
    CreateSignalAlertSubscription,
    DeleteSignalAlertSubscription,
    EvaluateSignalAlertSubscriptions,
    ListSignalAlertSubscriptions,
    ProcessAlertDeliveries,
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
        account_id=item.account_id,
    )


def _dispatch_dto(item: AlertChannelDispatchResult) -> AlertChannelDispatchDto:
    return AlertChannelDispatchDto(
        subscription_id=item.subscription_id,
        channel=item.channel,
        ok=item.ok,
        error=item.error,
        attempt=item.attempt,
        will_retry=item.will_retry,
        delivery_id=item.delivery_id,
    )


async def _require_scope(request: Request, account_id: str | None) -> str | None:
    """Ámbito por cuenta (fail-closed). Devuelve ``None`` si el principal no tiene cuenta."""
    return await resolve_account_scope_or_default(request, account_id)


@router.get("/signal-alerts", response_model=SignalAlertSubscriptionsResponseDto)
async def list_signal_alerts(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    active_only: Annotated[bool, Query(alias="activeOnly")] = False,
    account_id: Annotated[str | None, Depends(get_account_id_header)] = None,
) -> SignalAlertSubscriptionsResponseDto:
    scope = await _require_scope(request, account_id)
    if scope is None:
        return SignalAlertSubscriptionsResponseDto(data=[])
    use_case: ListSignalAlertSubscriptions = get_list_signal_alerts_use_case(session)
    items = await use_case.execute(account_id=scope, active_only=active_only)
    return SignalAlertSubscriptionsResponseDto(data=[_subscription_dto(item) for item in items])


@router.post("/signal-alerts", response_model=SignalAlertSubscriptionResponseDto, status_code=201)
async def create_signal_alert(
    request: Request,
    body: CreateSignalAlertSubscriptionRequestDto,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    account_id: Annotated[str | None, Depends(get_account_id_header)] = None,
) -> SignalAlertSubscriptionResponseDto:
    scope = await _require_scope(request, account_id)
    if scope is None:
        raise HTTPException(
            status_code=400,
            detail="Las alertas de señal requieren una cuenta operativa del principal",
        )
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
            account_id=scope,
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
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    account_id: Annotated[str | None, Depends(get_account_id_header)] = None,
) -> None:
    scope = await _require_scope(request, account_id)
    if scope is None:
        raise HTTPException(status_code=404, detail="Suscripción no encontrada")
    use_case: DeleteSignalAlertSubscription = get_delete_signal_alert_use_case(session)
    try:
        await use_case.execute(subscription_id, account_id=scope)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/signal-alerts/{subscription_id}/reset-dedupe",
    response_model=SignalAlertSubscriptionResponseDto,
)
async def reset_signal_alert_dedupe(
    subscription_id: str,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    account_id: Annotated[str | None, Depends(get_account_id_header)] = None,
) -> SignalAlertSubscriptionResponseDto:
    scope = await _require_scope(request, account_id)
    if scope is None:
        raise HTTPException(status_code=404, detail="Suscripción no encontrada")
    use_case: ResetSignalAlertDedupe = get_reset_signal_alert_use_case(session)
    try:
        item = await use_case.execute(subscription_id, account_id=scope)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return SignalAlertSubscriptionResponseDto(data=_subscription_dto(item))


@router.post("/signal-alerts/evaluate", response_model=EvaluateSignalAlertsResponseDto)
async def evaluate_signal_alerts(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    account_id: Annotated[str | None, Depends(get_account_id_header)] = None,
) -> EvaluateSignalAlertsResponseDto:
    scope = await _require_scope(request, account_id)
    if scope is None:
        return EvaluateSignalAlertsResponseDto(data=[], dispatches=[])
    use_case: EvaluateSignalAlertSubscriptions = get_evaluate_signal_alerts_use_case(session)
    result = await use_case.execute(account_id=scope)
    return EvaluateSignalAlertsResponseDto(
        data=[
            TriggeredSignalAlertDto(
                subscription=_subscription_dto(item.subscription),
                signal=to_signal_event_v1_dto(item.signal),
                dispatches=[_dispatch_dto(dispatch) for dispatch in item.dispatches],
            )
            for item in result.triggered
        ],
        dispatches=[_dispatch_dto(dispatch) for dispatch in result.dispatches],
    )


@router.post(
    "/signal-alerts/deliveries/process",
    response_model=ProcessAlertDeliveriesResponseDto,
)
async def process_signal_alert_deliveries(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> ProcessAlertDeliveriesResponseDto:
    """Worker del OUTBOX: reintenta las entregas vencidas (PENDING/RETRYABLE_FAILED).

    Idempotente y sin ámbito de cuenta: reclama CUALQUIER entrega vencida (el dueño viaja en la
    fila) para que un fallo de SMTP/webhook no se pierda. Pensado para cron/scheduler.
    """
    use_case: ProcessAlertDeliveries = get_process_alert_deliveries_use_case(session)
    dispatches = await use_case.execute(limit=limit)
    return ProcessAlertDeliveriesResponseDto(
        dispatches=[_dispatch_dto(dispatch) for dispatch in dispatches]
    )
