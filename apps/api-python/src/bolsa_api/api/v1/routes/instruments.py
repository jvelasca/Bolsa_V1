"""Rutas HTTP de instrumentos — catálogo, OHLCV, sync, búsqueda e import.

Endpoints bajo /api/instruments*. Los DTOs Pydantic viven en bolsa_api.schemas.
Los casos de uso se inyectan vía bolsa_api.api.dependencies.
"""
from typing import Annotated

from bolsa_domain.value_objects.timeframe import TimeFrame
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_api.api.dependencies import (
    get_db_session,
    get_delete_instrument_use_case,
    get_import_instrument_use_case,
    get_instrument_data_status_use_case,
    get_instrument_db_inventory_use_case,
    get_instrument_detail_use_case,
    get_instrument_fundamentals_use_case,
    get_instrument_indicators_use_case,
    get_instrument_profile_use_case,
    get_instrument_quotes_use_case,
    get_instrument_removal_preview_use_case,
    get_instrument_repository,
    get_list_instruments_use_case,
    get_live_quote_use_case,
    get_live_quotes_use_case,
    get_ohlcv_bars_use_case,
    get_search_instruments_use_case,
    get_sync_instrument_use_case,
    get_sync_scheduler_repository,
    get_validate_instrument_xtb_use_case,
)
from bolsa_api.schemas.composite_card import (
    CompositeChipDto,
    CompositeChipListResponseDto,
    QueryInstrumentCompositeDto,
)
from bolsa_api.schemas.extra_mappers import to_live_quote_dto, to_sync_result_dto
from bolsa_api.schemas.fundamental_card import (
    FundamentalCardDto,
    FundamentalCardResponseDto,
    FundamentalChipDto,
    FundamentalChipListResponseDto,
    QueryInstrumentFundamentalsDto,
)
from bolsa_api.schemas.instrument_lifecycle import (
    InstrumentRemovalPreviewResponseDto,
)
from bolsa_api.schemas.instruments import (
    ExternalInstrumentSearchHitDto,
    ImportInstrumentMetaDto,
    ImportInstrumentRequestDto,
    ImportInstrumentResponseDto,
    IndicatorsResponseDto,
    InstrumentDataStatusResponseDto,
    InstrumentDbInventoryResponseDto,
    InstrumentDetailResponseDto,
    InstrumentListResponseDto,
    InstrumentProfileResponseDto,
    InstrumentQuotesRequestDto,
    InstrumentSearchResponseDto,
    InstrumentXtbValidationResponseDto,
    OhlcvResponseDto,
)
from bolsa_api.schemas.lifecycle_mappers import to_removal_preview_dto
from bolsa_api.schemas.mappers import (
    to_data_status_dto,
    to_db_inventory_dto,
    to_indicators_dto,
    to_instrument_detail_dto,
    to_instrument_dto,
    to_ohlcv_dto,
    to_xtb_validation_dto,
)
from bolsa_api.schemas.market import LiveQuoteEnvelopeDto, LiveQuoteListResponseDto, SyncResponseDto

router = APIRouter()


def _parse_timeframe(value: str) -> TimeFrame:
    try:
        return TimeFrame(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid timeframe: {value}") from exc


class SyncRequestDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)

    years_back: int | None = Field(alias="yearsBack", default=5, ge=1, le=30)


