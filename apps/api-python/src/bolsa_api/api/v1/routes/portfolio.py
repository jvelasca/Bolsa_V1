"""API: cartera y posiciones."""

from typing import Annotated

from bolsa_application.accounts import ExecuteTrade
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_api.api.dependencies import (
    get_account_id_header,
    get_db_session,
    get_execute_trade_use_case,
    get_list_transactions_use_case,
    get_portfolio_summary_use_case,
    require_account_header_access,
)
from bolsa_api.api.v1.idempotency_responses import IDEMPOTENCY_CONFLICT_RESPONSES
from bolsa_api.schemas.extra_mappers import (
    to_portfolio_summary_dto,
    to_trade_response_data,
    to_transaction_dto,
)
from bolsa_api.schemas.portfolio import (
    PortfolioSummaryResponseDto,
    TradeRequestDto,
    TradeResponseDto,
    TransactionsResponseDto,
)

router = APIRouter()





@router.get("/portfolio", response_model=PortfolioSummaryResponseDto)

async def get_portfolio(

    session: Annotated[AsyncSession, Depends(get_db_session)],

    account_id: Annotated[str | None, Depends(require_account_header_access)],

) -> PortfolioSummaryResponseDto:

    use_case = get_portfolio_summary_use_case(session)

    summary = await use_case.execute(account_id=account_id)

    return PortfolioSummaryResponseDto(data=to_portfolio_summary_dto(summary))





@router.get("/portfolio/transactions", response_model=TransactionsResponseDto)

async def list_transactions(

    session: Annotated[AsyncSession, Depends(get_db_session)],

    account_id: Annotated[str | None, Depends(require_account_header_access)],

    limit: Annotated[int, Query(ge=1, le=200)] = 50,

) -> TransactionsResponseDto:

    transactions = await get_list_transactions_use_case(session).execute(

        limit=limit,

        account_id=account_id,

    )

    return TransactionsResponseDto(data=[to_transaction_dto(tx) for tx in transactions])





@router.post(
    "/portfolio/trade",
    response_model=TradeResponseDto,
    responses=IDEMPOTENCY_CONFLICT_RESPONSES,
)

async def execute_trade(

    body: TradeRequestDto,

    session: Annotated[AsyncSession, Depends(get_db_session)],

    account_id: Annotated[str | None, Depends(get_account_id_header)],

) -> TradeResponseDto:

    use_case: ExecuteTrade = get_execute_trade_use_case(session)

    try:

        result = await use_case.execute(

            instrument_id=body.instrument_id,

            trade_type=body.type,

            quantity=body.quantity,

            price=body.price,

            account_id=account_id,

            idempotency_key=body.idempotency_key,

        )

    except ValueError as exc:

        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return TradeResponseDto(data=to_trade_response_data(result))


