"""API: datos de mercado (proveedores, FX)."""

from datetime import UTC, datetime
from typing import Annotated

from bolsa_application.market_providers import (
    ProviderConfigError,
    UnknownProviderError,
    summarize_provider_health,
)
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_api.api.dependencies import (
    get_db_session,
    get_fx_rate_use_case,
    get_market_status_use_case,
    get_provider_check_policy_use_case,
    get_test_provider_connection_use_case,
    get_update_market_provider_use_case,
)
from bolsa_api.schemas.extra_mappers import to_market_provider_dto
from bolsa_api.schemas.market import (
    FxRateDto,
    FxRateResponseDto,
    MarketProviderResponseDto,
    MarketProvidersResponseDto,
    ProviderHealthEntryDto,
    ProviderHealthSummaryDto,
    ProviderHealthSummaryResponseDto,
    ProviderTestResponseDto,
    ProviderTestResultDto,
    UpdateMarketProviderDto,
)

router = APIRouter()


@router.get("/market/providers", response_model=MarketProvidersResponseDto)
async def get_market_providers(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    refresh: Annotated[bool, Query(description="Ignora la caché de configuración")] = False,
) -> MarketProvidersResponseDto:
    """Configuración efectiva y estado medido de cada proveedor del registro."""
    use_case = await get_market_status_use_case(session, refresh=refresh)
    providers = await use_case.execute()
    return MarketProvidersResponseDto(
        data=[to_market_provider_dto(provider) for provider in providers],
    )


async def _provider_health_summary(
    session: AsyncSession,
    *,
    probing: bool,
) -> ProviderHealthSummaryDto:
    """Veredicto único construido SOLO con lo persistido (sin tráfico a proveedores).

    Medir es competencia del comprobador (bucle o «Comprobar ahora»): un GET que mide
    tiene dos fuentes de verdad y hace depender la barra de una petición real a Yahoo.
    """
    policy = await get_provider_check_policy_use_case(session).execute()
    status_use_case = await get_market_status_use_case(session, refresh=True, live=False)
    summary = summarize_provider_health(await status_use_case.execute(), policy=policy)
    return ProviderHealthSummaryDto(
        status=summary.status,
        ok=summary.ok,
        measured_at=summary.measured_at,
        probing=probing,
        auto_check_enabled=summary.auto_check_enabled,
        check_interval_seconds=summary.check_interval_seconds,
        next_check_at=summary.next_check_at,
        providers=[
            ProviderHealthEntryDto(
                id=entry.id,
                label=entry.label,
                enabled=entry.enabled,
                healthy=entry.healthy,
                verified=entry.verified,
                message=entry.message,
                last_check_at=entry.last_check_at,
                last_check_ok=entry.last_check_ok,
            )
            for entry in summary.providers
        ],
    )


@router.get("/market/providers/health", response_model=ProviderHealthSummaryResponseDto)
async def get_market_providers_health(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ProviderHealthSummaryResponseDto:
    """Veredicto único para el icono de servidores de la barra de estado.

    Si la comprobación automática está ON y el dato venció, se programa una sonda sin
    bloquear esta respuesta: el campo ``probing`` lo declara y la siguiente consulta ya
    devuelve la medida. Nunca se inventa un estado: sin medición es ``unverified``.
    """
    monitor = getattr(request.app.state, "provider_health", None)
    probing = bool(monitor.ensure_fresh()) if monitor is not None else False
    return ProviderHealthSummaryResponseDto(
        data=await _provider_health_summary(session, probing=probing)
    )


@router.post("/market/providers/health/check", response_model=ProviderHealthSummaryResponseDto)
async def check_market_providers_health(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ProviderHealthSummaryResponseDto:
    """«Comprobar ahora»: mide los proveedores habilitados y persiste el resultado.

    Mide aunque la comprobación automática esté OFF: apagar la cadencia no debe impedir
    un diagnóstico puntual. Si el comprobador no está disponible en este proceso, se
    responde 503 en vez de devolver un veredicto que no se acaba de medir.
    """
    monitor = getattr(request.app.state, "provider_health", None)
    if monitor is None:
        raise HTTPException(
            status_code=503,
            detail="Comprobador de proveedores no disponible en este proceso",
        )
    await monitor.probe_if_due(force=True)
    return ProviderHealthSummaryResponseDto(
        data=await _provider_health_summary(session, probing=monitor.probing)
    )


@router.patch("/market/providers/{provider_id}", response_model=MarketProviderResponseDto)
async def update_market_provider(
    provider_id: str,
    body: UpdateMarketProviderDto,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> MarketProviderResponseDto:
    """Actualiza solo los campos declarados del proveedor."""
    declared = body.model_fields_set
    try:
        updated = await get_update_market_provider_use_case(session).execute(
            provider_id,
            enabled=body.enabled if "enabled" in declared else None,
            priority=body.priority if "priority" in declared else None,
            min_interval_seconds=(
                body.min_interval_seconds if "min_interval_seconds" in declared else None
            ),
            base_url=body.base_url,
            base_url_provided="base_url" in declared,
        )
    except UnknownProviderError as exc:
        raise HTTPException(status_code=404, detail=f"Proveedor desconocido: {exc}") from exc
    except ProviderConfigError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    status_use_case = await get_market_status_use_case(session, refresh=True)
    statuses = {provider.id: provider for provider in await status_use_case.execute()}
    status = statuses.get(updated.id)
    if status is None:  # pragma: no cover — el registro y la BD comparten IDs
        raise HTTPException(status_code=500, detail="Proveedor sin estado calculable")
    return MarketProviderResponseDto(data=to_market_provider_dto(status))


@router.post("/market/providers/{provider_id}/test", response_model=ProviderTestResponseDto)
async def test_market_provider(
    provider_id: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ProviderTestResponseDto:
    """Verifica el proveedor con una llamada real y persiste el resultado."""
    try:
        result = await get_test_provider_connection_use_case(session).execute(provider_id)
    except UnknownProviderError as exc:
        raise HTTPException(status_code=404, detail=f"Proveedor desconocido: {exc}") from exc
    return ProviderTestResponseDto(
        data=ProviderTestResultDto(
            provider_id=provider_id,
            ok=result.ok,
            message=result.message,
            checked_at=datetime.now(UTC).isoformat(),
        )
    )


@router.get("/market/fx", response_model=FxRateResponseDto)
async def get_fx_rate(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    from_currency: Annotated[str, Query(alias="from", min_length=3, max_length=3)],
    to_currency: Annotated[str, Query(alias="to", min_length=3, max_length=3)],
) -> FxRateResponseDto:
    _ = session
    try:
        fx = await get_fx_rate_use_case().execute(from_currency, to_currency)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return FxRateResponseDto(
        data=FxRateDto(
            from_currency=fx.from_currency,
            to_currency=fx.to_currency,
            rate=fx.rate,
            yahoo_symbol=fx.yahoo_symbol,
            timestamp=fx.timestamp,
            source=fx.source,
        ),
    )


#: ``baseUrl`` omitido en el PATCH se distingue de ``null`` con ``model_fields_set``.
