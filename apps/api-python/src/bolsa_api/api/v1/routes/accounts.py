"""API: cuentas DEMO/trading (CRUD + resumen)."""

from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_api.api.dependencies import (
    get_account_repository,
    get_close_account_use_case,
    get_create_account_use_case,
    get_daily_ops_report_use_case,
    get_db_session,
    get_decision_board_use_case,
    get_decision_journal_use_case,
    get_delete_account_use_case,
    get_deposit_cash_use_case,
    get_get_account_summary_use_case,
    get_get_account_use_case,
    get_list_account_summaries_use_case,
    get_list_accounts_use_case,
    get_list_ledger_use_case,
    get_record_session_verdict_use_case,
    get_set_default_account_use_case,
    get_tax_report_use_case,
    get_update_account_settings_use_case,
    get_update_account_use_case,
    get_withdraw_cash_use_case,
    require_account_access,
)
from bolsa_api.api.v1.idempotency_responses import IDEMPOTENCY_CONFLICT_RESPONSES
from bolsa_api.auth.request_principal import get_request_principal
from bolsa_api.schemas.account_mappers import (
    settings_dto_to_domain,
    to_account_summary_dto,
    to_cash_movement_result_dto,
    to_investment_account_dto,
    to_ledger_entry_dto,
    to_tax_report_dto,
)
from bolsa_api.schemas.accounts import (
    AccountResponseDto,
    AccountsResponseDto,
    AccountSummariesResponseDto,
    AccountSummaryResponseDto,
    CashMovementResponseDto,
    CreateAccountInvestorProfileDto,
    CreateInvestmentAccountDto,
    DailyOpsDigestNotifyDto,
    DailyOpsDigestNotifyResponseDto,
    DecisionBoardResponseDto,
    DecisionJournalListResponseDto,
    DepositCashDto,
    LedgerResponseDto,
    SendDailyOpsDigestDto,
    SessionVerdictBodyDto,
    SessionVerdictResponseDto,
    TaxReportResponseDto,
    UpdateAccountSettingsDto,
    UpdateInvestmentAccountDto,
    WithdrawCashDto,
)
from bolsa_api.schemas.ai_governance import AiEffectivenessResponseDto
from bolsa_application.broker_venue_runtime import (
    account_broker_venue_from_settings,
    effective_broker_venue_async,
    normalize_broker_venue,
)

router = APIRouter()


class AccountBrokerVenueBody(BaseModel):
    """PA-1 — preferencia Paper|Live en settings_json.brokerVenue (≠ override global mesa)."""

    venue: Literal["paper", "live"] = Field(..., description="Preferencia por cuenta")


class AccountBrokerVenueResponse(BaseModel):
    accountId: str
    preference: Literal["paper", "live"] | None = None
    effective: Literal["paper", "live"]


@router.get("/accounts", response_model=AccountsResponseDto)
async def list_accounts(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    type: str | None = Query(default=None),
) -> AccountsResponseDto:
    owner_user_id = get_request_principal(request)
    accounts = await get_list_accounts_use_case(session).execute(
        account_type=type,
        owner_user_id=owner_user_id,
    )
    return AccountsResponseDto(data=[to_investment_account_dto(a) for a in accounts])


@router.get("/accounts/summaries", response_model=AccountSummariesResponseDto)
async def list_account_summaries(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    type: str | None = Query(default=None),
) -> AccountSummariesResponseDto:
    """Hub equity strip — no per-row HTTP and no custody side-effects."""
    owner_user_id = get_request_principal(request)
    summaries = await get_list_account_summaries_use_case(session).execute(
        account_type=type,
        owner_user_id=owner_user_id,
    )
    return AccountSummariesResponseDto(data=[to_account_summary_dto(s) for s in summaries])


