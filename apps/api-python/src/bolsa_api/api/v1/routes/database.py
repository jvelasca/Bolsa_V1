from typing import Annotated

from bolsa_application.account_lifecycle import ListClosedSimulatedAccountsResult
from bolsa_application.get_database_summary import DatabaseSummary
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_api.api.dependencies import (
    get_database_summary_use_case,
    get_db_session,
    get_list_closed_simulated_accounts_use_case,
    get_list_orphan_instruments_use_case,
    get_purge_closed_simulated_accounts_use_case,
    get_purge_orphan_instruments_use_case,
)
from bolsa_api.schemas.account_lifecycle import (
    ClosedSimulatedAccountDto,
    ClosedSimulatedAccountsDto,
    ClosedSimulatedAccountsResponseDto,
    PurgeClosedAccountSkippedDto,
    PurgeClosedAccountsRequestDto,
    PurgeClosedAccountsResponseDto,
    PurgeClosedAccountsResultDto,
)
from bolsa_api.schemas.database import (
    DatabaseSummaryDto,
    DatabaseSummaryResponseDto,
    DatabaseTableCountDto,
    InstrumentOhlcvBreakdownDto,
)
from bolsa_api.schemas.instrument_lifecycle import (
    OrphanInstrumentsResponseDto,
    PurgeOrphansRequestDto,
    PurgeOrphansResponseDto,
)
from bolsa_api.schemas.lifecycle_mappers import to_orphans_dto, to_purge_orphans_result_dto

router = APIRouter()


def _to_dto(summary: DatabaseSummary) -> DatabaseSummaryDto:
    return DatabaseSummaryDto(
        connected=summary.connected,
        message=summary.message,
        tables=[
            DatabaseTableCountDto(table=t.table, label=t.label, count=t.count)
            for t in summary.tables
        ],
        instrument_ohlcv=[
            InstrumentOhlcvBreakdownDto(timeframe=i.timeframe, bar_count=i.bar_count)
            for i in summary.instrument_ohlcv
        ],
    )


@router.get("/database/summary", response_model=DatabaseSummaryResponseDto)
async def get_database_summary(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    instrument_id: Annotated[str | None, Query(alias="instrumentId")] = None,
) -> DatabaseSummaryResponseDto:
    summary = await get_database_summary_use_case(session).execute(instrument_id)
    return DatabaseSummaryResponseDto(data=_to_dto(summary))


@router.get("/database/orphans", response_model=OrphanInstrumentsResponseDto)
async def list_orphan_instruments(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> OrphanInstrumentsResponseDto:
    result = await get_list_orphan_instruments_use_case(session).execute(limit=limit)
    return OrphanInstrumentsResponseDto(data=to_orphans_dto(result))


@router.post("/database/orphans/purge", response_model=PurgeOrphansResponseDto)
async def purge_orphan_instruments(
    body: PurgeOrphansRequestDto,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> PurgeOrphansResponseDto:
    raw = await get_purge_orphan_instruments_use_case(session).execute(limit=body.limit)
    return PurgeOrphansResponseDto(data=to_purge_orphans_result_dto(raw))


def _to_closed_accounts_dto(
    result: ListClosedSimulatedAccountsResult,
) -> ClosedSimulatedAccountsDto:
    return ClosedSimulatedAccountsDto(
        accounts=[
            ClosedSimulatedAccountDto(
                id=a.id,
                name=a.name,
                currency=a.currency,
                updated_at=a.updated_at.isoformat(),
                ledger_entry_count=a.ledger_entry_count,
                portfolio_count=a.portfolio_count,
                position_count=a.position_count,
                transaction_count=a.transaction_count,
                pending_order_count=a.pending_order_count,
            )
            for a in result.accounts
        ],
        total_ledger_entries=result.total_ledger_entries,
    )


@router.get("/database/closed-accounts", response_model=ClosedSimulatedAccountsResponseDto)
async def list_closed_simulated_accounts(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> ClosedSimulatedAccountsResponseDto:
    result = await get_list_closed_simulated_accounts_use_case(session).execute(limit=limit)
    return ClosedSimulatedAccountsResponseDto(data=_to_closed_accounts_dto(result))


@router.post("/database/closed-accounts/purge", response_model=PurgeClosedAccountsResponseDto)
async def purge_closed_simulated_accounts(
    body: PurgeClosedAccountsRequestDto,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> PurgeClosedAccountsResponseDto:
    raw = await get_purge_closed_simulated_accounts_use_case(session).execute(limit=body.limit)
    skipped_raw = raw.get("skipped") or []
    skipped = [
        PurgeClosedAccountSkippedDto(
            account_id=str(item["accountId"]),
            name=str(item["name"]),
            reasons=list(item.get("reasons") or []),
        )
        for item in skipped_raw
        if isinstance(item, dict)
    ]
    return PurgeClosedAccountsResponseDto(
        data=PurgeClosedAccountsResultDto(
            purged_ids=list(raw.get("purgedIds") or []),
            skipped=skipped,
            scanned=int(raw.get("scanned") or 0),
        )
    )
