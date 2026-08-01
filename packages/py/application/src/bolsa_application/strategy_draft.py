from dataclasses import dataclass

from typing import Any, Literal



from bolsa_analytics.research.llm_draft import draft_strategy_from_prompt_with_llm
from bolsa_analytics.research.prompt_draft import PromptDraftResult





@dataclass(frozen=True, slots=True)

class DraftStrategyFromPromptResult:

    draft_kind: Literal["classic", "hybrid"]

    preset_key: str

    timeframe: str

    suggested_name: str

    confidence: float

    explanation: str

    definition: dict[str, Any]

    engine: str

    validated: bool

    gate_preset_key: str | None = None

    min_score: float | None = None

    feedback: dict[str, Any] | None = None





class DraftStrategyFromPrompt:

    async def execute(

        self,

        *,

        prompt: str,

        instrument_ids: list[str] | None = None,

    ) -> DraftStrategyFromPromptResult:

        draft: PromptDraftResult = draft_strategy_from_prompt_with_llm(
            prompt, instrument_ids=instrument_ids
        )

        return DraftStrategyFromPromptResult(

            draft_kind=draft.draft_kind,

            preset_key=draft.preset_key,

            timeframe=draft.timeframe,

            suggested_name=draft.suggested_name,

            confidence=draft.confidence,

            explanation=draft.explanation,

            definition=draft.definition,

            engine=draft.engine,

            validated=draft.validated,

            gate_preset_key=draft.gate_preset_key,

            min_score=draft.min_score,

            feedback=draft.feedback,

        )