@router.post("/accounts", response_model=AccountResponseDto, status_code=201)
async def create_account(
    body: CreateInvestmentAccountDto,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AccountResponseDto:
    settings = settings_dto_to_domain(body.settings) if body.settings else None
    account = await get_create_account_use_case(session).execute(
        name=body.name,
        description=body.description,
        currency=body.currency,
        base_currency=body.base_currency,
        initial_deposit=body.initial_deposit,
        leverage=body.leverage,
        margin_call_level_pct=body.margin_call_level_pct,
        portfolio_name=body.portfolio_name,
        portfolio_description=body.portfolio_description,
        strategy_tag=body.strategy_tag,
        settings=settings,
        commission_preset_id=body.commission_preset_id,
    )
    # ART-PROFILE: wizard puede crear/asignar; si no, moderate por defecto (Gate)
    from bolsa_api.api.dependencies import get_ensure_account_investor_profile_use_case

    declared = None
    if body.investor_profile is not None:
        ip: CreateAccountInvestorProfileDto = body.investor_profile
        from bolsa_application.investor_profiles import DeclaredProfileInput

        declared = DeclaredProfileInput(
            name=ip.name,
            horizon=ip.horizon,
            objectives=list(ip.objectives),
            risk_tolerance=ip.risk_tolerance,
            experience=ip.experience,
            max_acceptable_loss_pct=ip.max_acceptable_loss_pct,
            notes=ip.notes,
            suggested_policy_template_id=ip.suggested_policy_template_id,
            selected_policy_template_id=ip.selected_policy_template_id,
        )
    try:
        await get_ensure_account_investor_profile_use_case(session).execute(
            account_id=account.id,
            account_name=account.name,
            declared=declared,
            active_profile_id=body.active_profile_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    account = await get_get_account_use_case(session).execute(account.id)
    return AccountResponseDto(data=to_investment_account_dto(account))


@router.get("/accounts/{account_id}", response_model=AccountResponseDto)
async def get_account(
    account_id: Annotated[str, Depends(require_account_access)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AccountResponseDto:
    try:
        account = await get_get_account_use_case(session).execute(account_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return AccountResponseDto(data=to_investment_account_dto(account))


@router.patch("/accounts/{account_id}", response_model=AccountResponseDto)
async def update_account(
    account_id: Annotated[str, Depends(require_account_access)],
    body: UpdateInvestmentAccountDto,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AccountResponseDto:
    try:
        account = await get_update_account_use_case(session).execute(
            account_id,
            name=body.name,
            description=body.description,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return AccountResponseDto(data=to_investment_account_dto(account))


@router.post("/accounts/{account_id}/make-default", response_model=AccountResponseDto)
async def make_default_account(
    account_id: Annotated[str, Depends(require_account_access)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AccountResponseDto:
    try:
        account = await get_set_default_account_use_case(session).execute(account_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return AccountResponseDto(data=to_investment_account_dto(account))


@router.patch("/accounts/{account_id}/settings", response_model=AccountResponseDto)
async def update_account_settings(
    account_id: Annotated[str, Depends(require_account_access)],
    body: UpdateAccountSettingsDto,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AccountResponseDto:
    try:
        account = await get_update_account_settings_use_case(session).execute(
            account_id,
            settings_dto_to_domain(body.settings),
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return AccountResponseDto(data=to_investment_account_dto(account))


@router.get(
    "/accounts/{account_id}/broker-venue",
    response_model=AccountBrokerVenueResponse,
)
async def get_account_broker_venue(
    account_id: Annotated[str, Depends(require_account_access)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AccountBrokerVenueResponse:
    """PA-1 — preferencia cuenta + venue efectivo (global override gana)."""
    try:
        settings = await get_account_repository(session).get_settings_json(account_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    pref_raw = account_broker_venue_from_settings(settings)
    preference: Literal["paper", "live"] | None = (
        normalize_broker_venue(pref_raw) if pref_raw is not None else None
    )
    effective = await effective_broker_venue_async(account_venue=pref_raw)
    return AccountBrokerVenueResponse(
        accountId=account_id,
        preference=preference,
        effective=effective,
    )


@router.patch(
    "/accounts/{account_id}/broker-venue",
    response_model=AccountBrokerVenueResponse,
)
async def patch_account_broker_venue(
    account_id: Annotated[str, Depends(require_account_access)],
    body: AccountBrokerVenueBody,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AccountBrokerVenueResponse:
    """PA-1 — escribe settings_json.brokerVenue vía merge (≠ POST /risk/broker-venue)."""
    chosen = normalize_broker_venue(body.venue)
    try:
        await get_account_repository(session).merge_settings_json(
            account_id, {"brokerVenue": chosen}
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    effective = await effective_broker_venue_async(account_venue=chosen)
    return AccountBrokerVenueResponse(
        accountId=account_id,
        preference=chosen,
        effective=effective,
    )


@router.post("/accounts/{account_id}/close", response_model=AccountResponseDto)
async def close_account(
    account_id: Annotated[str, Depends(require_account_access)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AccountResponseDto:
    try:
        account = await get_close_account_use_case(session).execute(account_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return AccountResponseDto(data=to_investment_account_dto(account))


@router.delete("/accounts/{account_id}", status_code=204)
async def delete_account(
    account_id: Annotated[str, Depends(require_account_access)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> Response:
    try:
        await get_delete_account_use_case(session).execute(account_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return Response(status_code=204)


@router.get("/accounts/{account_id}/summary", response_model=AccountSummaryResponseDto)
async def get_account_summary(
    account_id: Annotated[str, Depends(require_account_access)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AccountSummaryResponseDto:
    try:
        summary = await get_get_account_summary_use_case(session).execute(account_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return AccountSummaryResponseDto(data=to_account_summary_dto(summary))


@router.get("/accounts/{account_id}/daily-ops-report", response_model=AiEffectivenessResponseDto)
async def get_daily_ops_report(
    account_id: Annotated[str, Depends(require_account_access)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    as_of: Annotated[
        str | None,
        Query(alias="asOf", description="YYYY-MM-DD"),
    ] = None,
    instrument_ids: Annotated[
        str | None,
        Query(alias="instrumentIds", description="IDs Estudio separados por coma"),
    ] = None,
) -> dict[str, Any]:
    """R1 — resumen operativo del día (preview web; email = R3)."""
    from datetime import date as date_cls

    day: date_cls | None = None
    if as_of:
        try:
            day = date_cls.fromisoformat(as_of.strip()[:10])
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="asOf inválido (YYYY-MM-DD)") from exc
    ids = [x.strip() for x in (instrument_ids or "").split(",") if x.strip()]
    try:
        bundle = await get_daily_ops_report_use_case(session).execute(
            account_id,
            as_of=day,
            instrument_ids=ids or None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    from bolsa_application.daily_ops_report import DAILY_OPS_REPORT_SCHEMA

    return {
        "data": {
            "schemaVersion": DAILY_OPS_REPORT_SCHEMA,
            "asOf": bundle.as_of.isoformat(),
            "generatedAt": bundle.generated_at,
            "accountId": bundle.account_id,
            "summary": to_account_summary_dto(bundle.summary).model_dump(by_alias=True),
            "ledgerToday": [
                to_ledger_entry_dto(e).model_dump(by_alias=True) for e in bundle.ledger_today
            ],
            "tradesToday": [
                to_ledger_entry_dto(e).model_dump(by_alias=True) for e in bundle.trades_today
            ],
            "week": bundle.week,
            "f3PendingCount": bundle.f3_pending_count,
            "channels": bundle.channels,
            "opinions": bundle.opinions,
            "notes": bundle.notes,
        }
    }


@router.get(
    "/accounts/{account_id}/decision-board",
    response_model=DecisionBoardResponseDto,
)
async def get_decision_board(
    account_id: Annotated[str, Depends(require_account_access)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DecisionBoardResponseDto:
    """F0.6a — Decision Board: vista de solo lectura de oportunidades pendientes.

    No decide ni muta estado: agrupa la cola SEMI_F3 por confirmar y las
    decision sessions recientes con el resultado de su gate (PASS/VETO/
    DEFERRED/unknown).
    """
    if not account_id or not account_id.strip():
        raise HTTPException(status_code=422, detail="account_id no puede estar vacío")
    bundle = await get_decision_board_use_case(session).execute(account_id)
    data = bundle.to_dict()
    return DecisionBoardResponseDto(data=data)


@router.get(
    "/accounts/{account_id}/decision-journal",
    response_model=DecisionJournalListResponseDto,
)
async def get_decision_journal(
    account_id: Annotated[str, Depends(require_account_access)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    instrument_id: Annotated[str | None, Query(alias="instrumentId")] = None,
    since: Annotated[str | None, Query(description="ISO-8601 timestamp inclusive lower bound")] = None,
    event_type: Annotated[str | None, Query(alias="eventType")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> DecisionJournalListResponseDto:
    """ADR-029 F2 — Decision Journal: audit trail append-only del spine (solo lectura).

    Lista cronológica descendente de transiciones registradas por JournalWriter.
    No decide ni muta estado.
    """
    if not account_id or not account_id.strip():
        raise HTTPException(status_code=422, detail="account_id no puede estar vacío")
    result = await get_decision_journal_use_case(session).execute(
        account_id,
        instrument_id=instrument_id,
        since=since,
        event_type=event_type,
        limit=limit,
        offset=offset,
    )
    return DecisionJournalListResponseDto(data=result.to_dict())


@router.post(
    "/accounts/{account_id}/session-verdict",
    response_model=SessionVerdictResponseDto,
)
async def record_session_verdict(
    account_id: Annotated[str, Depends(require_account_access)],
    body: SessionVerdictBodyDto,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> SessionVerdictResponseDto:
    """P4 — «No operar hoy» u otro veredicto de sesión → Decision Journal."""
    if not account_id or not account_id.strip():
        raise HTTPException(status_code=422, detail="account_id no puede estar vacío")
    try:
        result = await get_record_session_verdict_use_case(session).execute(
            account_id=account_id,
            verdict=body.verdict,
            note=body.note,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return SessionVerdictResponseDto(data=result)


@router.get("/accounts/{account_id}/daily-ops-report.pdf")
async def download_daily_ops_digest_pdf(
    account_id: Annotated[str, Depends(require_account_access)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    as_of: Annotated[
        str | None,
        Query(alias="asOf", description="YYYY-MM-DD"),
    ] = None,
    instrument_ids: Annotated[
        str | None,
        Query(alias="instrumentIds", description="IDs Estudio separados por coma"),
    ] = None,
) -> Response:
    """R4 — descarga PDF del resumen operativo (sin email)."""
    from datetime import date as date_cls

    from bolsa_infrastructure.alerts.daily_ops_digest_pdf import (
        build_daily_ops_digest_pdf,
        digest_pdf_filename,
    )

    day: date_cls | None = None
    if as_of:
        try:
            day = date_cls.fromisoformat(as_of.strip()[:10])
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="asOf inválido (YYYY-MM-DD)") from exc
    ids = [x.strip() for x in (instrument_ids or "").split(",") if x.strip()]
    try:
        bundle = await get_daily_ops_report_use_case(session).execute(
            account_id,
            as_of=day,
            instrument_ids=ids or None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    pdf = build_daily_ops_digest_pdf(bundle)
    filename = digest_pdf_filename(bundle)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post(
    "/accounts/{account_id}/daily-ops-report/email",
    response_model=DailyOpsDigestNotifyResponseDto,
)
async def send_daily_ops_digest_email(
    account_id: Annotated[str, Depends(require_account_access)],
    body: SendDailyOpsDigestDto,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DailyOpsDigestNotifyResponseDto:
    """R3 — envío manual HTML del resumen operativo (SMTP + prefs)."""
    from datetime import date as date_cls

    from bolsa_infrastructure.alerts.daily_ops_digest_email import maybe_notify_daily_ops_digest
    from bolsa_infrastructure.config import get_settings

    day: date_cls | None = None
    if body.as_of:
        try:
            day = date_cls.fromisoformat(body.as_of.strip()[:10])
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="asOf inválido (YYYY-MM-DD)") from exc
    ids = [i.strip() for i in (body.instrument_ids or []) if isinstance(i, str) and i.strip()]
    try:
        bundle = await get_daily_ops_report_use_case(session).execute(
            account_id,
            as_of=day,
            instrument_ids=ids or None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    meta = await maybe_notify_daily_ops_digest(
        get_settings(),
        bundle,
        email_to=body.notify_email,
        digest_enabled=body.notify_digest_enabled,
        attach_pdf=body.attach_pdf,
    )
    return DailyOpsDigestNotifyResponseDto(
        data=DailyOpsDigestNotifyDto(
            digest_enabled=bool(meta["digest_enabled"]),
            sent=bool(meta["sent"]),
            skipped_reason=meta.get("skipped_reason"),
            as_of=meta.get("as_of"),
            pdf_attached=bool(meta.get("pdf_attached")),
        )
    )


@router.post(
    "/accounts/{account_id}/deposits",
    response_model=CashMovementResponseDto,
    status_code=201,
    responses=IDEMPOTENCY_CONFLICT_RESPONSES,
)
async def deposit_cash(
    account_id: Annotated[str, Depends(require_account_access)],
    body: DepositCashDto,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> CashMovementResponseDto:
    try:
        result = await get_deposit_cash_use_case(session).execute(
            account_id,
            amount=body.amount,
            note=body.note,
            idempotency_key=body.idempotency_key,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return CashMovementResponseDto(data=to_cash_movement_result_dto(result))


@router.post(
    "/accounts/{account_id}/withdrawals",
    response_model=CashMovementResponseDto,
    status_code=201,
    responses=IDEMPOTENCY_CONFLICT_RESPONSES,
)
async def withdraw_cash(
    account_id: Annotated[str, Depends(require_account_access)],
    body: WithdrawCashDto,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> CashMovementResponseDto:
    try:
        result = await get_withdraw_cash_use_case(session).execute(
            account_id,
            amount=body.amount,
            note=body.note,
            idempotency_key=body.idempotency_key,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return CashMovementResponseDto(data=to_cash_movement_result_dto(result))


@router.get("/accounts/{account_id}/tax-report", response_model=TaxReportResponseDto)
async def get_tax_report(
    account_id: Annotated[str, Depends(require_account_access)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    year: Annotated[int, Query(ge=2000, le=2100)] | None = None,
) -> TaxReportResponseDto:
    report_year = year if year is not None else datetime.now().year
    try:
        report = await get_tax_report_use_case(session).execute(account_id, report_year)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return TaxReportResponseDto(data=to_tax_report_dto(report))


@router.get("/accounts/{account_id}/ledger", response_model=LedgerResponseDto)
async def list_ledger(
    account_id: Annotated[str, Depends(require_account_access)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> LedgerResponseDto:
    try:
        entries = await get_list_ledger_use_case(session).execute(
            account_id,
            limit=limit,
            offset=offset,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return LedgerResponseDto(data=[to_ledger_entry_dto(e) for e in entries])
