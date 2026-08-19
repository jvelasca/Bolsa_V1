"""API: dictamen diario Estudio (InstrumentDailyOpinion, on-demand)."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_api.api.dependencies import (
    get_daily_opinion_service,
    get_daily_opinion_telemetry_service,
    get_db_session,
)
from bolsa_api.schemas.instrument_daily_opinions import (
    EstudioEodDigestNotifyDto,
    EstudioEodOpinionBatchResponseDto,
    EstudioEodOpinionEmailNotifyDto,
    InstrumentDailyOpinionsListResponseDto,
    OpinionTelemetryDto,
    OpinionTelemetryResponseDto,
    QueryInstrumentDailyOpinionsDto,
    RunEstudioEodOpinionBatchDto,
    to_instrument_daily_opinion_dto,
)
from bolsa_application.daily_opinion_service import OpinionHint
from bolsa_infrastructure.alerts.daily_ops_digest_email import maybe_notify_daily_ops_digest
from bolsa_infrastructure.alerts.estudio_opinion_email import maybe_notify_estudio_alarmas
from bolsa_infrastructure.config import get_settings

router = APIRouter()


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
    service = get_daily_opinion_service(session)
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
    return InstrumentDailyOpinionsListResponseDto(
        data=[to_instrument_daily_opinion_dto(r) for r in rows]
    )


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
    service = get_daily_opinion_service(session)
    rows = await service.query(
        instrument_ids=[instrument_id],
        as_of_bar_date=_parse_as_of(as_of_bar_date),
        force_refresh=force_refresh,
        hints=[],
    )
    return InstrumentDailyOpinionsListResponseDto(
        data=[to_instrument_daily_opinion_dto(r) for r in rows]
    )


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
    service = get_daily_opinion_service(session)
    rows = await service.history(
        instrument_id,
        days=days,
        ensure_days=ensure_days,
    )
    return InstrumentDailyOpinionsListResponseDto(
        data=[to_instrument_daily_opinion_dto(r) for r in rows]
    )


@router.get(
    "/instrument-daily-opinions/telemetry",
    response_model=OpinionTelemetryResponseDto,
)
async def get_opinion_telemetry(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    lookback_days: Annotated[int, Query(alias="lookbackDays", ge=7, le=366)] = 90,
    instrument_ids: Annotated[list[str] | None, Query(alias="instrumentIds")] = None,
) -> OpinionTelemetryResponseDto:
    """A0 — precisión/recall proxy del dictamen (sin execute AUTO)."""
    ids = None
    if instrument_ids:
        ids = [i.strip() for i in instrument_ids if isinstance(i, str) and i.strip()]
        if not ids:
            ids = None
    service = get_daily_opinion_telemetry_service(session)
    tel = await service.compute(lookback_days=lookback_days, instrument_ids=ids)
    return OpinionTelemetryResponseDto(data=OpinionTelemetryDto.model_validate(tel.to_dict()))


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
    service = get_daily_opinion_service(session)
    rows = await service.run_eod_batch(
        instrument_ids=body.instrument_ids,
        as_of_bar_date=_parse_as_of(body.as_of_bar_date),
        account_id=body.account_id,
        force=True,
    )
    email_meta = await maybe_notify_estudio_alarmas(
        settings,
        rows,
        email_to=body.notify_email,
        email_enabled=body.notify_email_enabled,
    )

    digest_meta: dict[str, Any] | None = None
    want_digest = body.notify_digest_enabled is not None or bool(
        settings.daily_ops_digest_email_enabled
    )
    if want_digest:
        digest_bundle = None
        if body.account_id:
            from bolsa_api.api.dependencies import get_daily_ops_report_use_case

            try:
                digest_bundle = await get_daily_ops_report_use_case(session).execute(
                    body.account_id,
                    as_of=_parse_as_of(body.as_of_bar_date),
                    instrument_ids=list(body.instrument_ids),
                )
            except ValueError:
                digest_bundle = None
        digest_meta = await maybe_notify_daily_ops_digest(
            settings,
            digest_bundle,
            email_to=body.notify_email,
            digest_enabled=body.notify_digest_enabled,
            attach_pdf=body.attach_pdf,
        )

    return EstudioEodOpinionBatchResponseDto(
        enabled=enabled,
        forced=bool(body.force) or not enabled,
        count=len(rows),
        data=[to_instrument_daily_opinion_dto(r) for r in rows],
        email_notify=EstudioEodOpinionEmailNotifyDto(
            email_enabled=bool(email_meta["email_enabled"]),
            alarma_count=int(email_meta["alarma_count"]),
            sent=bool(email_meta["sent"]),
            skipped_reason=email_meta.get("skipped_reason"),
        ),
        digest_notify=(
            EstudioEodDigestNotifyDto(
                digest_enabled=bool(digest_meta["digest_enabled"]),
                sent=bool(digest_meta["sent"]),
                skipped_reason=digest_meta.get("skipped_reason"),
                as_of=digest_meta.get("as_of"),
                pdf_attached=bool(digest_meta.get("pdf_attached")),
            )
            if digest_meta is not None
            else None
        ),
    )
