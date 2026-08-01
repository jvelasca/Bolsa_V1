from typing import Annotated
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_api.api.dependencies import (
    get_close_account_use_case,
    get_create_account_use_case,
    get_db_session,
    get_delete_account_use_case,
    get_deposit_cash_use_case,
    get_get_account_summary_use_case,
    get_get_account_use_case,
    get_investor_profile_repository,
    get_list_account_summaries_use_case,
    get_list_accounts_use_case,
    get_list_ledger_use_case,
    get_set_default_account_use_case,
    get_tax_report_use_case,
    get_update_account_settings_use_case,
    get_update_account_use_case,
    get_withdraw_cash_use_case,
)
from bolsa_application.investor_profiles import EnsureDefaultInvestorProfile
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
    AccountSummariesResponseDto,
    AccountSummaryResponseDto,
    AccountsResponseDto,
    CashMovementResponseDto,
    CreateInvestmentAccountDto,
    DepositCashDto,
    LedgerResponseDto,
    TaxReportResponseDto,
    UpdateAccountSettingsDto,
    UpdateInvestmentAccountDto,
    WithdrawCashDto,
)

router = APIRouter()


@router.get("/accounts", response_model=AccountsResponseDto)
async def list_accounts(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    type: str | None = Query(default=None),
) -> AccountsResponseDto:
    accounts = await get_list_accounts_use_case(session).execute(account_type=type)
    return AccountsResponseDto(data=[to_investment_account_dto(a) for a in accounts])


@router.get("/accounts/summaries", response_model=AccountSummariesResponseDto)
async def list_account_summaries(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    type: str | None = Query(default=None),
) -> AccountSummariesResponseDto:
    """Hub equity strip — no per-row HTTP and no custody side-effects."""
    summaries = await get_list_account_summaries_use_case(session).execute(account_type=type)
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
    profile_store = get_investor_profile_repository(session)
    if body.investor_profile is not None:
        from bolsa_analytics.cognitive.suggest_policy import suggest_policy_template_from_declared
        from bolsa_application.investor_profiles import CreateInvestorProfile

        ip = body.investor_profile
        suggested = ip.suggested_policy_template_id or suggest_policy_template_from_declared(
            risk_tolerance=ip.risk_tolerance,
            horizon=ip.horizon,
            experience=ip.experience,
        )
        selected = ip.selected_policy_template_id or suggested
        profile_name = (ip.name or "").strip() or f"Perfil · {account.name}".strip()[:80]
        profile = await CreateInvestorProfile(profile_store).execute(
            name=profile_name,
            horizon=ip.horizon,
            objectives=list(ip.objectives),
            risk_tolerance=ip.risk_tolerance,
            experience=ip.experience,
            max_acceptable_loss_pct=ip.max_acceptable_loss_pct,
            notes=ip.notes or "Creado con la cuenta (asistente Nueva demo)",
            suggested_policy_template_id=suggested,
            selected_policy_template_id=selected,
        )
        await profile_store.assign_to_account(account.id, profile.id)
    elif body.active_profile_id:
        existing = await profile_store.get(body.active_profile_id)
        if existing is None:
            raise HTTPException(status_code=400, detail="Perfil inversor no encontrado")
        await profile_store.assign_to_account(account.id, body.active_profile_id)
    else:
        await EnsureDefaultInvestorProfile(profile_store).execute(account.id, account.name)
    account = await get_get_account_use_case(session).execute(account.id)
    return AccountResponseDto(data=to_investment_account_dto(account))


@router.get("/accounts/{account_id}", response_model=AccountResponseDto)
async def get_account(
    account_id: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AccountResponseDto:
    try:
        account = await get_get_account_use_case(session).execute(account_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return AccountResponseDto(data=to_investment_account_dto(account))


@router.patch("/accounts/{account_id}", response_model=AccountResponseDto)
async def update_account(
    account_id: str,
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
    account_id: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AccountResponseDto:
    try:
        account = await get_set_default_account_use_case(session).execute(account_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return AccountResponseDto(data=to_investment_account_dto(account))


@router.patch("/accounts/{account_id}/settings", response_model=AccountResponseDto)
async def update_account_settings(
    account_id: str,
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


@router.post("/accounts/{account_id}/close", response_model=AccountResponseDto)
async def close_account(
    account_id: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AccountResponseDto:
    try:
        account = await get_close_account_use_case(session).execute(account_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return AccountResponseDto(data=to_investment_account_dto(account))


@router.delete("/accounts/{account_id}", status_code=204)
async def delete_account(
    account_id: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> Response:
    try:
        await get_delete_account_use_case(session).execute(account_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return Response(status_code=204)


@router.get("/accounts/{account_id}/summary", response_model=AccountSummaryResponseDto)
async def get_account_summary(
    account_id: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AccountSummaryResponseDto:
    try:
        summary = await get_get_account_summary_use_case(session).execute(account_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return AccountSummaryResponseDto(data=to_account_summary_dto(summary))


@router.post("/accounts/{account_id}/deposits", response_model=CashMovementResponseDto, status_code=201)
async def deposit_cash(
    account_id: str,
    body: DepositCashDto,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> CashMovementResponseDto:
    try:
        result = await get_deposit_cash_use_case(session).execute(
            account_id,
            amount=body.amount,
            note=body.note,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return CashMovementResponseDto(data=to_cash_movement_result_dto(result))


@router.post(
    "/accounts/{account_id}/withdrawals",
    response_model=CashMovementResponseDto,
    status_code=201,
)
async def withdraw_cash(
    account_id: str,
    body: WithdrawCashDto,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> CashMovementResponseDto:
    try:
        result = await get_withdraw_cash_use_case(session).execute(
            account_id,
            amount=body.amount,
            note=body.note,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return CashMovementResponseDto(data=to_cash_movement_result_dto(result))


@router.get("/accounts/{account_id}/tax-report", response_model=TaxReportResponseDto)
async def get_tax_report(
    account_id: str,
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
    account_id: str,
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
