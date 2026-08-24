"""CRUD catálogo ART-PROFILE + asignación a cuenta."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_api.api.dependencies import (
    get_db_session,
    get_investor_profile_repository,
    get_list_accounts_use_case,
    require_account_access,
)
from bolsa_api.auth.principal import account_visible_to_principal
from bolsa_api.auth.request_principal import get_request_principal
from bolsa_api.schemas.investor_profiles import (
    AssignProfileDto,
    AssignProfileResponseDto,
    CreateInvestorProfileDto,
    DeclaredProfileDto,
    InvestorProfileDto,
    InvestorProfileListResponseDto,
    InvestorProfileResponseDto,
    UpdateInvestorProfileDto,
)
from bolsa_application.investor_profiles import (
    AssignInvestorProfileToAccount,
    CreateInvestorProfile,
    DeleteInvestorProfile,
    EnsureDefaultsForAccounts,
    GetInvestorProfile,
    ListInvestorProfiles,
    RefreshObservedProfile,
    UpdateInvestorProfile,
)
from bolsa_domain.entities.investor_profile import InvestorProfileRecord
from bolsa_infrastructure.database.repositories.cognitive_repository import (
    SqlAlchemyCognitiveRepository,
)
from bolsa_infrastructure.database.repositories.investor_profile_repository import (
    SqlAlchemyInvestorProfileRepository,
)

router = APIRouter()


def _require_profile_access(
    profile: InvestorProfileRecord | None,
    principal: str,
) -> InvestorProfileRecord:
    if profile is None or not account_visible_to_principal(profile.user_id, principal):
        raise HTTPException(status_code=404, detail="Perfil no encontrado")
    return profile


def _to_dto(p: InvestorProfileRecord) -> InvestorProfileDto:
    return InvestorProfileDto(
        profile_id=p.id,
        name=p.name,
        version=p.version,
        user_id=p.user_id,
        declared=DeclaredProfileDto(
            horizon=p.horizon,
            objectives=list(p.objectives),
            risk_tolerance=p.risk_tolerance,
            experience=p.experience,
            max_acceptable_loss_pct=p.max_acceptable_loss_pct,
            notes=p.notes,
        ),
        suggested_policy_template_id=p.suggested_policy_template_id,
        selected_policy_template_id=p.selected_policy_template_id,
        observed=p.observed,
        updated_by=p.updated_by,
        created_at=p.created_at,
        updated_at=p.updated_at,
    )


@router.get("/investor-profiles", response_model=InvestorProfileListResponseDto)
async def list_investor_profiles(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> InvestorProfileListResponseDto:
    principal = get_request_principal(request)
    store = get_investor_profile_repository(session)
    rows = await ListInvestorProfiles(store).execute(user_id=principal)  # type: ignore[arg-type]
    return InvestorProfileListResponseDto(data=[_to_dto(r) for r in rows])


@router.post("/investor-profiles/ensure-defaults", response_model=InvestorProfileListResponseDto)
async def ensure_default_profiles(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> InvestorProfileListResponseDto:
    """Crea y asigna perfil moderate a cuentas sin active_profile_id (cuentas antiguas)."""
    principal = get_request_principal(request)
    store = get_investor_profile_repository(session)
    accounts = await get_list_accounts_use_case(session).execute(
        owner_user_id=principal,
    )
    missing = [(a.id, a.name) for a in accounts if not a.active_profile_id]
    if missing:
        await EnsureDefaultsForAccounts(store).execute(missing)  # type: ignore[arg-type]
    rows = await ListInvestorProfiles(store).execute(user_id=principal)  # type: ignore[arg-type]
    return InvestorProfileListResponseDto(data=[_to_dto(r) for r in rows])


@router.get("/investor-profiles/{profile_id}", response_model=InvestorProfileResponseDto)
async def get_investor_profile(
    profile_id: str,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> InvestorProfileResponseDto:
    principal = get_request_principal(request)
    store = get_investor_profile_repository(session)
    row = await GetInvestorProfile(store).execute(profile_id)  # type: ignore[arg-type]
    row = _require_profile_access(row, principal)
    return InvestorProfileResponseDto(data=_to_dto(row))


@router.post("/investor-profiles", response_model=InvestorProfileResponseDto)
async def create_investor_profile(
    body: CreateInvestorProfileDto,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> InvestorProfileResponseDto:
    from bolsa_analytics.cognitive.suggest_policy import suggest_policy_template_from_declared

    store = get_investor_profile_repository(session)
    suggested = body.suggested_policy_template_id or suggest_policy_template_from_declared(
        risk_tolerance=body.risk_tolerance,
        horizon=body.horizon,
        experience=body.experience,
    )
    selected = body.selected_policy_template_id or suggested
    row = await CreateInvestorProfile(store).execute(  # type: ignore[arg-type]
        name=body.name,
        horizon=body.horizon,
        objectives=body.objectives,
        risk_tolerance=body.risk_tolerance,
        experience=body.experience,
        max_acceptable_loss_pct=body.max_acceptable_loss_pct,
        notes=body.notes,
        suggested_policy_template_id=suggested,
        selected_policy_template_id=selected,
        user_id=get_request_principal(request),
    )
    return InvestorProfileResponseDto(data=_to_dto(row))


@router.patch("/investor-profiles/{profile_id}", response_model=InvestorProfileResponseDto)
async def update_investor_profile(
    profile_id: str,
    body: UpdateInvestorProfileDto,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> InvestorProfileResponseDto:
    principal = get_request_principal(request)
    store = get_investor_profile_repository(session)
    existing = await GetInvestorProfile(store).execute(profile_id)  # type: ignore[arg-type]
    _require_profile_access(existing, principal)
    kwargs: dict[str, Any] = {}
    if body.name is not None:
        kwargs["name"] = body.name
    if body.horizon is not None:
        kwargs["horizon"] = body.horizon
    if body.objectives is not None:
        kwargs["objectives"] = body.objectives
    if body.risk_tolerance is not None:
        kwargs["risk_tolerance"] = body.risk_tolerance
    if body.experience is not None:
        kwargs["experience"] = body.experience
    if body.suggested_policy_template_id is not None:
        kwargs["suggested_policy_template_id"] = body.suggested_policy_template_id
    if body.selected_policy_template_id is not None:
        kwargs["selected_policy_template_id"] = body.selected_policy_template_id
    # max/notes: allow explicit null via model fields when provided
    data = body.model_dump(exclude_unset=True, by_alias=False)
    if "max_acceptable_loss_pct" in data:
        kwargs["max_acceptable_loss_pct"] = data["max_acceptable_loss_pct"]
    if "notes" in data:
        kwargs["notes"] = data["notes"]
    row = await UpdateInvestorProfile(store).execute(profile_id, **kwargs)  # type: ignore[arg-type]
    if row is None:
        raise HTTPException(status_code=404, detail="Perfil no encontrado")
    return InvestorProfileResponseDto(data=_to_dto(row))


@router.delete("/investor-profiles/{profile_id}")
async def delete_investor_profile(
    profile_id: str,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, bool]:
    principal = get_request_principal(request)
    store = get_investor_profile_repository(session)
    existing = await GetInvestorProfile(store).execute(profile_id)  # type: ignore[arg-type]
    _require_profile_access(existing, principal)
    ok = await DeleteInvestorProfile(store).execute(profile_id)  # type: ignore[arg-type]
    if not ok:
        raise HTTPException(status_code=404, detail="Perfil no encontrado")
    return {"ok": True}


@router.post(
    "/investor-profiles/{profile_id}/refresh-observed",
    response_model=InvestorProfileResponseDto,
)
async def refresh_observed_profile(
    profile_id: str,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    account_id: str | None = Query(default=None, alias="accountId"),
) -> InvestorProfileResponseDto:
    """Recalcula Observed desde Decision Memory y persiste observed_json (no toca Declared)."""
    principal = get_request_principal(request)
    store = get_investor_profile_repository(session)
    existing = await GetInvestorProfile(store).execute(profile_id)  # type: ignore[arg-type]
    _require_profile_access(existing, principal)
    cognitive = SqlAlchemyCognitiveRepository(session)
    memories = await cognitive.list_decision_memory(limit=200, account_id=account_id)
    payloads = [
        {
            "outcome": m.outcome,
            "reasons": list(m.reasons),
        }
        for m in memories
    ]
    row = await RefreshObservedProfile(store).execute(profile_id, memory_payloads=payloads)  # type: ignore[arg-type]
    if row is None:
        raise HTTPException(status_code=404, detail="Perfil no encontrado")
    return InvestorProfileResponseDto(data=_to_dto(row))


@router.put("/accounts/{account_id}/active-profile", response_model=AssignProfileResponseDto)
async def assign_active_profile(
    account_id: Annotated[str, Depends(require_account_access)],
    body: AssignProfileDto,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AssignProfileResponseDto:
    store = get_investor_profile_repository(session)
    try:
        pid = await AssignInvestorProfileToAccount(store).execute(account_id, body.profile_id)  # type: ignore[arg-type]
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return AssignProfileResponseDto(
        data={"accountId": account_id, "activeProfileId": pid},
    )


@router.get("/accounts/{account_id}/active-profile", response_model=InvestorProfileResponseDto)
async def get_active_profile(
    account_id: Annotated[str, Depends(require_account_access)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> InvestorProfileResponseDto:
    store: SqlAlchemyInvestorProfileRepository = get_investor_profile_repository(session)
    row = await store.get_for_account(account_id)
    if row is None:
        raise HTTPException(status_code=404, detail="La cuenta no tiene perfil activo")
    return InvestorProfileResponseDto(data=_to_dto(row))
