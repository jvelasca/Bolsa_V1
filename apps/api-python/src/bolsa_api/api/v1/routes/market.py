"""API: datos de mercado (OHLCV, búsqueda)."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_api.api.dependencies import (
    get_db_session,
    get_fx_rate_use_case,
    get_market_status_use_case,
)
from bolsa_api.schemas.extra_mappers import to_market_provider_dto
from bolsa_api.schemas.market import FxRateDto, FxRateResponseDto, MarketProvidersResponseDto

router = APIRouter()


@router.get("/market/providers", response_model=MarketProvidersResponseDto)
async def get_market_providers(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> MarketProvidersResponseDto:
    _ = session
    providers = await get_market_status_use_case().execute()
    return MarketProvidersResponseDto(
        data=[to_market_provider_dto(provider) for provider in providers],
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