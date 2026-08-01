"""Prompt Registry — ART-PROMPT en YAML embebido (F1 bootstrap)."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import resources
from typing import Any

import json


@dataclass(frozen=True, slots=True)
class PromptTemplate:
    prompt_id: str
    version: str
    name: str
    system_prompt: str
    user_template: str
    default_provider: str
    default_model: str
    temperature: float
    max_tokens: int
    output_schema_ref: str


def _load_builtin_prompts() -> dict[str, PromptTemplate]:
    prompts: dict[str, PromptTemplate] = {}
    pkg = resources.files("bolsa_ai").joinpath("prompts")
    for name in (
        "prompt_strategy_authoring_v1.json",
        "prompt_indicator_authoring_v1.json",
        "prompt_backtest_coach_v1.json",
        "prompt_backtest_coach_adversary_v1.json",
        "prompt_fundamental_copilot_v1.json",
        "prompt_dia_d_session_evidence_v1.json",
        "prompt_core_r_review_evidence_v1.json",
        "prompt_filing_summary_v1.json",
        "prompt_filing_ask_v1.json",
    ):
        path = pkg.joinpath(name)
        if not path.is_file():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        template = PromptTemplate(
            prompt_id=str(data["id"]),
            version=str(data["version"]),
            name=str(data["name"]),
            system_prompt=str(data["payload"]["systemPrompt"]),
            user_template=str(data["payload"]["userTemplate"]),
            default_provider=str(data["payload"]["modelSettings"]["defaultProvider"]),
            default_model=str(data["payload"]["modelSettings"]["defaultModel"]),
            temperature=float(data["payload"]["modelSettings"]["temperature"]),
            max_tokens=int(data["payload"]["modelSettings"]["maxTokens"]),
            output_schema_ref=str(data["payload"]["outputSchemaRef"]),
        )
        prompts[template.prompt_id] = template
    return prompts


class PromptRegistry:
    def __init__(self, prompts: dict[str, PromptTemplate] | None = None) -> None:
        self._prompts = prompts if prompts is not None else _load_builtin_prompts()

    def get(self, prompt_id: str) -> PromptTemplate:
        try:
            return self._prompts[prompt_id]
        except KeyError as exc:
            raise KeyError(f"ART-PROMPT desconocido: {prompt_id}") from exc

    def render_user(self, prompt_id: str, variables: dict[str, Any]) -> str:
        template = self.get(prompt_id)
        text = template.user_template
        for key, value in variables.items():
            text = text.replace("{{" + key + "}}", str(value))
        return text