@router.get("/instruments", response_model=InstrumentListResponseDto)
async def list_instruments(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> InstrumentListResponseDto:
    items = await get_list_instruments_use_case(session).execute()
    return InstrumentListResponseDto(data=[to_instrument_dto(item) for item in items])


@router.get("/instruments/search", response_model=InstrumentSearchResponseDto)
async def search_instruments(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    q: Annotated[str, Query(min_length=1, max_length=64)],
) -> InstrumentSearchResponseDto:
    result = await get_search_instruments_use_case(session).execute(q)
    return InstrumentSearchResponseDto(
        catalog=[to_instrument_dto(item) for item in result.catalog],
        external=[
            ExternalInstrumentSearchHitDto(
                symbol=hit.symbol,
                yahoo_symbol=hit.yahoo_symbol,
                name=hit.name,
                exchange=hit.exchange,
                currency=hit.currency,
                isin=hit.isin,
            )
            for hit in result.external
        ],
    )


@router.post("/instruments/import", response_model=ImportInstrumentResponseDto)
async def import_instrument(
    body: ImportInstrumentRequestDto,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ImportInstrumentResponseDto:
    try:
        result = await get_import_instrument_use_case(session).execute(
            yahoo_symbol=body.yahoo_symbol,
            symbol=body.symbol,
            name=body.name,
            exchange=body.exchange,
            currency=body.currency,
            sync=body.sync,
            years_back=body.years_back,
            isin=body.isin,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"No se pudo importar el instrumento: {exc}",
        ) from exc

    if result is None:
        raise HTTPException(status_code=500, detail="No se pudo importar el instrumento")

    sync_dto = to_sync_result_dto(result.sync) if result.sync else None
    return ImportInstrumentResponseDto(
        data=to_instrument_dto(result.instrument),
        meta=ImportInstrumentMetaDto(created=result.created, sync=sync_dto),
    )


@router.post("/instruments/quotes", response_model=InstrumentListResponseDto)
async def get_instrument_quotes(
    body: InstrumentQuotesRequestDto,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> InstrumentListResponseDto:
    items = await get_instrument_quotes_use_case(session).execute(body.ids)
    return InstrumentListResponseDto(data=[to_instrument_dto(item) for item in items])


@router.post(
    "/instruments/fundamentals/query",
    response_model=FundamentalChipListResponseDto,
)
async def query_instrument_fundamentals(
    body: QueryInstrumentFundamentalsDto,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> FundamentalChipListResponseDto:
    """Batch chips FA para Universo Lista (PR3). Sin IA."""
    chips = await get_instrument_fundamentals_use_case(session).execute_chips(
        body.instrument_ids,
    )
    return FundamentalChipListResponseDto(
        data=[FundamentalChipDto.model_validate(c) for c in chips],
    )


@router.post(
    "/instruments/composite/query",
    response_model=CompositeChipListResponseDto,
)
async def query_instrument_composite(
    body: QueryInstrumentCompositeDto,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> CompositeChipListResponseDto:
    """Batch chips Composite (TA+FUND) para hub Instrumentos I2. Sin IA."""
    from bolsa_api.api.dependencies import get_instrument_composite_use_case

    chips = await get_instrument_composite_use_case(session).execute_chips(
        body.instrument_ids,
        horizon=body.horizon,
        regime=body.regime,
    )
    return CompositeChipListResponseDto(
        data=[CompositeChipDto.model_validate(c) for c in chips],
    )


class FundamentalScreenerUniverseBody(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    list_id: str | None = Field(default=None, alias="listId")
    instrument_ids: list[str] | None = Field(default=None, alias="instrumentIds")


class FundamentalScreenerPersistBody(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    list_id: str | None = Field(default=None, alias="listId")
    name: str | None = None


class FundamentalScreenerRunBody(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    universe: FundamentalScreenerUniverseBody
    fundamental_gate: dict = Field(alias="fundamentalGate")
    refresh_stale: bool = Field(default=True, alias="refreshStale")
    max_results: int = Field(default=100, alias="maxResults", ge=1, le=500)
    persist: FundamentalScreenerPersistBody | None = None


@router.post("/instruments/fundamentals/screener")
async def run_fundamental_screener(
    body: FundamentalScreenerRunBody,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict:
    """
    F4 — Screener FA: universo × gate → lista blanca (sin timing técnico).
    Opcional: persistir hits en lista snapshot.
    """
    from bolsa_api.api.dependencies import get_run_fundamental_screener_use_case

    payload = {
        "universe": {
            "listId": body.universe.list_id,
            "instrumentIds": body.universe.instrument_ids,
        },
        "fundamentalGate": body.fundamental_gate,
        "refreshStale": body.refresh_stale,
        "maxResults": body.max_results,
        "persist": (
            None
            if body.persist is None
            else {"listId": body.persist.list_id, "name": body.persist.name}
        ),
    }
    try:
        result = await get_run_fundamental_screener_use_case(session).execute(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"data": result}


@router.post("/instruments/live-quotes", response_model=LiveQuoteListResponseDto)
async def get_instrument_live_quotes(
    body: InstrumentQuotesRequestDto,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> LiveQuoteListResponseDto:
    quotes = await get_live_quotes_use_case(session).execute(body.ids)
    return LiveQuoteListResponseDto(data=[to_live_quote_dto(quote) for quote in quotes])


@router.get("/instruments/{instrument_id}", response_model=InstrumentDetailResponseDto)
async def get_instrument(
    instrument_id: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> InstrumentDetailResponseDto:
    detail = await get_instrument_detail_use_case(session).execute(instrument_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Instrument not found")
    return to_instrument_detail_dto(detail)


@router.get(
    "/instruments/{instrument_id}/db-inventory",
    response_model=InstrumentDbInventoryResponseDto,
)
async def get_instrument_db_inventory(
    instrument_id: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> InstrumentDbInventoryResponseDto:
    inventory = await get_instrument_db_inventory_use_case(session).execute(instrument_id)
    if inventory is None:
        raise HTTPException(status_code=404, detail="Instrument not found")
    return InstrumentDbInventoryResponseDto(data=to_db_inventory_dto(inventory))


@router.post(
    "/instruments/{instrument_id}/validate-xtb",
    response_model=InstrumentXtbValidationResponseDto,
)
async def validate_instrument_xtb(
    instrument_id: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> InstrumentXtbValidationResponseDto:
    validation = await get_validate_instrument_xtb_use_case(session).execute(instrument_id)
    if validation is None:
        raise HTTPException(status_code=404, detail="Instrument not found")
    return InstrumentXtbValidationResponseDto(data=to_xtb_validation_dto(validation))


@router.get("/instruments/{instrument_id}/profile", response_model=InstrumentProfileResponseDto)
async def get_instrument_profile(
    instrument_id: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> InstrumentProfileResponseDto:
    detail = await get_instrument_detail_use_case(session).execute(instrument_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Instrument not found")
    profile = await get_instrument_profile_use_case(session).execute(instrument_id)
    return InstrumentProfileResponseDto(data=profile)


@router.get(
    "/instruments/{instrument_id}/fundamentals",
    response_model=FundamentalCardResponseDto,
)
async def get_instrument_fundamentals(
    instrument_id: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    as_of: Annotated[str | None, Query(alias="asOf")] = None,
) -> FundamentalCardResponseDto:
    """F1 — tarjeta FA determinista (Score_FUND + facts + confidence). Sin IA.

    ``asOf`` (YYYY-MM-DD): corte DÍA D. Si el snapshot Yahoo es posterior a D,
    scores/ratios se bloquean (sin look-ahead).
    """
    card = await get_instrument_fundamentals_use_case(session).execute(
        instrument_id,
        as_of=as_of,
    )
    if card is None:
        raise HTTPException(status_code=404, detail="Instrument not found")
    return FundamentalCardResponseDto(data=FundamentalCardDto.model_validate(card))


@router.get("/instruments/{instrument_id}/composite")
async def get_instrument_composite(
    instrument_id: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    horizon: Annotated[str, Query()] = "swing",
    regime: Annotated[str, Query()] = "neutral",
    as_of: Annotated[str | None, Query(alias="asOf")] = None,
) -> dict:
    """
    F3 — Composite Investment Score (Monitor).
    Piernas TA+FUND+régimen+liquidez+perfil; portfolio constraints stub.
    ``paperDUnlocked=true`` documenta ranking auditable (no despliega paper).
    ``asOf``: TA via OHLCV ≤ D; FA bloqueada si snapshot > D.
    """
    from bolsa_api.api.dependencies import get_instrument_composite_use_case

    card = await get_instrument_composite_use_case(session).execute(
        instrument_id,
        horizon=horizon,
        regime=regime,
        as_of=as_of,
    )
    if card is None:
        raise HTTPException(status_code=404, detail="Instrument not found")
    return {"data": card}


@router.get("/instruments/{instrument_id}/filings")
async def list_instrument_filings(
    instrument_id: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict:
    """F2b lite — lista metadatos de filings en disco (no toca Score_FUND)."""
    from bolsa_application.instrument_filings import InstrumentFilingsService

    result = await InstrumentFilingsService(get_instrument_repository(session)).list(instrument_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Instrument not found")
    return result


@router.post("/instruments/{instrument_id}/filings")
async def upload_instrument_filing(
    instrument_id: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    file: Annotated[UploadFile, File(...)],
    kind: Annotated[str, Form()] = "10-K",
) -> dict:
    """F2b lite — sube PDF o TXT 10-K/10-Q. Extracto en disco; sin RAG."""
    from bolsa_application.instrument_filings import InstrumentFilingsService
    from bolsa_market.filing_store import ALLOWED_KINDS

    if kind not in ALLOWED_KINDS:
        raise HTTPException(status_code=400, detail=f"kind inválido; use {sorted(ALLOWED_KINDS)}")
    content = await file.read()
    try:
        result = await InstrumentFilingsService(get_instrument_repository(session)).upload(
            instrument_id,
            kind=kind,
            original_name=file.filename or "filing.bin",
            content_type=file.content_type or "application/octet-stream",
            content=content,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="Instrument not found")
    return result


@router.post("/instruments/{instrument_id}/filings/sec-fetch")
async def fetch_instrument_filing_from_sec(
    instrument_id: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    kind: Annotated[str, Query()] = "10-K",
) -> dict:
    """
    F2b+ — descarga el último 10-K/10-Q desde SEC EDGAR al almacén local.
    Solo tickers US. No altera Score_FUND. Sin RAG.
    """
    from bolsa_application.instrument_filings import InstrumentFilingsService

    try:
        result = await InstrumentFilingsService(get_instrument_repository(session)).fetch_from_sec(
            instrument_id,
            kind=kind,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="Instrument not found")
    return result


@router.delete("/instruments/{instrument_id}/filings/{filing_id}")
async def delete_instrument_filing(
    instrument_id: str,
    filing_id: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict:
    """F2b lite — elimina filing del almacén local."""
    from bolsa_application.instrument_filings import InstrumentFilingsService

    deleted = await InstrumentFilingsService(get_instrument_repository(session)).delete(
        instrument_id, filing_id
    )
    if deleted is None:
        raise HTTPException(status_code=404, detail="Instrument not found")
    if not deleted:
        raise HTTPException(status_code=404, detail="Filing not found")
    return {"ok": True}


@router.get(
    "/instruments/{instrument_id}/data-status",
    response_model=InstrumentDataStatusResponseDto,
)
async def get_instrument_data_status(
    instrument_id: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    timeframe: Annotated[str, Query()] = "1d",
) -> InstrumentDataStatusResponseDto:
    tf = _parse_timeframe(timeframe)
    status = await get_instrument_data_status_use_case(session).execute(instrument_id, timeframe=tf)
    if status is None:
        raise HTTPException(status_code=404, detail="Instrument not found")
    return InstrumentDataStatusResponseDto(data=to_data_status_dto(status))


@router.get("/instruments/{instrument_id}/ohlcv", response_model=OhlcvResponseDto)
async def get_ohlcv(
    instrument_id: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    limit: Annotated[int, Query(ge=1, le=10_000)] = 365,
    timeframe: Annotated[str, Query()] = "1d",
) -> OhlcvResponseDto:
    tf = _parse_timeframe(timeframe)
    bars = await get_ohlcv_bars_use_case(session).execute(
        instrument_id,
        limit=limit,
        timeframe=tf,
    )
    if bars is None:
        raise HTTPException(status_code=404, detail="Instrument not found")
    return to_ohlcv_dto(bars, timeframe=tf.value)


@router.get("/instruments/{instrument_id}/indicators", response_model=IndicatorsResponseDto)
async def get_indicators(
    instrument_id: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    limit: Annotated[int, Query(ge=1, le=2000)] = 365,
    timeframe: Annotated[str, Query()] = "1d",
) -> IndicatorsResponseDto:
    tf = _parse_timeframe(timeframe)
    result = await get_instrument_indicators_use_case(session).execute(
        instrument_id,
        limit=limit,
        timeframe=tf,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Instrument not found")
    return to_indicators_dto(result.data, result.signals)


@router.get("/instruments/{instrument_id}/live-quote", response_model=LiveQuoteEnvelopeDto)
async def get_live_quote(
    instrument_id: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> LiveQuoteEnvelopeDto:
    quote = await get_live_quote_use_case(session).execute(instrument_id)
    if quote is None:
        raise HTTPException(status_code=404, detail="Instrument not found")
    return LiveQuoteEnvelopeDto(data=to_live_quote_dto(quote))


@router.post("/instruments/{instrument_id}/sync", response_model=SyncResponseDto)
async def sync_instrument(
    instrument_id: str,
    body: SyncRequestDto,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> SyncResponseDto:
    result = await get_sync_instrument_use_case(session).execute(
        instrument_id,
        years_back=body.years_back or 5,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Instrument not found")
    if result.status == "failed":
        scheduler = get_sync_scheduler_repository(session)
        settings = await scheduler.get_settings()
        await scheduler.requeue_failed(
            instrument_id,
            result.error or "sync failed",
            settings.retry_backoff_minutes,
        )
    return SyncResponseDto(data=to_sync_result_dto(result))


@router.get(
    "/instruments/{instrument_id}/removal-preview",
    response_model=InstrumentRemovalPreviewResponseDto,
)
async def get_instrument_removal_preview(
    instrument_id: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    excluding_list_id: Annotated[str | None, Query(alias="excludingListId")] = None,
) -> InstrumentRemovalPreviewResponseDto:
    preview = await get_instrument_removal_preview_use_case(session).execute(
        instrument_id,
        excluding_list_id=excluding_list_id,
    )
    if preview is None:
        raise HTTPException(status_code=404, detail="Instrument not found")
    return InstrumentRemovalPreviewResponseDto(data=to_removal_preview_dto(preview))


@router.delete("/instruments/{instrument_id}", status_code=204)
async def delete_instrument(
    instrument_id: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    force: Annotated[bool, Query()] = False,
) -> None:
    try:
        await get_delete_instrument_use_case(session).execute(instrument_id, force=force)
    except ValueError as exc:
        detail = str(exc)
        status = 404 if "no encontrado" in detail.lower() else 400
        raise HTTPException(status_code=status, detail=detail) from exc
