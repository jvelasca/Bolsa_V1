"""API: dictamen diario Estudio (InstrumentDailyOpinion, on-demand)."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_api.api.dependencies import get_db_session
from bolsa_api.schemas.instrument_daily_opinions import (
    EstudioEodOpinionBatchResponseDto,
    EstudioEodOpinionEmailNotifyDto,
    InstrumentDailyOpinionDto,
    InstrumentDailyOpinionsListResponseDto,
    QueryInstrumentDailyOpinionsDto,
    RunEstudioEodOpinionBatchDto,
)
from bolsa_application.daily_opinion_service import DailyOpinionService, OpinionHint
from bolsa_infrastructure.alerts.estudio_opinion_email import maybe_notify_estudio_alarmas
from bolsa_infrastructure.config import get_settings
from bolsa_infrastructure.database.repositories.instrument_daily_opinion_repository import (
    InstrumentDailyOpinionRecord,
    SqlAlchemyInstrumentDailyOpinionRepository,
)
from bolsa_infrastructure.database.repositories.instrument_strategy_top_repository import (
    SqlAlchemyInstrumentStrategyTopRepository,
)
from bolsa_infrastructure.database.repositories.ohlcv_repository import (
    SqlAlchemyOhlcvRepository,
)

router = APIRouter()


def _iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _to_dto(row: InstrumentDailyOpinionRecord) -> InstrumentDailyOpinionDto:
    return InstrumentDailyOpinionDto(
        id=row.id,
        instrument_id=row.instrument_id,
        account_id=row.account_id,
        as_of_bar_date=row.as_of_bar_date.isoformat(),
        stance=row.stance,  # type: ignore[arg-type]
        dictamen_stars=row.dictamen_stars,
        strategy_stars=row.strategy_stars,
        io_score=row.io_score,
        fa_score=row.fa_score,
        ta_score=row.ta_score,
        distress=row.distress,
        reasons=list(row.reasons),
        gate_status=row.gate_status,  # type: ignore[arg-type]
        top_id=row.top_id,
        top_version=row.top_version,
        source=row.source,  # type: ignore[arg-type]
        engine_version=row.engine_version,
        idempotency_key=row.idempotency_key,
        computed_at=_iso(row.computed_at),
        created_at=_iso(row.created_at),
        updated_at=_iso(row.updated_at),
    )


def _parse_as_of(raw: str | None) -> date | None:
    if not raw:
        return None
    try:
        return date.fromisoformat(raw.strip()[:10])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="asOfBarDate inválida (YYYY-MM-DD)") from exc


@router.post(
    "/instrument-daily-opinions/query",
    response_model=InstrumentDailyOpinionsListResponseDto,
)
async def query_instrument_daily_opinions(
    body: QueryInstrumentDailyOpinionsDto,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> InstrumentDailyOpinionsListResponseDto:
    service = DailyOpinionService(
        SqlAlchemyInstrumentDailyOpinionRepository(session),
        SqlAlchemyInstrumentStrategyTopRepository(session),
        SqlAlchemyOhlcvRepository(session),
    )
    hints = [
        OpinionHint(
            instrument_id=h.instrument_id,
            io_score=h.io_score,
            fa_score=h.fa_score,
            ta_score=h.ta_score,
            distress=h.distress,
            position_open=h.position_open,
            allow_trading=h.allow_trading,
            has_eod_bar=h.has_eod_bar,
        )
        for h in body.hints
    ]
    try:
        rows = await service.query(
            instrument_ids=body.instrument_ids,
            as_of_bar_date=_parse_as_of(body.as_of_bar_date),
            account_id=body.account_id,
            force_refresh=body.force_refresh,
            hints=hints,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return InstrumentDailyOpinionsListResponseDto(data=[_to_dto(r) for r in rows])


@router.get(
    "/instruments/{instrument_id}/daily-opinion",
    response_model=InstrumentDailyOpinionsListResponseDto,
)
async def get_instrument_daily_opinion(
    instrument_id: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    as_of_bar_date: Annotated[str | None, Query(alias="asOfBarDate")] = None,
    force_refresh: Annotated[bool, Query(alias="forceRefresh")] = False,
) -> InstrumentDailyOpinionsListResponseDto:
    """Conveniencia single-id (sin hints → fail-closed EOD vía barras)."""
    service = DailyOpinionService(
        SqlAlchemyInstrumentDailyOpinionRepository(session),
        SqlAlchemyInstrumentStrategyTopRepository(session),
        SqlAlchemyOhlcvRepository(session),
    )
    rows = await service.query(
        instrument_ids=[instrument_id],
        as_of_bar_date=_parse_as_of(as_of_bar_date),
        force_refresh=force_refresh,
        hints=[],
    )
    return InstrumentDailyOpinionsListResponseDto(data=[_to_dto(r) for r in rows])


@router.get(
    "/instruments/{instrument_id}/daily-opinions",
    response_model=InstrumentDailyOpinionsListResponseDto,
)
async def list_instrument_daily_opinions(
    instrument_id: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    days: Annotated[int, Query(ge=1, le=90)] = 30,
    ensure_days: Annotated[int, Query(alias="ensureDays", ge=0, le=21)] = 0,
) -> InstrumentDailyOpinionsListResponseDto:
    """Historial de dictámenes (ascendente). `ensureDays` rellena laborables faltantes."""
    service = DailyOpinionService(
        SqlAlchemyInstrumentDailyOpinionRepository(session),
        SqlAlchemyInstrumentStrategyTopRepository(session),
        SqlAlchemyOhlcvRepository(session),
    )
    rows = await service.history(
        instrument_id,
        days=days,
        ensure_days=ensure_days,
    )
    return InstrumentDailyOpinionsListResponseDto(data=[_to_dto(r) for r in rows])


@router.post(
    "/instrument-daily-opinions/eod-batch",
    response_model=EstudioEodOpinionBatchResponseDto,
)
async def run_estudio_eod_opinion_batch(
    body: RunEstudioEodOpinionBatchDto,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> EstudioEodOpinionBatchResponseDto:
    """Batch EOD (source=eod_batch). Flag off-by-default; `force` permite dry-run manual."""
    settings = get_settings()
    enabled = bool(settings.estudio_eod_opinion_enabled)
    if not enabled and not body.force:
        raise HTTPException(
            status_code=403,
            detail=(
                "ESTUDIO_EOD_OPINION_ENABLED=false. "
                "Pasa force=true para una corrida manual (sin cron)."
            ),
        )
    service = DailyOpinionService(
        SqlAlchemyInstrumentDailyOpinionRepository(session),
        SqlAlchemyInstrumentStrategyTopRepository(session),
        SqlAlchemyOhlcvRepository(session),
    )
    rows = await service.run_eod_batch(
        instrument_ids=body.instrument_ids,
        as_of_bar_date=_parse_as_of(body.as_of_bar_date),
        account_id=body.account_id,
        force=True,
    )
    email_meta = await maybe_notify_estudio_alarmas(settings, rows)
    return EstudioEodOpinionBatchResponseDto(
        enabled=enabled,
        forced=bool(body.force) or not enabled,
        count=len(rows),
        data=[_to_dto(r) for r in rows],
        email_notify=EstudioEodOpinionEmailNotifyDto(
            email_enabled=bool(email_meta["email_enabled"]),
            alarma_count=int(email_meta["alarma_count"]),
            sent=bool(email_meta["sent"]),
            skipped_reason=email_meta.get("skipped_reason"),
        ),
    )
