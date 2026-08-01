"""API — discovery / constitutivos / suscripción de índices (L0–L2)."""



from typing import Annotated



from fastapi import APIRouter, Depends, HTTPException, Query, status

from sqlalchemy.ext.asyncio import AsyncSession



from bolsa_api.api.dependencies import (

    get_db_session,

    get_import_instrument_use_case,

    get_instrument_repository,

    get_list_repository,

)

from bolsa_api.schemas.market_indices import (

    CatalogIndexEntryDto,

    IndexConstituentDto,

    IndexConstituentMemberDto,

    IndexConstituentsResponseDto,

    IndexHitDto,

    IndexSubscribeJobDto,

    IndexSubscribeJobResponseDto,

    MarketIndexCatalogResponseDto,

    MarketIndicesSearchResponseDto,

    SubscribeMarketIndexRequestDto,

    SubscribeMarketIndexResponseDto,

    SubscribeMarketIndexResultDto,

    SubscribeProgressDto,

)

from bolsa_application.market_indices import (

    EnqueueIndexSubscribeJob,

    GetIndexSubscribeJob,

    ListMarketIndexCatalog,

    ResolveIndexConstituents,

    SearchMarketIndices,

    SubscribeMarketIndex,

)

from bolsa_infrastructure.database.repositories.index_subscribe_job_repository import (

    IndexSubscribeJobRecord,

    SqlAlchemyIndexSubscribeJobRepository,

)



router = APIRouter()





def _job_dto(record: IndexSubscribeJobRecord) -> IndexSubscribeJobDto:

    return IndexSubscribeJobDto(

        id=record.id,

        status=record.status,

        payload=record.payload,

        result=record.result,

        error=record.error,

        created_at=record.created_at,

        updated_at=record.updated_at,

        completed_at=record.completed_at,

    )





@router.get("/market-indices/catalog", response_model=MarketIndexCatalogResponseDto)

async def list_market_index_catalog() -> MarketIndexCatalogResponseDto:

    entries = ListMarketIndexCatalog().execute()

    return MarketIndexCatalogResponseDto(

        data=[

            CatalogIndexEntryDto(

                code=e.code,

                display_name=e.display_name,

                yahoo_symbol=e.yahoo_symbol,

                region=e.region,

                currency=e.currency,

                constituent_ready=e.constituent_ready,

                expected_count_min=e.expected_count_min,

                expected_count_max=e.expected_count_max,

                list_id=e.list_id,

            )

            for e in entries

        ],

    )





@router.get("/market-indices/search", response_model=MarketIndicesSearchResponseDto)

async def search_market_indices(

    q: Annotated[str, Query(min_length=1, max_length=80)],

    limit: Annotated[int, Query(ge=1, le=30)] = 12,

) -> MarketIndicesSearchResponseDto:

    result = await SearchMarketIndices().execute(q, limit=limit)

    return MarketIndicesSearchResponseDto(

        data=[

            IndexHitDto(

                code=hit.code,

                display_name=hit.display_name,

                yahoo_symbol=hit.yahoo_symbol,

                region=hit.region,

                currency=hit.currency,

                quote_type=hit.quote_type,

                source=hit.source,

                constituent_ready=hit.constituent_ready,

                score=hit.score,

            )

            for hit in result.hits

        ],

    )





@router.get(

    "/market-indices/{index_key}/constituents",

    response_model=IndexConstituentsResponseDto,

)

async def get_index_constituents(index_key: str) -> IndexConstituentsResponseDto:

    resolved = await ResolveIndexConstituents().execute(index_key)

    if resolved is None:

        raise HTTPException(

            status_code=404,

            detail=(

                "Constituents no disponibles aún para este índice "

                "(provider pending)."

            ),

        )

    return IndexConstituentsResponseDto(

        data=IndexConstituentDto(

            index_code=resolved.index_code,

            yahoo_index_symbol=resolved.yahoo_index_symbol,

            provider=resolved.provider,

            as_of=resolved.as_of,

            content_hash=resolved.content_hash,

            members=[

                IndexConstituentMemberDto(

                    symbol=m.symbol,

                    yahoo_symbol=m.yahoo_symbol,

                    name=m.name,

                )

                for m in resolved.members

            ],

        ),

    )





@router.post("/market-indices/subscribe", response_model=SubscribeMarketIndexResponseDto)

async def subscribe_market_index(

    body: SubscribeMarketIndexRequestDto,

    session: Annotated[AsyncSession, Depends(get_db_session)],

) -> SubscribeMarketIndexResponseDto:

    """Suscripción síncrona (índices pequeños / compat). Preferir /subscribe/jobs para S&P 500."""

    use_case = SubscribeMarketIndex(

        get_list_repository(session),

        get_instrument_repository(session),

        get_import_instrument_use_case(session),

    )

    try:

        result = await use_case.execute(

            body.index_key,

            sync_bars=body.sync_bars,

            years_back=body.years_back,

        )

    except ValueError as exc:

        raise HTTPException(status_code=400, detail=str(exc)) from exc

    except Exception as exc:

        raise HTTPException(status_code=500, detail=f"No se pudo suscribir el índice: {exc}") from exc



    return SubscribeMarketIndexResponseDto(

        data=SubscribeMarketIndexResultDto(

            list_id=result.list_id,

            index_code=result.index_code,

            display_name=result.display_name,

            yahoo_index_symbol=result.yahoo_index_symbol,

            content_hash=result.content_hash,

            instrument_ids=result.instrument_ids,

            progress=SubscribeProgressDto(

                total=result.progress.total,

                already_present=result.progress.already_present,

                imported=result.progress.imported,

                failed=list(result.progress.failed),

                joined=list(result.progress.joined),

                left=list(result.progress.left),

            ),

            status=result.status,

        ),

    )





@router.post(

    "/market-indices/subscribe/jobs",

    response_model=IndexSubscribeJobResponseDto,

    status_code=status.HTTP_202_ACCEPTED,

)

async def enqueue_index_subscribe_job(

    body: SubscribeMarketIndexRequestDto,

    session: Annotated[AsyncSession, Depends(get_db_session)],

) -> IndexSubscribeJobResponseDto:

    jobs = SqlAlchemyIndexSubscribeJobRepository(session)

    record = await EnqueueIndexSubscribeJob(jobs).execute(

        index_key=body.index_key,

        sync_bars=body.sync_bars,

        years_back=body.years_back,

    )

    return IndexSubscribeJobResponseDto(data=_job_dto(record))





@router.get(

    "/market-indices/subscribe/jobs/{job_id}",

    response_model=IndexSubscribeJobResponseDto,

)

async def get_index_subscribe_job(

    job_id: str,

    session: Annotated[AsyncSession, Depends(get_db_session)],

) -> IndexSubscribeJobResponseDto:

    record = await GetIndexSubscribeJob(SqlAlchemyIndexSubscribeJobRepository(session)).execute(job_id)

    if record is None:

        raise HTTPException(status_code=404, detail="Job no encontrado")

    return IndexSubscribeJobResponseDto(data=_job_dto(record))


