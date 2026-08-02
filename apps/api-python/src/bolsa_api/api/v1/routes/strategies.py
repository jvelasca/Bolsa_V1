from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_analytics.signals.preset_catalog import is_valid_preset_key
from bolsa_api.api.dependencies import (
    get_create_strategy_from_preset_use_case,
    get_create_strategy_use_case,
    get_db_session,
    get_delete_strategy_use_case,
    get_deploy_paper_account_use_case,
    get_draft_strategy_from_prompt_use_case,
    get_list_strategies_use_case,
    get_strategy_definition_use_case,
    get_update_strategy_use_case,
)
from bolsa_api.schemas.account_mappers import to_investment_account_dto
from bolsa_api.schemas.accounts import AccountResponseDto
from bolsa_api.schemas.paper_bridge import DeployPaperAccountRequestDto
from bolsa_api.schemas.strategies import (
    CreateStrategyFromPresetRequestDto,
    DraftStrategyFromPromptRequestDto,
    DraftStrategyFromPromptResponseDto,
    DraftStrategyFromPromptResultDto,
    StrategyDefinitionDetailDto,
    StrategyDefinitionResponseDto,
    StrategyDefinitionsListResponseDto,
    StrategyDefinitionSummaryDto,
    UpdateStrategyDefinitionRequestDto,
    UpsertStrategyDefinitionRequestDto,
)
from bolsa_application.paper_bridge import DeployStrategyToPaperAccount
from bolsa_application.strategies import (
    CreateStrategyDefinition,
    CreateStrategyFromPreset,
    DeleteStrategyDefinition,
    GetStrategyDefinition,
    ListStrategyDefinitions,
    UpdateStrategyDefinition,
)
from bolsa_application.strategy_draft import DraftStrategyFromPrompt
from bolsa_domain.entities.strategy_definition import StrategyDefinitionRecord

router = APIRouter()


def _instrument_ids_from_definition(definition: dict[str, Any]) -> list[str]:
    universe = definition.get("universe") or {}
    raw = universe.get("instrumentIds") if isinstance(universe, dict) else None
    if not isinstance(raw, list):
        return []
    return [str(item) for item in raw if item]


def _summary(record: StrategyDefinitionRecord) -> StrategyDefinitionSummaryDto:
    definition: dict[str, Any] = record.definition
    return StrategyDefinitionSummaryDto(
        id=record.id,
        name=record.name,
        preset_key=record.preset_key,
        origin=record.origin,
        timeframe=record.timeframe,
        kind=str(definition.get("kind", "indicator_signals")),
        instrument_ids=_instrument_ids_from_definition(definition),
        updated_at=record.updated_at,
        created_at=record.created_at,
    )


def _detail(record: StrategyDefinitionRecord) -> StrategyDefinitionDetailDto:
    return StrategyDefinitionDetailDto(
        **_summary(record).model_dump(),
        definition=record.definition,
    )


