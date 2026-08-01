"""OpenAI Chat Completions — adapter opcional (cloud)."""

from __future__ import annotations

import json
import os
from typing import Any

from bolsa_ai.models import LlmProvider


class OpenAIAdapter:
    provider: LlmProvider = "openai"

    def is_available(self) -> bool:
        return bool(os.getenv("OPENAI_API_KEY"))

    def complete_json(
        self,
        *,
        system: str,
        user: str,
        model: str,
        temperature: float,
        timeout_seconds: float,
    ) -> dict[str, Any] | None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return None
        try:
            import httpx
        except ImportError:
            return None

        payload = {
            "model": model or os.getenv("BOLSA_LLM_MODEL", "gpt-4o-mini"),
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "response_format": {"type": "json_object"},
            "temperature": temperature,
        }
        try:
            response = httpx.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json=payload,
                timeout=timeout_seconds,
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            parsed = json.loads(content)
            return parsed if isinstance(parsed, dict) else None
        except Exception:
            return None
