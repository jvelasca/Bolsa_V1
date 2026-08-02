
from bolsa_application.indicator_draft import DraftIndicatorFromPrompt
from fastapi import APIRouter, HTTPException

from bolsa_api.api.dependencies import get_draft_indicator_from_prompt_use_case
from bolsa_api.schemas.indicators_draft import (
    DraftIndicatorFromPromptRequestDto,
    DraftIndicatorFromPromptResponseDto,
    DraftIndicatorFromPromptResultDto,
)

router = APIRouter()


@router.post("/indicators/draft-from-prompt", response_model=DraftIndicatorFromPromptResponseDto)
async def draft_indicator_from_prompt(
    body: DraftIndicatorFromPromptRequestDto,
) -> DraftIndicatorFromPromptResponseDto:
    use_case: DraftIndicatorFromPrompt = get_draft_indicator_from_prompt_use_case()
    try:
        result = await use_case.execute(prompt=body.prompt)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return DraftIndicatorFromPromptResponseDto(
        data=DraftIndicatorFromPromptResultDto(
            definition_id=result.definition_id,
            suggested_preset_name=result.suggested_preset_name,
            confidence=result.confidence,
            explanation=result.explanation,
            preset=result.preset,
            engine=result.engine,
            validated=result.validated,
            feedback=result.feedback,
        ),
    )