@router.get("/strategies", response_model=StrategyDefinitionsListResponseDto)
async def list_strategies(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> StrategyDefinitionsListResponseDto:
    use_case: ListStrategyDefinitions = get_list_strategies_use_case(session)
    records = await use_case.execute(limit=200)
    return StrategyDefinitionsListResponseDto(data=[_summary(r) for r in records])


@router.get("/strategies/{strategy_id}", response_model=StrategyDefinitionResponseDto)
async def get_strategy(
    strategy_id: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> StrategyDefinitionResponseDto:
    use_case: GetStrategyDefinition = get_strategy_definition_use_case(session)
    record = await use_case.execute(strategy_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Strategy not found")
    return StrategyDefinitionResponseDto(data=_detail(record))


@router.post(
    "/strategies/from-preset",
    response_model=StrategyDefinitionResponseDto,
    status_code=201,
)
async def create_strategy_from_preset(
    body: CreateStrategyFromPresetRequestDto,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> StrategyDefinitionResponseDto:
    if not is_valid_preset_key(body.preset_key):
        raise HTTPException(status_code=400, detail="presetKey inválido")
    use_case: CreateStrategyFromPreset = get_create_strategy_from_preset_use_case(session)
    record = await use_case.execute(
        name=body.name,
        preset_key=body.preset_key,  # type: ignore[arg-type]
        timeframe=body.timeframe or "1d",
        commission_bps=body.commission_bps or 0,
        slippage_bps=body.slippage_bps or 0,
    )
    return StrategyDefinitionResponseDto(data=_detail(record))


@router.post("/strategies/draft-from-prompt", response_model=DraftStrategyFromPromptResponseDto)
async def draft_strategy_from_prompt(
    body: DraftStrategyFromPromptRequestDto,
) -> DraftStrategyFromPromptResponseDto:
    use_case: DraftStrategyFromPrompt = get_draft_strategy_from_prompt_use_case()
    try:
        result = await use_case.execute(
            prompt=body.prompt,
            instrument_ids=body.instrument_ids,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return DraftStrategyFromPromptResponseDto(
        data=DraftStrategyFromPromptResultDto(
            draft_kind=result.draft_kind,
            preset_key=result.preset_key,
            timeframe=result.timeframe,
            suggested_name=result.suggested_name,
            confidence=result.confidence,
            explanation=result.explanation,
            definition=result.definition,
            engine=result.engine,
            validated=result.validated,
            gate_preset_key=result.gate_preset_key,
            min_score=result.min_score,
            feedback=result.feedback,
        ),
    )


@router.post("/strategies", response_model=StrategyDefinitionResponseDto, status_code=201)
async def create_strategy(
    body: UpsertStrategyDefinitionRequestDto,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> StrategyDefinitionResponseDto:
    use_case: CreateStrategyDefinition = get_create_strategy_use_case(session)
    record = await use_case.execute(name=body.name, definition=body.definition)
    patched = {**record.definition, "id": record.id}
    update_case: UpdateStrategyDefinition = get_update_strategy_use_case(session)
    updated = await update_case.execute(record.id, definition=patched)
    return StrategyDefinitionResponseDto(data=_detail(updated or record))


@router.patch("/strategies/{strategy_id}", response_model=StrategyDefinitionResponseDto)
async def update_strategy(
    strategy_id: str,
    body: UpdateStrategyDefinitionRequestDto,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> StrategyDefinitionResponseDto:
    use_case: UpdateStrategyDefinition = get_update_strategy_use_case(session)
    record = await use_case.execute(strategy_id, name=body.name, definition=body.definition)
    if record is None:
        raise HTTPException(status_code=404, detail="Strategy not found")
    return StrategyDefinitionResponseDto(data=_detail(record))


@router.delete("/strategies/{strategy_id}", status_code=204)
async def delete_strategy(
    strategy_id: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> None:
    use_case: DeleteStrategyDefinition = get_delete_strategy_use_case(session)
    try:
        deleted = await use_case.execute(strategy_id)
    except IntegrityError as exc:
        raise HTTPException(
            status_code=409,
            detail=(
                "No se puede eliminar la estrategia porque sigue "
                "referenciada en la base de datos."
            ),
        ) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="Strategy not found")


@router.post(
    "/strategies/{strategy_id}/paper-account",
    response_model=AccountResponseDto,
    status_code=201,
)
async def deploy_strategy_paper_account(
    strategy_id: str,
    body: DeployPaperAccountRequestDto,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AccountResponseDto:
    use_case: DeployStrategyToPaperAccount = get_deploy_paper_account_use_case(session)
    try:
        account = await use_case.execute(
            strategy_definition_id=strategy_id,
            initial_deposit=body.initial_deposit,
            source_backtest_run_id=body.source_backtest_run_id,
            account_name=body.account_name,
            lab_evidence_hint=body.lab_evidence,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return AccountResponseDto(data=to_investment_account_dto(account))
