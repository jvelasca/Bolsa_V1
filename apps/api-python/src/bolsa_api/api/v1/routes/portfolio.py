"""API: cartera y posiciones."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_api.api.dependencies import (
    get_account_repository,
    get_db_session,
    get_execute_gated_portfolio_trade_use_case,
    get_investor_profile_repository,
    get_list_transactions_use_case,
    get_portfolio_recon_lookup,
    get_portfolio_summary_use_case,
    get_position_state_repository,
    require_account_header_access,
)
from bolsa_api.api.v1.idempotency_responses import IDEMPOTENCY_CONFLICT_RESPONSES
from bolsa_api.schemas.extra_mappers import (
    attach_operational_positions,
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
from bolsa_application.execute_gated_portfolio_trade import (
    ExitVetoedError,
    OpeningVetoedError,
)

router = APIRouter()





@router.get("/portfolio", response_model=PortfolioSummaryResponseDto)

async def get_portfolio(

    session: Annotated[AsyncSession, Depends(get_db_session)],

    account_id: Annotated[str | None, Depends(require_account_header_access)],

) -> PortfolioSummaryResponseDto:

    use_case = get_portfolio_summary_use_case(session)

    summary = await use_case.execute(account_id=account_id)

    dto = to_portfolio_summary_dto(summary)
    scope = await get_account_repository(session).resolve_scope(account_id)
    records = await get_position_state_repository(session).list_open_for_account(
        scope.account.id
    )
    profile = await get_investor_profile_repository(session).get_for_account(
        scope.account.id
    )
    template_id = (
        profile.selected_policy_template_id
        if profile is not None
        else None
    )
    attach_operational_positions(
        dto,
        records,
        policy_template_id=template_id,
        recon_status=await _portfolio_recon_status(session, scope.account.id),
        lifecycle_stages=await _lifecycle_stages_for_positions(
            session, [p.id for p in dto.positions]
        ),
    )
    return PortfolioSummaryResponseDto(data=dto)


async def _lifecycle_stages_for_positions(
    session: AsyncSession, position_ids: list[str]
) -> dict[str, str]:
    """V1.91 — batch lifecycle stage for Mesa (one portfolio GET, no FE N+1)."""
    if not position_ids:
        return {}
    from bolsa_application.lifecycle_event_store import PostgresLifecycleEventStore
    from bolsa_domain.lifecycle import reduce_lifecycle_events

    store = PostgresLifecycleEventStore(session)
    stages: dict[str, str] = {}
    for pid in position_ids:
        try:
            events = await store.list_by_position(pid)
        except Exception:  # noqa: BLE001
            continue
        if not events:
            continue
        stage, _ = reduce_lifecycle_events(events)
        if isinstance(stage, str) and stage:
            stages[pid] = stage
    return stages


async def _portfolio_recon_status(session: AsyncSession, account_id: str) -> str:
    try:
        status = await get_portfolio_recon_lookup(session).portfolio_recon_status(
            account_id
        )
        return str(status)
    except Exception:
        return "unavailable"





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
    account_id: Annotated[str | None, Depends(require_account_header_access)],
) -> TradeResponseDto:
    use_case = get_execute_gated_portfolio_trade_use_case(session)
    try:
        result = await use_case.execute(
            instrument_id=body.instrument_id,
            trade_type=body.type,
            quantity=body.quantity,
            price=body.price,
            account_id=account_id,
            idempotency_key=body.idempotency_key,
        )
    except OpeningVetoedError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ExitVetoedError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return TradeResponseDto(data=to_trade_response_data(result))


