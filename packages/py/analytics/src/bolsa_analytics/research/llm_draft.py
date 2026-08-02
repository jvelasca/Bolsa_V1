"""Strategy authoring via AIGovernanceProxy (RFC-007) + heurística fallback."""

from __future__ import annotations

from typing import Any

from bolsa_ai import get_default_proxy
from bolsa_analytics.research.prompt_draft import (
    _ENGINE_LABELS,
    PromptDraftResult,
    draft_strategy_from_prompt,
)

LLM_ENGINE_OPENAI = "openai_structured_v1"
LLM_ENGINE_OLLAMA = "ollama_structured_v1"

_ENGINE_LABELS_EXTRA = {
    LLM_ENGINE_OPENAI: "OpenAI structured",
    LLM_ENGINE_OLLAMA: "Ollama structured",
}


def _engine_for_provider(provider: str) -> str:
    if provider == "ollama":
        return LLM_ENGINE_OLLAMA
    if provider == "openai":
        return LLM_ENGINE_OPENAI
    return "prompt_catalog_v1"


def _merge_llm_hint(
    heuristic: PromptDraftResult,
    llm_payload: dict[str, Any],
    *,
    engine: str,
) -> PromptDraftResult:
    preset_key = str(llm_payload.get("presetKey") or heuristic.preset_key)
    if preset_key != heuristic.preset_key:
        return heuristic

    suggested = (
        str(llm_payload["suggestedName"])
        if llm_payload.get("suggestedName")
        else heuristic.suggested_name
    )
    definition = dict(heuristic.definition)
    if llm_payload.get("suggestedName"):
        definition["name"] = suggested
    feedback = dict(heuristic.feedback or {})
    if llm_payload.get("explanation"):
        feedback["summary"] = str(llm_payload["explanation"])
    feedback["engineLabel"] = _ENGINE_LABELS_EXTRA.get(
        engine, _ENGINE_LABELS.get(engine, engine)
    )
    return PromptDraftResult(
        draft_kind=heuristic.draft_kind,
        preset_key=heuristic.preset_key,
        timeframe=heuristic.timeframe,
        suggested_name=suggested,
        confidence=min(0.99, heuristic.confidence + 0.05),
        explanation=str(llm_payload.get("explanation") or heuristic.explanation),
        definition=definition,
        engine=engine,
        validated=heuristic.validated,
        gate_preset_key=heuristic.gate_preset_key,
        min_score=heuristic.min_score,
        validation_errors=heuristic.validation_errors,
        feedback=feedback,
    )


def draft_strategy_from_prompt_with_llm(
    prompt: str,
    *,
    instrument_ids: list[str] | None = None,
) -> PromptDraftResult:
    """Proxy First: LLM vía bolsa_ai; si None → catálogo heurístico local."""
    heuristic = draft_strategy_from_prompt(prompt, instrument_ids=instrument_ids)
    completion = get_default_proxy().complete_structured(
        prompt_template_id="prompt_strategy_authoring_v1",
        variables={"user_input": prompt},
    )
    if completion is None:
        return heuristic
    return _merge_llm_hint(
        heuristic,
        completion.payload,
        engine=_engine_for_provider(completion.provider),
    )
