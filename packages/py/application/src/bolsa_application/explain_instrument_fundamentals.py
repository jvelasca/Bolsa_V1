"""Caso de uso F1b — explicación FA (Ollama o heurística)."""

from __future__ import annotations

from typing import Any

from bolsa_analytics.knowledge.fundamental_copilot import (
    build_fundamental_copilot_variables,
    heuristic_fundamental_explanation,
)
from bolsa_application.get_instrument_fundamentals import GetInstrumentFundamentals


class ExplainInstrumentFundamentals:
    def __init__(self, fundamentals: GetInstrumentFundamentals) -> None:
        self._fundamentals = fundamentals

    async def execute(self, instrument_id: str) -> dict[str, Any] | None:
        card = await self._fundamentals.execute(instrument_id)
        if card is None:
            return None

        variables = build_fundamental_copilot_variables(card)
        heuristic = heuristic_fundamental_explanation(card)

        try:
            from bolsa_ai import get_default_proxy

            proxy = get_default_proxy()
            completion = proxy.complete_structured(
                prompt_template_id="prompt_fundamental_copilot_v1",
                variables=variables,
            )
        except Exception:  # noqa: BLE001 — copiloto nunca tumba la API
            completion = None

        if completion is None:
            return {
                "engine": "heuristic",
                "payload": heuristic,
                "provider": None,
                "model": None,
                "card": card,
            }

        payload = completion.payload if isinstance(completion.payload, dict) else None
        paragraphs = payload.get("paragraphs") if payload else None
        if not isinstance(paragraphs, list) or len(paragraphs) < 1:
            payload = heuristic
        else:
            # Normaliza a 3 strings
            cleaned = [str(p).strip() for p in paragraphs if str(p).strip()][:3]
            while len(cleaned) < 3:
                cleaned.append(heuristic["paragraphs"][len(cleaned)])
            disclaimer = (
                str(payload.get("disclaimer")).strip()
                if payload and payload.get("disclaimer")
                else heuristic["disclaimer"]
            )
            payload = {"paragraphs": cleaned, "disclaimer": disclaimer}

        return {
            "engine": f"{completion.provider}_structured_v1",
            "payload": payload,
            "provider": completion.provider,
            "model": completion.model_name,
            "card": card,
        }
