"""Use-case: borrador de indicador desde prompt."""

from dataclasses import dataclass
from typing import Any

from bolsa_analytics.research.llm_indicator_draft import draft_indicator_from_prompt_with_llm
from bolsa_analytics.research.prompt_indicator_draft import PromptIndicatorDraftResult


@dataclass(frozen=True, slots=True)
class DraftIndicatorFromPromptResult:
    """Genera borrador Indicator From Prompt Result."""
    definition_id: str
    suggested_preset_name: str
    confidence: float
    explanation: str
    preset: dict[str, Any]
    engine: str
    validated: bool
    feedback: dict[str, Any] | None = None


class DraftIndicatorFromPrompt:
    """Genera borrador Indicator From Prompt."""
    async def execute(self, *, prompt: str) -> DraftIndicatorFromPromptResult:
        draft: PromptIndicatorDraftResult = draft_indicator_from_prompt_with_llm(prompt)
        return DraftIndicatorFromPromptResult(
            definition_id=draft.definition_id,
            suggested_preset_name=draft.suggested_preset_name,
            confidence=draft.confidence,
            explanation=draft.explanation,
            preset=draft.preset,
            engine=draft.engine,
            validated=draft.validated,
            feedback=draft.feedback,
        )
