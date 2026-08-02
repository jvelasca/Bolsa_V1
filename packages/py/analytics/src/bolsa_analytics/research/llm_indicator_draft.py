"""Indicator authoring via AIGovernanceProxy (RFC-007) + heurística fallback."""

from __future__ import annotations

from typing import Any

from bolsa_ai import get_default_proxy

from bolsa_analytics.research.prompt_indicator_draft import (
    PromptIndicatorDraftResult,
    draft_indicator_from_prompt,
)

LLM_ENGINE_OPENAI = "openai_structured_v1"
LLM_ENGINE_OLLAMA = "ollama_structured_v1"

_ENGINE_LABELS: dict[str, str] = {
    "indicator_prompt_catalog_v1": "Catálogo heurístico (local)",
    LLM_ENGINE_OPENAI: "OpenAI structured",
    LLM_ENGINE_OLLAMA: "Ollama structured",
}


def _engine_for_provider(provider: str) -> str:
    if provider == "ollama":
        return LLM_ENGINE_OLLAMA
    if provider == "openai":
        return LLM_ENGINE_OPENAI
    return "indicator_prompt_catalog_v1"


def _merge_llm_hint(
    heuristic: PromptIndicatorDraftResult,
    llm_payload: dict[str, Any],
    *,
    engine: str,
) -> PromptIndicatorDraftResult:
    definition_id = str(llm_payload.get("definitionId") or heuristic.definition_id)
    if definition_id != heuristic.definition_id:
        return heuristic

    preset = dict(heuristic.preset)
    parameters = dict(preset.get("parameters") or {})
    if llm_payload.get("period") is not None and "period" in parameters:
        try:
            parameters["period"] = int(llm_payload["period"])
        except (TypeError, ValueError):
            pass
    if definition_id == "technical_rating_v1" and llm_payload.get("showComponents") is True:
        parameters["showComponents"] = True
    if definition_id == "ai_global_score_v1":
        if llm_payload.get("setupWeight") is not None:
            try:
                setup = int(llm_payload["setupWeight"])
                parameters["setupWeight"] = setup
                parameters["dataWeight"] = max(0, 100 - setup)
            except (TypeError, ValueError):
                pass
    preset["parameters"] = parameters

    suggested_name = str(llm_payload.get("suggestedName") or heuristic.suggested_preset_name)
    preset["name"] = suggested_name

    feedback = dict(heuristic.feedback or {})
    if llm_payload.get("explanation"):
        feedback["summary"] = str(llm_payload["explanation"])
    feedback["engineLabel"] = _ENGINE_LABELS.get(engine, engine)

    explanation = str(llm_payload.get("explanation") or heuristic.explanation)

    return PromptIndicatorDraftResult(
        definition_id=heuristic.definition_id,
        suggested_preset_name=suggested_name,
        confidence=min(0.99, heuristic.confidence + 0.05),
        explanation=explanation,
        preset=preset,
        engine=engine,
        validated=heuristic.validated,
        feedback=feedback,
    )


def draft_indicator_from_prompt_with_llm(prompt: str) -> PromptIndicatorDraftResult:
    """Proxy First: LLM vía bolsa_ai; si None → catálogo heurístico local."""
    heuristic = draft_indicator_from_prompt(prompt)
    completion = get_default_proxy().complete_structured(
        prompt_template_id="prompt_indicator_authoring_v1",
        variables={"user_input": prompt},
    )
    if completion is None:
        return heuristic
    return _merge_llm_hint(
        heuristic,
        completion.payload,
        engine=_engine_for_provider(completion.provider),
    )
